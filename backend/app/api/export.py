import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import client_ip, require_admin
from app.db import get_db
from app.models import User
from app.models._common import utcnow
from app.services import audit
from app.services.export import build_export

router = APIRouter(prefix="/api/admin/export", tags=["admin: export"])


@router.get("")
def export(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> Response:
    payload = build_export(db)
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    audit.record(
        db, "export.download", user_id=admin.id,
        meta={"recordings": len(payload["recordings"]), "normalisation_version": payload["normalisation_version"]},
        ip_address=client_ip(request),
    )
    db.commit()
    filename = f"annotations-{utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
