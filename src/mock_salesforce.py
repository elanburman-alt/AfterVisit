import json
import uuid
from datetime import datetime, timezone

from jsonschema import Draft7Validator

from .config import ACTIVITY_LOG, SCHEMAS_DIR

_SCHEMA = json.loads((SCHEMAS_DIR / "activity_note.schema.json").read_text(encoding="utf-8"))
_VALIDATOR = Draft7Validator(_SCHEMA)


def post_activity(note: dict) -> dict:
    errors = sorted(_VALIDATOR.iter_errors(note), key=lambda e: list(e.path))
    if errors:
        return {
            "status": "error",
            "errors": [{"path": list(e.path), "message": e.message} for e in errors],
        }
    ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(ACTIVITY_LOG.read_text(encoding="utf-8")) if ACTIVITY_LOG.exists() else []
    record = {
        "id": str(uuid.uuid4()),
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    log.append(record)
    ACTIVITY_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return {"id": record["id"], "status": "ok"}
