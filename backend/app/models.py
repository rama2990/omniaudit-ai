"""Tabel SQLite. Uang disimpan sebagai int rupiah; persen sebagai str Decimal."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


def J(default=None):
    return Field(default_factory=lambda: default() if callable(default) else default, sa_column=Column(JSON))


class Spv(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str


class Persona(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    role: str
    title: str
    spvs: list = J(list)


class Vendor(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    npwp: str  # 16 digit
    jenis: str  # PELAKSANAAN | TERINTEGRASI | PERENCANAAN | PENGAWASAN
    sbu: str  # KECIL | MENENGAH | BESAR | TANPA


class Contract(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spv_id: str = Field(index=True)
    no: str
    no_norm: str = Field(index=True)
    name: str
    vendor_id: int
    dpp_kontrak: int
    ret_pct: str = "0.05"
    um_pct: str = "0"
    target_date: date
    denda_harian: str = "0.002"
    denda_cap: str = "0.05"


class Termin(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spv_id: str = Field(index=True)
    contract_id: int | None = None
    status: str = "PROCESSING"
    filename: str = ""
    pdf_path: str = ""
    uploaded_by: str = ""
    uploaded_at: datetime = Field(default_factory=now)
    processed_at: datetime | None = None
    posted_at: datetime | None = None
    invoice_norm: str = Field(default="", index=True)
    npwp_norm: str = ""
    confidence: str = "0"
    pages: list = J(list)
    extraction: dict = J(dict)
    overrides: dict = J(dict)  # {field: value} dan "progres_disetujui"
    calc_claim: dict = J(dict)
    calc_verified: dict = J(dict)
    anomalies: list = J(list)
    needs_cfo: bool = False
    erp_ref: str | None = None
    telemetry: list = J(list)
    error: str | None = None


class Unit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spv_id: str = Field(index=True)
    code: str
    buyer: str
    va: str = Field(index=True)
    phone: str = ""
    email: str = ""


class Installment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    unit_id: int = Field(index=True)
    seq: int
    due: date
    amount: int
    paid: int = 0


class Receipt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spv_id: str = Field(index=True)
    date: date
    sender: str
    bank: str
    amount: int
    memo: str
    ref: str = ""
    va: str = ""
    status: str = "UNALLOCATED"  # RECOMMENDED | MANUAL_REVIEW | ALLOCATED
    dup_flag: bool = False
    candidates: list = J(list)
    unit_id: int | None = None
    allocation: dict = J(dict)
    waiver: dict = J(dict)  # {reason, justification, by}
    penalty_status: str = ""  # "" | DITAGIH | WAIVED | MENUNGGU_CFO
    erp_ref: str | None = None
    uploaded_at: datetime = Field(default_factory=now)
    allocated_at: datetime | None = None


class JournalBatch(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spv_id: str
    source: str  # AP | AR
    source_id: int
    lines: list = J(list)
    erp_ref: str | None = None
    created_at: datetime = Field(default_factory=now)


class Outbox(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    receipt_id: int
    channel: str  # WHATSAPP | EMAIL
    to: str
    body: str
    attachment: str = ""
    created_at: datetime = Field(default_factory=now)


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=now)
    actor: str
    role: str
    spv_id: str
    action: str
    entity: str
    entity_id: int
    before: dict = J(dict)
    after: dict = J(dict)
    reason: str = ""
    prev_hash: str = ""
    hash: str = ""
