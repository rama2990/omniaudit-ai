"""Layanan AR: ingest rekening koran (FR-29), pencocokan (FR-31..33), alokasi & notifikasi (FR-34..37)."""
import csv
import io
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app import auditlog
from app.allocation import Inst, allocate
from app.journal import ar_journal, penalty_journal
from app.matching import Receipt as R
from app.matching import UnitInfo, match_status, score_receipt
from app.mocks import ErpError, erp_post, receipt_pdf
from app.models import Installment, JournalBatch, Outbox, Receipt, Unit, now
from app.money import fmt_rp

OPEN = ("UNALLOCATED", "RECOMMENDED", "MANUAL_REVIEW")
WAIVER_REASONS = ("Pencairan KPR Bank", "Promosi Special Waiver", "Kewenangan Eksekutif")


def _insts(s: Session, unit_id: int) -> list[Installment]:
    return list(s.exec(select(Installment).where(Installment.unit_id == unit_id).order_by(Installment.seq)).all())


def _to_inst(i: Installment) -> Inst:
    return Inst(id=i.id, seq=i.seq, due=i.due, amount=Decimal(i.amount), paid=Decimal(i.paid))


def units_info(s: Session, spv_id: str) -> list[UnitInfo]:
    units = s.exec(select(Unit).where(Unit.spv_id == spv_id)).all()
    by_unit: dict[int, list[Inst]] = {}
    for i in s.exec(select(Installment).where(Installment.unit_id.in_([u.id for u in units]))).all():
        by_unit.setdefault(i.unit_id, []).append(_to_inst(i))
    return [UnitInfo(u.id, u.code, u.buyer, u.va, by_unit.get(u.id, [])) for u in units]


def _as_r(r: Receipt) -> R:
    return R(r.date, r.sender, Decimal(r.amount), r.memo, r.va or None)


def score(s: Session, r: Receipt, infos: list[UnitInfo]):
    if r.va and (u := next((x for x in infos if x.va == r.va), None)):
        unpaid = sorted([i for i in u.installments if i.remaining > 0], key=lambda i: i.due)
        r.candidates = [{"unit_id": u.id, "code": u.code, "buyer": u.buyer, "s_unit": "1", "s_nama": "1",
                         "s_nominal": "1", "score": "1", "via": "VA"}]
        late = bool(unpaid) and unpaid[0].due < r.date
        r.status = "RECOMMENDED" if late or not unpaid else "AUTO"
        return
    cands = score_receipt(_as_r(r), infos)
    r.candidates = [{k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(c).items()} for c in cands]
    r.status = "RECOMMENDED" if match_status(cands) == "RECOMMENDED" else "MANUAL_REVIEW"


def ingest_csv(s: Session, spv_id: str, text: str, actor: str, role: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    required = {"tanggal", "nama_pengirim", "bank", "nominal", "berita"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"Kolom CSV wajib: {', '.join(sorted(required))}")
    infos = units_info(s, spv_id)
    stats = {"rows": 0, "auto": 0, "recommended": 0, "manual": 0, "duplicates": 0}
    for row in rows:
        r = Receipt(spv_id=spv_id, date=date.fromisoformat(row["tanggal"].strip()), sender=row["nama_pengirim"].strip(),
                    bank=row["bank"].strip(), amount=int(row["nominal"].replace(".", "").strip()),
                    memo=row["berita"].strip(), ref=(row.get("referensi") or "").strip(),
                    va=(row.get("no_va") or "").strip())
        r.dup_flag = s.exec(select(Receipt).where(
            Receipt.spv_id == spv_id, Receipt.date == r.date, Receipt.amount == r.amount, Receipt.memo == r.memo,
            Receipt.sender == r.sender, Receipt.ref == r.ref)).first() is not None
        stats["duplicates"] += r.dup_flag
        score(s, r, infos)
        s.add(r)
        s.flush()
        stats["rows"] += 1
        if r.status == "AUTO" and not r.dup_flag:
            confirm(s, r, r.candidates[0]["unit_id"], None, "system", "SYSTEM")
            infos = units_info(s, spv_id)
            stats["auto"] += 1
        else:
            if r.status == "AUTO":
                r.status = "RECOMMENDED"
            stats["recommended" if r.status == "RECOMMENDED" else "manual"] += 1
    auditlog.record(s, actor=actor, role=role, spv_id=spv_id, action="UPLOAD_CSV", entity="receipt", entity_id=0,
                    after=stats)
    return stats


def preview(s: Session, r: Receipt, unit_id: int, waive: bool) -> dict:
    unpaid = [_to_inst(i) for i in _insts(s, unit_id) if i.paid < i.amount]
    a = allocate(Decimal(r.amount), r.date, unpaid, waive=waive)
    return {"lines": [{k: str(v) if isinstance(v, (Decimal, date)) else v for k, v in asdict(l).items()} for l in a.lines],
            "titipan": str(a.titipan), "selisih_transfer": str(a.selisih_transfer), "total_denda": str(a.total_denda),
            "waived": a.waived}, a


def confirm(s: Session, r: Receipt, unit_id: int, waiver: dict | None, actor: str, role: str) -> Receipt:
    if r.status not in OPEN + ("AUTO",):
        raise ValueError("Penerimaan sudah dialokasikan")
    unit = s.get(Unit, unit_id)
    if unit is None or unit.spv_id != r.spv_id:
        raise ValueError("Unit tidak ditemukan di SPV ini")
    if waiver:
        if waiver.get("reason") not in WAIVER_REASONS:
            raise ValueError("Alasan Waiver tidak valid")
        if not (waiver.get("justification") or "").strip():
            raise ValueError("Justifikasi Waiver wajib diisi")
    pending_cfo = bool(waiver) and waiver["reason"] == "Kewenangan Eksekutif"
    data, a = preview(s, r, unit_id, waive=bool(waiver))
    # update angsuran
    insts = {i.id: i for i in _insts(s, unit_id)}
    for l in a.lines:
        i = insts[l.inst_id]
        i.paid = i.amount if l.settled else i.paid + int(l.pokok)
        s.add(i)
    lines = [{"side": x.side, "account": x.account, "amount": int(x.amount)}
             for x in ar_journal(a, Decimal(r.amount), include_penalty=not waiver)]
    batch = JournalBatch(spv_id=r.spv_id, source="AR", source_id=r.id, lines=lines)
    try:
        batch.erp_ref = erp_post(lines)
    except ErpError:
        batch.erp_ref = None  # ponytail: AR tidak punya status ERP_GAGAL; batch tersimpan untuk kirim ulang manual
    s.add(batch)
    r.unit_id, r.allocation, r.status, r.allocated_at, r.erp_ref = unit_id, data, "ALLOCATED", now(), batch.erp_ref
    r.waiver = {**waiver, "by": actor} if waiver else {}
    r.penalty_status = ("MENUNGGU_CFO" if pending_cfo else "WAIVED") if waiver else (
        "DITAGIH" if a.total_denda > 0 else "")
    pdf = receipt_pdf(r.id, unit.buyer, unit.code, r.amount, r.date.isoformat(), data["lines"], r.erp_ref or "-")
    msg = (f"Yth. {unit.buyer}, pembayaran {fmt_rp(r.amount)} untuk unit {unit.code} tanggal {r.date:%d-%m-%Y} "
           f"telah kami terima dan alokasikan. Kuitansi digital terlampir.")
    if a.total_denda > 0 and not waiver:
        msg += f" Denda keterlambatan {fmt_rp(a.total_denda)} tercatat."
    s.add(Outbox(receipt_id=r.id, channel="WHATSAPP", to=unit.phone, body=msg, attachment=pdf))
    s.add(Outbox(receipt_id=r.id, channel="EMAIL", to=unit.email, body=msg, attachment=pdf))
    s.add(r)
    auditlog.record(s, actor=actor, role=role, spv_id=r.spv_id, action="ALLOCATE", entity="receipt", entity_id=r.id,
                    after={"unit": unit.code, "amount": r.amount, "denda": str(a.total_denda),
                           "waiver": r.waiver.get("reason", ""), "erp_ref": r.erp_ref},
                    reason=(waiver or {}).get("justification", ""))
    s.flush()
    infos = units_info(s, r.spv_id)
    for other in s.exec(select(Receipt).where(Receipt.spv_id == r.spv_id, Receipt.status.in_(OPEN))).all():
        score(s, other, infos)  # angsuran berubah -> skor ulang
        if other.status == "AUTO":
            other.status = "RECOMMENDED"
        s.add(other)
    return r


def cfo_waiver(s: Session, r: Receipt, approve: bool, actor: str, role: str, reason: str) -> Receipt:
    if r.penalty_status != "MENUNGGU_CFO":
        raise ValueError("Tidak ada Waiver yang menunggu CFO")
    total = Decimal(r.allocation["total_denda"])
    if approve:
        r.penalty_status = "WAIVED"
    else:
        r.penalty_status = "DITAGIH"
        lines = [{"side": x.side, "account": x.account, "amount": int(x.amount)} for x in penalty_journal(total)]
        b = JournalBatch(spv_id=r.spv_id, source="AR", source_id=r.id, lines=lines)
        try:
            b.erp_ref = erp_post(lines)
        except ErpError:
            pass
        s.add(b)
    s.add(r)
    auditlog.record(s, actor=actor, role=role, spv_id=r.spv_id, action="CFO_WAIVER_" + ("APPROVE" if approve else "REJECT"),
                    entity="receipt", entity_id=r.id, after={"penalty_status": r.penalty_status}, reason=reason)
    return r
