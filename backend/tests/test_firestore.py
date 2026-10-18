import threading
import time

from app import auditlog, firestore_sink
from app.db import init_db, session
from app.models import JournalBatch


class FakeDb:
    def __init__(self, fail=False):
        self.docs, self.fail = {}, fail

    def collection(self, name):
        db = self

        class Doc:
            def __init__(self, i):
                self.i = i

            def set(self, data):
                if db.fail:
                    raise RuntimeError("Firestore down")
                db.docs[(name, self.i or f"auto{len(db.docs)}")] = data

        class Col:
            def document(self, i=None):
                return Doc(i)

        return Col()


def _settle():
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(timeout=5)
    time.sleep(0.05)


def test_audit_dan_jurnal_dicerminkan_ke_firestore(monkeypatch):
    fake = FakeDb()
    monkeypatch.setenv("FIRESTORE_ENABLED", "1")
    monkeypatch.setattr(firestore_sink, "_client", fake)
    init_db()
    with session() as s:
        e = auditlog.record(s, actor="dewi", role="AP", spv_id="SLO1", action="POST_ERP", entity="termin",
                            entity_id=1, after={"net_payable": "234562500.00"})
        firestore_sink.journal(JournalBatch(spv_id="SLO1", source="AP", source_id=1, erp_ref="ERP-1",
                                            lines=[{"side": "D", "account": "Hutang", "amount": 1}]), "dewi")
        s.rollback()
    _settle()
    assert fake.docs[("audit_log", e.hash)]["action"] == "POST_ERP"
    assert any(k[0] == "erp_journals" and v["erp_ref"] == "ERP-1" for k, v in fake.docs.items())


def test_firestore_gagal_tidak_mengganggu_audit(monkeypatch):
    monkeypatch.setenv("FIRESTORE_ENABLED", "1")
    monkeypatch.setattr(firestore_sink, "_client", FakeDb(fail=True))
    before = firestore_sink.STATS["failed"]
    init_db()
    with session() as s:
        e = auditlog.record(s, actor="dewi", role="AP", spv_id="SLO1", action="FLAG", entity="termin", entity_id=1)
        s.rollback()
    _settle()
    assert e.hash and firestore_sink.STATS["failed"] == before + 1


def test_mati_bila_tidak_diaktifkan(monkeypatch):
    monkeypatch.delenv("FIRESTORE_ENABLED", raising=False)
    fake = FakeDb()
    monkeypatch.setattr(firestore_sink, "_client", fake)
    firestore_sink.mirror("audit_log", {"x": 1})
    _settle()
    assert fake.docs == {}
