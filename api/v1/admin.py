from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from typing import Dict, Optional
from services.auth import require_admin, TokenData
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db.models import AuditLog
from db.session import get_db
import uuid
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])


class WeightUpdateRequest(BaseModel):
    weights: Dict[str, float]
    apply_to: str = "institution"

    @validator("weights")
    def weights_must_be_valid(cls, v):
        for k, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Weight for {k} must be between 0.0 and 1.0")
        return v


class ConfigResponse(BaseModel):
    modules: list
    weights: dict
    institution_id: Optional[str]


@router.put("/weights")
async def update_weights(
    req: WeightUpdateRequest,
    current_user: TokenData = Depends(require_admin),
):
    from api.main import registry

    institution_id = current_user.institution_id if req.apply_to == "institution" else None
    await registry.set_weights(req.weights, institution_id=institution_id)

    total = sum(req.weights.values())
    normalized_ok = abs(total - 1.0) < 0.05 or abs(total) < 0.001

    # Log action
    return {
        "updated": True,
        "effective_at": datetime.utcnow().isoformat(),
        "weights": req.weights,
        "sum": round(total, 4),
        "validation": "weights_sum_to_1.0" if normalized_ok else "weights_do_not_sum_to_1.0",
        "institution_id": institution_id,
    }


@router.get("/config", response_model=ConfigResponse)
async def get_config(current_user: TokenData = Depends(require_admin)):
    from api.main import registry

    modules = registry.list_modules()
    weights = await registry.get_weights(institution_id=current_user.institution_id)

    active_modules = []
    for m in modules:
        enabled = await registry.is_enabled(m["module_id"])
        active_modules.append({**m, "enabled": enabled})

    return ConfigResponse(
        modules=active_modules,
        weights=weights,
        institution_id=current_user.institution_id,
    )


@router.get("/audit-log")
async def get_audit_log(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    result = await db.execute(
        select(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return {
        "logs": [
            {
                "id": l.id,
                "actor_id": l.actor_id,
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "details": l.details,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ]
    }


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    from sqlalchemy import func
    from db.models import Submission, IntegrityReport

    # Count by status
    status_result = await db.execute(
        select(Submission.status, func.count(Submission.id))
        .group_by(Submission.status)
    )
    status_counts = dict(status_result.all())

    # Count by risk level
    risk_result = await db.execute(
        select(IntegrityReport.risk_level, func.count(IntegrityReport.id))
        .group_by(IntegrityReport.risk_level)
    )
    risk_counts = dict(risk_result.all())

    # Average score
    avg_result = await db.execute(
        select(func.avg(IntegrityReport.integrity_score))
    )
    avg_score = avg_result.scalar()

    return {
        "submissions": {
            "total": sum(status_counts.values()),
            "by_status": status_counts,
        },
        "reports": {
            "by_risk": risk_counts,
            "average_score": round(float(avg_score or 0), 4),
        },
    }
