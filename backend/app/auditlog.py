"""Jejak Audit append-only dengan hash chain (FR-41)."""
import hashlib
import json

from sqlmodel import Session, select

from app.models import AuditLog, now


def _digest(prev: str, e: AuditLog) -> str:
    body = json.dumps([prev, e.ts.isoformat(), e.actor, e.role, e.spv_id, e.action, e.entity, e.entity_id,
                       e.before, e.after, e.reason], sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def record(s: Session, *, actor: str, role: str, spv_id: str, action: str, entity: str, entity_id: int,
           before: dict | None = None, after: dict | None = None, reason: str = "") -> AuditLog:
    last = s.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    e = AuditLog(ts=now(), actor=actor, role=role, spv_id=spv_id, action=action, entity=entity,
                 entity_id=entity_id, before=before or {}, after=after or {}, reason=reason,
                 prev_hash=last.hash if last else "GENESIS")
    e.hash = _digest(e.prev_hash, e)
    s.add(e)
    s.flush()
    return e


def verify(s: Session) -> dict:
    prev = "GENESIS"
    rows = s.exec(select(AuditLog).order_by(AuditLog.id)).all()
    for e in rows:
        if e.prev_hash != prev or _digest(prev, e) != e.hash:
            return {"ok": False, "broken_at": e.id, "checked": len(rows)}
        prev = e.hash
    return {"ok": True, "broken_at": None, "checked": len(rows)}
