"""Orkestrasi AP: OCR → Parser Agent → Contract Agent → Adversarial Auditor → Mesin Kalkulasi (+ Telemetry)."""
import os
import time
import traceback
from dataclasses import asdict

from decimal import Decimal

from sqlmodel import Session, select

from app import auditlog, extractor
from app.audit import AuditContext, decide_status, needs_cfo, norm_invoice, norm_npwp, run_rules
from app.calc import ContractTerms, PostedHistory, TerminCalc, compute_termin, pph_rate
from app.db import session
from app.journal import ap_journal
from app.mocks import ErpError, erp_post
from app.models import Contract, JournalBatch, Termin, Vendor, now
from app.money import ZERO, fmt_rp
from app.ocr import ocr_pdf

D = Decimal
TELEMETRY: dict[int, list[dict]] = {}
JENIS_EN = {"PELAKSANAAN": "construction", "TERINTEGRASI": "integrated", "PERENCANAAN": "design",
            "PENGAWASAN": "supervision"}
SBU_EN = {"KECIL": "small", "MENENGAH": "medium", "BESAR": "large", "TANPA": "no grade"}
STATUS_EN = {"READY": "ready to approve", "DISPUTE": "dispute", "HARD_STOP": "hard stop"}
FINAL = ("POSTED", "REJECTED")


def publish(tid: int, agent: str, msg: str, level: str = "info"):
    TELEMETRY.setdefault(tid, []).append({"ts": time.time(), "agent": agent, "msg": msg, "level": level})
    time.sleep(float(os.getenv("OMNI_TELEMETRY_DELAY", "0.35")))


# ---------- input & kalkulasi ----------

def get(t: Termin, name: str):
    if name in t.overrides:
        return extractor.parse(extractor.KIND[name], t.overrides[name])
    return extractor.value(t.extraction, name)


def terms_of(s: Session, c: Contract) -> tuple[ContractTerms, Vendor]:
    v = s.get(Vendor, c.vendor_id)
    return ContractTerms(dpp_kontrak=D(c.dpp_kontrak), pph_rate=pph_rate(v.jenis, v.sbu), target_date=c.target_date,
                         ret_pct=D(c.ret_pct), um_pct=D(c.um_pct), denda_harian=D(c.denda_harian),
                         denda_cap=D(c.denda_cap)), v


def history(s: Session, contract_id: int, exclude: int | None = None) -> tuple[PostedHistory, Decimal]:
    rows = s.exec(select(Termin).where(Termin.contract_id == contract_id, Termin.status == "POSTED")).all()
    rows = [r for r in rows if r.id != exclude]
    tot = lambda k: sum((D(r.calc_verified[k]) for r in rows), ZERO)  # noqa: E731
    prev = max((D(r.calc_verified["p"]) for r in rows), default=ZERO)
    return PostedHistory(np_sum=tot("np"), um_sum=tot("um"), pen_sum=tot("pen")), prev


def calc_from(d: dict) -> TerminCalc:
    return TerminCalc(**{k: (v if k == "late_days" else D(v)) for k, v in d.items()})


def evaluate(s: Session, t: Termin) -> tuple[list, Decimal]:
    """Hitung ulang kontrak, kalkulasi dua kolom, anomali, dan kebutuhan CFO dari ekstraksi + override."""
    ext = t.extraction
    t.invoice_norm = norm_invoice(get(t, "invoice_no") or "")
    t.npwp_norm = norm_npwp(get(t, "npwp") or "")
    contract = s.get(Contract, t.contract_id) if t.contract_id else None
    if contract is None and (cno := get(t, "contract_no")):
        contract = s.exec(select(Contract).where(Contract.spv_id == t.spv_id, Contract.no_norm == cno)).first()
    t.contract_id = contract.id if contract else None

    klaim, bap, tgl = get(t, "progres_klaim"), get(t, "progres_bap"), get(t, "tanggal_bap")
    klaim = klaim / 100 if klaim is not None else None
    bap = bap / 100 if bap is not None else None
    approved = D(t.overrides["progres_disetujui"]) / 100 if "progres_disetujui" in t.overrides else (
        min(klaim, bap) if klaim is not None and bap is not None else None)

    vendor, prev, cc, cv = None, ZERO, None, None
    if contract and klaim is not None and approved is not None and tgl:
        terms, vendor = terms_of(s, contract)
        hist, prev = history(s, contract.id, exclude=t.id)
        cc, cv = compute_termin(terms, hist, klaim, tgl), compute_termin(terms, hist, approved, tgl)
    t.calc_claim = cc.as_dict() if cc else {}
    t.calc_verified = cv.as_dict() if cv else {}

    dup = None
    if t.invoice_norm and t.npwp_norm:
        others = s.exec(select(Termin).where(Termin.invoice_norm == t.invoice_norm, Termin.npwp_norm == t.npwp_norm,
                                             Termin.id != t.id, Termin.status != "REJECTED")).all()
        if any(o.spv_id != t.spv_id for o in others):
            dup = "OTHER_SPV"
        elif others:
            dup = "SAME_SPV"
    open_other = bool(contract) and s.exec(select(Termin).where(
        Termin.contract_id == contract.id, Termin.id < (t.id or 0),
        Termin.status.not_in(FINAL + ("GAGAL_PROSES",)))).first() is not None
    pph_rate_inv = get(t, "pph_tertulis_rate")
    items = [extractor.parse("money", f["value"]) for f in ext.get("line_items", []) if f.get("grounded")]
    ctx = AuditContext(
        contract_found=contract is not None, progres_klaim=klaim, progres_bap=bap, progres_prev=prev,
        pph_master=terms_of(s, contract)[0].pph_rate if contract else None,
        bruto_tertulis=D(b) if (b := get(t, "bruto_tertulis")) is not None else None,
        bruto_klaim_calc=cc.bruto if cc else None,
        vendor_npwp=vendor.npwp if vendor else t.npwp_norm, ppn_klaim_calc=cc.ppn if cc else None,
        retensi_tertulis=D(r) if (r := get(t, "retensi_tertulis")) is not None else None,
        pph_tertulis_rate=pph_rate_inv / 100 if pph_rate_inv is not None else None,
        line_items_sum=D(sum(items)) if items else None,
        ppn_tertulis=D(p) if (p := get(t, "ppn_tertulis")) is not None else None,
        faktur_found="FAKTUR_PAJAK" in ext.get("page_types", {}).values(),
        faktur_ppn=D(f) if (f := get(t, "faktur_ppn")) is not None else None,
        faktur_npwp=get(t, "faktur_npwp"), duplicate=dup, other_open_termin=open_other,
        pen_left_at_full=bool(cv and approved >= 1 and cv.pen_left > 0),
    )
    anoms = run_rules(ctx)
    t.anomalies = [asdict(a) for a in anoms]
    conf = min((D(1) if n in t.overrides else D(str(ext["fields"][n]["confidence"])) for n in extractor.WAJIB),
               default=ZERO).quantize(D("0.01")) if ext else ZERO
    t.confidence = str(conf)
    t.needs_cfo = needs_cfo(ctx.bruto_tertulis, cc.bruto if cc else None)
    return anoms, conf


# ---------- proses dokumen ----------

def process_termin(tid: int, ext: dict | None = None):
    with session() as s:
        t = s.get(Termin, tid)
        TELEMETRY[tid] = []
        try:
            if not t.pages:
                publish(tid, "Parser Agent", "Running local OCR on the document…")
                t.pages = ocr_pdf(t.pdf_path)
            for p in t.pages:
                src = {"digital": "digital text", "scan": "scanned (RapidOCR)", "unreadable": "UNREADABLE"}
                publish(tid, "Parser Agent", f"Page {p['n']}: {len(p['words'])} words, {src[p['source']]}",
                        "warn" if p["source"] == "unreadable" else "info")
            m = extractor.mode()
            publish(tid, "Parser Agent", f"Sending OCR text to Gemini ({os.getenv('GEMINI_MODEL', 'gemini-flash-latest')})…"
                    if m == "gemini" else "Offline mode: extracting with local text patterns")
            try:
                t.extraction = ext or extractor.extract(t.pages)
            except RuntimeError as e:
                if m != "gemini" or os.getenv("GEMINI_FALLBACK", "1") == "0":
                    raise
                publish(tid, "Parser Agent", f"{e} Switching to the local text-pattern reader.", "warn")
                t.extraction = extractor.extract_offline(t.pages, str(e))
            types = ", ".join(f"p{k}={v}" for k, v in sorted(t.extraction["page_types"].items()))
            publish(tid, "Parser Agent", f"Page types: {types}")
            for n in extractor.WAJIB:
                f = t.extraction["fields"][n]
                if f.get("grounded"):
                    publish(tid, "Parser Agent", f"{n} = {f['value']} (confidence {f['confidence']:.0%})")
                else:
                    publish(tid, "Parser Agent", f"{n}: not found or not grounded in the OCR text, confidence 0", "warn")

            anoms, conf = evaluate(s, t)
            c = s.get(Contract, t.contract_id) if t.contract_id else None
            if c:
                terms, v = terms_of(s, c)
                hist, prev = history(s, c.id, exclude=t.id)
                publish(tid, "Contract Agent", f"Contract {c.no} found: {c.name}, value excl. VAT {fmt_rp(c.dpp_kontrak)}")
                publish(tid, "Contract Agent", f"Vendor {v.name}: {JENIS_EN[v.jenis]}, grade {SBU_EN[v.sbu]}, withholding tax "
                                               f"{terms.pph_rate * 100:.2f}%. Retention {D(c.ret_pct):.0%}, "
                                               f"down payment {D(c.um_pct):.0%}, previous progress {prev:.0%}")
            else:
                publish(tid, "Contract Agent", "Contract not found in this SPV", "warn")
            if anoms:
                for a in anoms:
                    publish(tid, "Adversarial Auditor", f"[{a.severity}] {a.message}",
                            "error" if a.severity != "MEDIUM" else "warn")
            else:
                publish(tid, "Adversarial Auditor", "No anomalies found.")
            if t.calc_verified:
                cc, cv = calc_from(t.calc_claim), calc_from(t.calc_verified)
                publish(tid, "Calculator", f"Net payable claimed {fmt_rp(cc.net)}, verified {fmt_rp(cv.net)}"
                                                f" (difference {fmt_rp(cc.net - cv.net)})")
            t.status = decide_status(anoms, conf)
            publish(tid, "System", f"Confidence {conf:.0%}, status: {STATUS_EN.get(t.status, t.status)}"
                                   + (", needs CFO approval" if t.status == "DISPUTE" and t.needs_cfo else ""))
            t.processed_at = now()
            t.error = None
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            t.status, t.error = "GAGAL_PROSES", str(e)[:500]
            publish(tid, "System", f"Processing failed: {t.error}", "error")
        t.telemetry = list(TELEMETRY[tid])
        auditlog.record(s, actor="system", role="SYSTEM", spv_id=t.spv_id, action="PROCESSED", entity="termin",
                        entity_id=t.id, after={"status": t.status, "confidence": t.confidence,
                                               "anomalies": [a["code"] for a in t.anomalies]})
        s.add(t)
        s.commit()


# ---------- posting ----------

def post(s: Session, t: Termin, actor: str, role: str) -> str:
    """Hitung ulang dari baseline terbaru lalu kirim Batch Jurnal ke ERP mock. Return status baru."""
    before = dict(t.calc_verified)
    evaluate(s, t)
    if not t.calc_verified:
        raise ValueError("Calculation incomplete (contract or progress missing)")
    if before and before != t.calc_verified:
        t.status = "DISPUTE"
        auditlog.record(s, actor=actor, role=role, spv_id=t.spv_id, action="RECALC_CHANGED", entity="termin",
                        entity_id=t.id, before=before, after=t.calc_verified, reason="Baseline changed before posting")
        return t.status
    lines = [{"side": l.side, "account": l.account, "amount": int(l.amount)}
             for l in ap_journal(calc_from(t.calc_verified))]
    batch = s.exec(select(JournalBatch).where(JournalBatch.source == "AP", JournalBatch.source_id == t.id)).first() \
        or JournalBatch(spv_id=t.spv_id, source="AP", source_id=t.id, lines=lines)
    batch.lines = lines
    try:
        batch.erp_ref = erp_post(lines)
        t.erp_ref, t.status, t.posted_at = batch.erp_ref, "POSTED", now()
    except ErpError as e:
        t.status, t.error = "ERP_GAGAL", str(e)
    s.add(batch)
    auditlog.record(s, actor=actor, role=role, spv_id=t.spv_id, action="POST_ERP", entity="termin", entity_id=t.id,
                    after={"status": t.status, "erp_ref": t.erp_ref, "net_payable": t.calc_verified["net"]})
    return t.status
