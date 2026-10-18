"""Cermin jejak audit & batch jurnal ERP ke Firestore (aktif bila FIRESTORE_ENABLED=1).

Fire-and-forget: tulis di thread terpisah, gagal hanya dicatat di log. SQLite tetap sumber kebenaran,
jadi aplikasi tidak pernah melambat atau rusak karena Firestore.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone

log = logging.getLogger("omniaudit.firestore")
STATS = {"written": 0, "failed": 0, "last_error": ""}
_client = None
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("FIRESTORE_ENABLED") == "1"


def _db():
    global _client
    with _lock:
        if _client is None:
            from google.cloud import firestore
            _client = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None)
        return _client


def _write(collection: str, doc_id: str | None, data: dict):
    try:
        col = _db().collection(collection)
        (col.document(doc_id) if doc_id else col.document()).set(data)
        STATS["written"] += 1
    except Exception as e:  # noqa: BLE001 - Firestore mati tidak boleh mengganggu alur audit
        STATS["failed"] += 1
        STATS["last_error"] = str(e)[:200]
        log.warning("Firestore mirror %s gagal: %s", collection, e)


def mirror(collection: str, data: dict, doc_id: str | None = None):
    # ponytail: dicerminkan sebelum commit SQLite; transaksi yang di-rollback bisa meninggalkan dokumen yatim
    if not enabled():
        return
    doc = json.loads(json.dumps(data, default=str))  # Decimal/datetime → tipe yang diterima Firestore
    doc["mirrored_at"] = datetime.now(timezone.utc).isoformat()
    threading.Thread(target=_write, args=(collection, doc_id, doc), daemon=True).start()


def journal(batch, actor: str):
    mirror("erp_journals", {"spv_id": batch.spv_id, "source": batch.source, "source_id": batch.source_id,
                            "erp_ref": batch.erp_ref, "lines": batch.lines, "posted_by": actor})


def status() -> dict:
    return {"enabled": enabled(), **STATS}
