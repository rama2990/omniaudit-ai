"""HTTP API. Setiap endpoint memeriksa persona (header X-Persona), peran, dan SPV (FR-1, FR-2)."""
import asyncio
import json
import os
import shutil
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app import ar, auditlog, extractor, firestore_sink, pipeline
from app.audit import AP, AR, CFO, Forbidden, InvalidTransition, transition
from app.calc import pph_rate
from app.db import DATA, session
from app.journal import ap_journal
from app.mocks import STATE
from app.models import (AuditLog, Contract, Installment, JournalBatch, Outbox, Persona, Receipt, Spv, Termin, Unit,
                        Vendor, now)

router = APIRouter(prefix="/api")
D = Decimal
OPEN_TERMIN = ("PROCESSING", "READY", "DISPUTE", "HARD_STOP", "MENUNGGU_CFO", "ERP_GAGAL", "GAGAL_PROSES")


def db():
    with session() as s:
        yield s


def me(x_persona: str = Header(...), s: Session = Depends(db)) -> Persona:
    p = s.get(Persona, x_persona)
    if not p:
        raise HTTPException(401, "Unknown persona")
    return p


def can_see(p: Persona, spv_id: str):
    if p.role != CFO and spv_id not in p.spvs:
        raise HTTPException(403, "This SPV is outside your assignment")


def need_role(p: Persona, *roles: str):
    if p.role not in roles:
        raise HTTPException(403, "Your role is not allowed to do this")


def scope(p: Persona, spv: str | None) -> list[str]:
    if spv in (None, "", "ALL"):
        if p.role != CFO:
            raise HTTPException(403, "Only the CFO can view all SPVs")
        return list(p.spvs)
    can_see(p, spv)
    return [spv]


# ---------- persona & meta ----------

@router.get("/personas")
def personas(s: Session = Depends(db)):
    spvs = {x.id: x.name for x in s.exec(select(Spv)).all()}
    return [{**p.model_dump(), "spv_names": {i: spvs[i] for i in p.spvs}} for p in s.exec(select(Persona)).all()]


def demo_tools() -> bool:
    """Reset data & simulasi ERP gagal. Matikan setelah penjurian: OMNI_DEMO_TOOLS=0."""
    return os.getenv("OMNI_DEMO_TOOLS", "1") != "0"


def need_demo_tools():
    if not demo_tools():
        raise HTTPException(403, "Demo tools are turned off on this deployment")


@router.get("/meta")
def meta():
    return {"mode": extractor.mode(), "model": os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
            "erp_fail": STATE["erp_fail"], "demo_tools": demo_tools(), "firestore": firestore_sink.status()}


class Toggle(BaseModel):
    on: bool


class ResetBody(BaseModel):
    mode: str = "standard"


@router.post("/demo/reset")
def demo_reset(body: ResetBody, x_persona: str = Header(...)):
    need_demo_tools()
    # tanpa Depends(db): koneksi database harus tertutup saat file data diganti
    with session() as s:
        if not s.get(Persona, x_persona):
            raise HTTPException(401, "Unknown persona")
    if body.mode not in ("standard", "full_run"):
        raise HTTPException(422, "Mode must be standard or full_run")
    from app.seed import reset
    reset(full_run=body.mode == "full_run")
    STATE["erp_fail"] = False
    pipeline.TELEMETRY.clear()
    return {"ok": True, "mode": body.mode}


@router.post("/demo/erp_fail")
def erp_fail(body: Toggle, p: Persona = Depends(me)):
    need_demo_tools()
    STATE["erp_fail"] = body.on
    return meta()


# ---------- dasbor & antrean ----------

@router.get("/dashboard")
def dashboard(spv: str | None = None, p: Persona = Depends(me), s: Session = Depends(db)):
    spvs = scope(p, spv)
    termins = s.exec(select(Termin).where(Termin.spv_id.in_(spvs))).all()
    receipts = s.exec(select(Receipt).where(Receipt.spv_id.in_(spvs), Receipt.status.in_(ar.OPEN))).all()
    cutoff = now() - timedelta(days=30)
    recent = [t for t in termins if t.status == "POSTED" and t.posted_at and t.posted_at >= cutoff]
    velocity = (sum((t.posted_at - t.uploaded_at).total_seconds() for t in recent) / 60 / len(recent)) if recent else None
    leak = sum((D(t.calc_claim["net"]) - D(t.calc_verified["net"]) for t in termins
                if t.status == "POSTED" and t.calc_claim and t.calc_verified), D(0))
    return {
        "unallocated_ar": sum(r.amount for r in receipts), "unallocated_count": len(receipts),
        "pending_ap": sum(int(t.calc_verified.get("bruto", 0)) for t in termins
                          if t.status not in ("POSTED", "REJECTED") and t.calc_verified),
        "pending_ap_count": sum(t.status not in ("POSTED", "REJECTED") for t in termins),
        "flagged": sum(t.status in ("DISPUTE", "HARD_STOP", "MENUNGGU_CFO") for t in termins),
        "velocity_min": round(velocity, 1) if velocity is not None else None,
        "leakage_prevented": int(leak),
    }


@router.get("/queue")
def queue(spv: str | None = None, p: Persona = Depends(me), s: Session = Depends(db)):
    spvs = scope(p, spv)
    items = []
    for t in s.exec(select(Termin).where(Termin.spv_id.in_(spvs)).order_by(Termin.id.desc())).all():
        if t.uploaded_by == "arsip":
            continue
        c = s.get(Contract, t.contract_id) if t.contract_id else None
        v = s.get(Vendor, c.vendor_id) if c else None
        items.append({"kind": "AP", "id": t.id, "spv": t.spv_id, "party": v.name if v else t.filename,
                      "ref": c.no if c else "-", "amount": int(t.calc_verified.get("bruto", 0) or 0),
                      "status": t.status, "score": float(t.confidence),
                      "severities": sorted({a["severity"] for a in t.anomalies}), "needs_cfo": t.needs_cfo,
                      "at": t.uploaded_at.isoformat()})
    for r in s.exec(select(Receipt).where(Receipt.spv_id.in_(spvs)).order_by(Receipt.id.desc())).all():
        items.append({"kind": "AR", "id": r.id, "spv": r.spv_id, "party": r.sender, "ref": r.memo, "amount": r.amount,
                      "status": r.status, "score": float(r.candidates[0]["score"]) if r.candidates else 0.0,
                      "severities": ["DUP"] if r.dup_flag else [], "needs_cfo": r.penalty_status == "MENUNGGU_CFO",
                      "at": r.uploaded_at.isoformat()})
    return items


# ---------- AP ----------

@router.post("/ap/upload")
def ap_upload(bg: BackgroundTasks, spv: str = Form(...), file: UploadFile = File(...), p: Persona = Depends(me),
              s: Session = Depends(db)):
    need_role(p, AP)
    can_see(p, spv)
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    t = Termin(spv_id=spv, filename=file.filename, uploaded_by=p.id)
    s.add(t)
    s.flush()
    dest = DATA / "uploads" / f"termin-{t.id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if dest.stat().st_size > 25 * 1024 * 1024:
        dest.unlink()
        raise HTTPException(400, "File is larger than 25 MB")
    import pymupdf
    try:
        with pymupdf.open(dest) as doc:
            if doc.page_count > 30:
                raise HTTPException(400, "At most 30 pages")
    except HTTPException:
        dest.unlink()
        raise
    except Exception:
        dest.unlink()
        raise HTTPException(400, "The PDF is damaged or unreadable")
    t.pdf_path = str(dest)
    auditlog.record(s, actor=p.id, role=p.role, spv_id=spv, action="UPLOAD", entity="termin", entity_id=t.id,
                    after={"filename": file.filename})
    s.commit()
    bg.add_task(pipeline.process_termin, t.id)
    return {"id": t.id}


ANOMALY_FIELDS = {
    "OVERBILLING": ["progres_klaim", "progres_bap"], "MATEMATIKA": ["bruto_tertulis", "ppn_tertulis", "line_items"],
    "NILAI_TIDAK_SESUAI_PROGRES": ["bruto_tertulis"], "PAJAK_SBU": ["pph_tertulis_rate"],
    "FAKTUR_PAJAK": ["faktur_ppn", "faktur_npwp"], "KLAIM_GANDA": ["invoice_no", "npwp"],
    "TERMIN_TIDAK_VALID": ["progres_klaim"], "KONTRAK_TIDAK_DITEMUKAN": ["contract_no"],
}


def _termin(s: Session, tid: int, p: Persona) -> Termin:
    t = s.get(Termin, tid)
    if not t:
        raise HTTPException(404, "Bill not found")
    can_see(p, t.spv_id)
    return t


def allowed_actions(t: Termin, p: Persona) -> list[str]:
    from app.audit import ALLOWED
    acts = [a for (st, a), (roles, _) in ALLOWED.items() if st == t.status and p.role in roles]
    if t.status == "DISPUTE" and t.needs_cfo:
        acts = [a for a in acts if a != "post"]
    if t.status == "DISPUTE" and not t.needs_cfo:
        acts = [a for a in acts if a != "submit_cfo"]
    if t.status in ("READY", "DISPUTE") and p.role == AP:
        acts += ["override", "set_contract"]
    return acts


@router.get("/ap/termin/{tid}")
def termin_detail(tid: int, p: Persona = Depends(me), s: Session = Depends(db)):
    t = _termin(s, tid, p)
    words = {w["id"]: (pg["n"], w) for pg in t.pages for w in pg["words"]}
    hot = {f for a in t.anomalies for f in ANOMALY_FIELDS.get(a["code"], [])}

    def boxes(ids):
        return [{"page": words[i][0], "bbox": words[i][1]["bbox"]} for i in ids if i in words]

    fields = []
    ext = t.extraction or {}
    for n in extractor.WAJIB + extractor.OPSIONAL:
        f = (ext.get("fields") or {}).get(n)
        if not f:
            continue
        fields.append({"name": n, "required": n in extractor.WAJIB, "value": f.get("value"),
                       "override": t.overrides.get(n), "confidence": f.get("confidence", 0),
                       "grounded": f.get("grounded", False), "boxes": boxes(f.get("word_ids", [])), "hot": n in hot})
    for k, f in enumerate(ext.get("line_items") or []):
        fields.append({"name": f"line_item_{k + 1}", "required": False, "value": f.get("value"), "override": None,
                       "confidence": f.get("confidence", 0), "grounded": f.get("grounded", False),
                       "boxes": boxes(f.get("word_ids", [])), "hot": "line_items" in hot})
    contract = vendor = None
    summary = {}
    if t.contract_id:
        c = s.get(Contract, t.contract_id)
        v = s.get(Vendor, c.vendor_id)
        hist, prev = pipeline.history(s, c.id, exclude=t.id)
        contract = {**c.model_dump(mode="json"), "dpp_kontrak": c.dpp_kontrak}
        vendor = v.model_dump()
        summary = {"pph_rate": str(pph_rate(v.jenis, v.sbu)), "progres_sebelumnya": str(prev),
                   "um_saldo": str(D(t.calc_verified["um_saldo_before"])) if t.calc_verified else None,
                   "late_days": t.calc_verified.get("late_days") if t.calc_verified else None,
                   "pen_left": t.calc_verified.get("pen_left") if t.calc_verified else None,
                   "pen_posted": str(hist.pen_sum)}
    journal = []
    if t.calc_verified:
        journal = [{"side": l.side, "account": l.account, "amount": int(l.amount)}
                   for l in ap_journal(pipeline.calc_from(t.calc_verified))]
    contracts = [{"id": c.id, "no": c.no, "name": c.name}
                 for c in s.exec(select(Contract).where(Contract.spv_id == t.spv_id)).all()]
    return {
        "id": t.id, "spv_id": t.spv_id, "status": t.status, "filename": t.filename, "confidence": t.confidence,
        "needs_cfo": t.needs_cfo, "erp_ref": t.erp_ref, "error": t.error, "anomalies": t.anomalies,
        "calc_claim": t.calc_claim, "calc_verified": t.calc_verified, "overrides": t.overrides,
        "pages": [{"n": pg["n"], "width": pg["width"], "height": pg["height"], "source": pg["source"],
                   "type": (ext.get("page_types") or {}).get(str(pg["n"])) or (ext.get("page_types") or {}).get(pg["n"])}
                  for pg in t.pages],
        "fields": fields, "contract": contract, "vendor": vendor, "summary": summary, "journal": journal,
        "telemetry": t.telemetry or pipeline.TELEMETRY.get(t.id, []), "actions": allowed_actions(t, p),
        "mode": ext.get("mode"), "model": ext.get("model"), "fallback": ext.get("fallback_reason"),
        "contracts": contracts,
        "uploaded_at": t.uploaded_at.isoformat(), "posted_at": t.posted_at.isoformat() if t.posted_at else None,
    }


@router.get("/ap/termin/{tid}/pdf")
def termin_pdf(tid: int, x_persona: str | None = Header(None), persona: str | None = None, s: Session = Depends(db)):
    p = s.get(Persona, x_persona or persona or "")
    if not p:
        raise HTTPException(401, "Unknown persona")
    t = _termin(s, tid, p)
    return FileResponse(t.pdf_path, media_type="application/pdf")


@router.get("/ap/termin/{tid}/events")
async def termin_events(tid: int, persona: str):
    with session() as s:
        p = s.get(Persona, persona)
        if not p:
            raise HTTPException(401, "Unknown persona")
        _termin(s, tid, p)

    async def gen():
        sent = 0
        while True:
            with session() as s:
                t = s.get(Termin, tid)
                status = t.status
                events = pipeline.TELEMETRY.get(tid) or t.telemetry or []
            for e in events[sent:]:
                yield f"data: {json.dumps(e)}\n\n"
            sent = len(events)
            if status != "PROCESSING":
                yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(gen(), media_type="text/event-stream")


class ApAction(BaseModel):
    action: str
    reason: str = ""
    field: str | None = None
    value: str | None = None
    contract_id: int | None = None


@router.post("/ap/termin/{tid}/action")
def termin_action(tid: int, body: ApAction, bg: BackgroundTasks, p: Persona = Depends(me), s: Session = Depends(db)):
    t = _termin(s, tid, p)
    a = body.action
    before = {"status": t.status}
    if a in ("override", "set_contract"):
        need_role(p, AP)
        if t.status not in ("READY", "DISPUTE"):
            raise HTTPException(409, "The bill cannot be changed in this status")
        if len(body.reason.strip()) < 10:
            raise HTTPException(422, "An override reason is required (at least 10 characters)")
        if a == "set_contract":
            c = s.get(Contract, body.contract_id or 0)
            if not c or c.spv_id != t.spv_id:
                raise HTTPException(422, "Contract not found in this SPV")
            before["contract_id"], t.contract_id = t.contract_id, c.id
        else:
            name = body.field or ""
            if name not in extractor.WAJIB + extractor.OPSIONAL + ["progres_disetujui"]:
                raise HTTPException(422, "Unknown field")
            if name == "progres_disetujui":
                k, b = pipeline.get(t, "progres_klaim"), pipeline.get(t, "progres_bap")
                try:
                    val = D(str(body.value).replace(",", "."))
                except Exception:
                    raise HTTPException(422, "Invalid progress value")
                if k is not None and b is not None and val > min(k, b):
                    raise HTTPException(422, "Approved progress cannot exceed the lower of claimed and inspected progress")
                body.value = str(val)
            elif extractor.parse(extractor.KIND[name], body.value) is None:
                raise HTTPException(422, "Invalid value format")
            before[name] = t.overrides.get(name) or (t.extraction["fields"].get(name) or {}).get("value")
            t.overrides = {**t.overrides, name: body.value}
        pipeline.evaluate(s, t)
        auditlog.record(s, actor=p.id, role=p.role, spv_id=t.spv_id, action=a.upper(), entity="termin", entity_id=t.id,
                        before=before, after={"overrides": t.overrides, "net": t.calc_verified.get("net")},
                        reason=body.reason)
        s.add(t)
        s.commit()
        return termin_detail(tid, p, s)

    try:
        target = transition(t.status, a, p.role)
    except Forbidden as e:
        raise HTTPException(403, str(e))
    except InvalidTransition as e:
        raise HTTPException(409, str(e))
    if a in ("reject", "cfo_reject", "flag", "cfo_unlock") and len(body.reason.strip()) < 10:
        raise HTTPException(422, "A reason is required (at least 10 characters)")
    if t.status == "DISPUTE" and a == "post" and t.needs_cfo:
        raise HTTPException(409, "Claim above IDR 500 million: send to the CFO")
    if a == "submit_cfo" and not t.needs_cfo:
        raise HTTPException(409, "This bill does not need CFO approval")
    if target == "POST":
        try:
            pipeline.post(s, t, p.id, p.role)
        except ValueError as e:
            raise HTTPException(409, str(e))
    elif target == "PROCESSING":
        t.status = "PROCESSING"
        bg.add_task(pipeline.process_termin, t.id)
    else:
        t.status = target
    auditlog.record(s, actor=p.id, role=p.role, spv_id=t.spv_id, action=a.upper(), entity="termin", entity_id=t.id,
                    before=before, after={"status": t.status, "erp_ref": t.erp_ref}, reason=body.reason)
    s.add(t)
    s.commit()
    return termin_detail(tid, p, s)


@router.get("/ap/contracts")
def contracts(spv: str, p: Persona = Depends(me), s: Session = Depends(db)):
    can_see(p, spv)
    return s.exec(select(Contract).where(Contract.spv_id == spv)).all()


# ---------- AR ----------

@router.post("/ar/upload")
async def ar_upload(spv: str = Form(...), file: UploadFile = File(...), p: Persona = Depends(me),
                    s: Session = Depends(db)):
    need_role(p, AR)
    can_see(p, spv)
    try:
        stats = ar.ingest_csv(s, spv, (await file.read()).decode("utf-8-sig"), p.id, p.role)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"Invalid CSV: {e}")
    s.commit()
    return stats


def _receipt(s: Session, rid: int, p: Persona) -> Receipt:
    r = s.get(Receipt, rid)
    if not r:
        raise HTTPException(404, "Payment not found")
    can_see(p, r.spv_id)
    return r


def _unit_view(s: Session, unit_id: int, on: str | None = None):
    u = s.get(Unit, unit_id)
    insts = s.exec(select(Installment).where(Installment.unit_id == unit_id).order_by(Installment.seq)).all()
    return {**u.model_dump(), "installments": [i.model_dump(mode="json") for i in insts]}


@router.get("/ar/receipt/{rid}")
def receipt_detail(rid: int, unit_id: int | None = None, waive: bool = False, p: Persona = Depends(me),
                   s: Session = Depends(db)):
    r = _receipt(s, rid, p)
    uid = unit_id or r.unit_id or (r.candidates[0]["unit_id"] if r.candidates else None)
    preview = r.allocation if r.status == "ALLOCATED" else (ar.preview(s, r, uid, waive)[0] if uid else None)
    outbox = s.exec(select(Outbox).where(Outbox.receipt_id == r.id)).all()
    return {**r.model_dump(mode="json"), "selected_unit": _unit_view(s, uid) if uid else None, "preview": preview,
            "outbox": [o.model_dump(mode="json") for o in outbox], "waiver_reasons": ar.WAIVER_REASONS,
            "can_confirm": p.role == AR and r.status in ar.OPEN}


class Confirm(BaseModel):
    unit_id: int
    waiver: dict | None = None


@router.post("/ar/receipt/{rid}/confirm")
def receipt_confirm(rid: int, body: Confirm, p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, AR)
    r = _receipt(s, rid, p)
    try:
        ar.confirm(s, r, body.unit_id, body.waiver, p.id, p.role)
    except ValueError as e:
        raise HTTPException(422, str(e))
    s.commit()
    return receipt_detail(rid, None, False, p, s)


@router.get("/ar/units")
def units(spv: str, q: str = "", p: Persona = Depends(me), s: Session = Depends(db)):
    can_see(p, spv)
    q = q.upper().strip()
    out = []
    for u in s.exec(select(Unit).where(Unit.spv_id == spv)).all():
        if not q or q in u.code.upper() or q in u.buyer.upper() or q in u.va:
            out.append({"id": u.id, "code": u.code, "buyer": u.buyer, "va": u.va})
    return out[:30]


# ---------- CFO ----------

@router.get("/cfo/queue")
def cfo_queue(p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, CFO)
    ts = s.exec(select(Termin).where(Termin.status.in_(("MENUNGGU_CFO", "HARD_STOP")))).all()
    rs = s.exec(select(Receipt).where(Receipt.penalty_status == "MENUNGGU_CFO")).all()
    out = []
    for t in ts:
        c = s.get(Contract, t.contract_id) if t.contract_id else None
        out.append({"kind": "AP", "id": t.id, "spv": t.spv_id, "status": t.status, "ref": c.no if c else t.filename,
                    "amount": int(t.calc_claim.get("bruto", 0) or 0), "anomalies": t.anomalies})
    for r in rs:
        out.append({"kind": "WAIVER", "id": r.id, "spv": r.spv_id, "status": r.penalty_status, "ref": r.sender,
                    "amount": int(D(r.allocation.get("total_denda", "0"))), "waiver": r.waiver})
    return out


class WaiverDecision(BaseModel):
    approve: bool
    reason: str = ""


@router.post("/cfo/waiver/{rid}")
def cfo_waiver(rid: int, body: WaiverDecision, p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, CFO)
    r = _receipt(s, rid, p)
    try:
        ar.cfo_waiver(s, r, body.approve, p.id, p.role, body.reason)
    except ValueError as e:
        raise HTTPException(409, str(e))
    s.commit()
    return {"penalty_status": r.penalty_status}


@router.get("/audit")
def audit(limit: int = 200, p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, CFO)
    return s.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()


@router.get("/audit/verify")
def audit_verify(p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, CFO)
    return auditlog.verify(s)


@router.post("/demo/tamper")
def tamper(p: Persona = Depends(me), s: Session = Depends(db)):
    """Demo: ubah satu entri langsung di database untuk menunjukkan rantai hash putus."""
    need_role(p, CFO)
    e = s.exec(select(AuditLog).where(AuditLog.action == "POST_ERP").order_by(AuditLog.id.desc())).first() \
        or s.exec(select(AuditLog).order_by(AuditLog.id.desc())).first()
    e.after = {**e.after, "net_payable": "1"}
    s.add(e)
    s.commit()
    return {"tampered_id": e.id}


@router.get("/accuracy")
def accuracy(p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, CFO)
    stats = {n: [0, 0] for n in extractor.WAJIB}
    for t in s.exec(select(Termin).where(Termin.uploaded_by != "arsip")).all():
        for n in extractor.WAJIB:
            if (t.extraction.get("fields") or {}).get(n):
                stats[n][0] += 1
                stats[n][1] += n in t.overrides
    return [{"field": n, "total": a, "overridden": o, "accuracy": (a - o) / a if a else None}
            for n, (a, o) in stats.items()]


@router.get("/outbox")
def outbox(p: Persona = Depends(me), s: Session = Depends(db)):
    need_role(p, AR, CFO)
    rows = s.exec(select(Outbox).order_by(Outbox.id.desc()).limit(100)).all()
    out = []
    for o in rows:
        r = s.get(Receipt, o.receipt_id)
        if p.role == CFO or r.spv_id in p.spvs:
            out.append(o.model_dump(mode="json"))
    return out


@router.get("/outbox/{oid}/attachment")
def outbox_attachment(oid: int, persona: str, s: Session = Depends(db)):
    p = s.get(Persona, persona)
    o = s.get(Outbox, oid)
    if not p or not o:
        raise HTTPException(404)
    can_see(p, s.get(Receipt, o.receipt_id).spv_id)
    return FileResponse(o.attachment, media_type="application/pdf")


@router.get("/journals")
def journals(source: str, source_id: int, p: Persona = Depends(me), s: Session = Depends(db)):
    rows = s.exec(select(JournalBatch).where(JournalBatch.source == source, JournalBatch.source_id == source_id)).all()
    for b in rows:
        can_see(p, b.spv_id)
    return rows
