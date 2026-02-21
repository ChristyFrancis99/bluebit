from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.auth import get_current_user, require_admin, TokenData

router = APIRouter(prefix="/modules", tags=["modules"])


class ToggleRequest(BaseModel):
    enabled: bool


class WeightUpdateRequest(BaseModel):
    weights: dict
    apply_to: str = "institution"  # institution | global


@router.get("")
async def list_modules(current_user: TokenData = Depends(get_current_user)):
    from api.main import registry

    modules = registry.list_modules()
    result = []
    for m in modules:
        enabled = await registry.is_enabled(m["module_id"])
        result.append({**m, "enabled": enabled})
    return {"modules": result}


@router.put("/{module_id}/toggle")
async def toggle_module(
    module_id: str,
    req: ToggleRequest,
    current_user: TokenData = Depends(require_admin),
):
    from api.main import registry

    success = await registry.toggle(
        module_id,
        req.enabled,
        institution_id=current_user.institution_id,
    )
    if not success:
        raise HTTPException(404, f"Module '{module_id}' not found")

    return {
        "module_id": module_id,
        "enabled": req.enabled,
        "effective_immediately": True,
        "institution_id": current_user.institution_id,
    }


@router.get("/{module_id}/health")
async def module_health(module_id: str, current_user: TokenData = Depends(get_current_user)):
    from api.main import registry

    mod = registry.get_module(module_id)
    if not mod:
        raise HTTPException(404, f"Module '{module_id}' not found")

    return {
        "module_id": module_id,
        "healthy": mod.is_healthy,
        "version": mod.version,
    }
