import json
from typing import List, Optional, Dict
from modules.base import BaseModule
from core.config import settings
import structlog

logger = structlog.get_logger()


class ModuleRegistry:
    def __init__(self, redis_client, modules: List[BaseModule]):
        self._modules: Dict[str, BaseModule] = {m.module_id: m for m in modules}
        self._redis = redis_client
        self._default_weights = {m.module_id: m.default_weight for m in modules}

    async def initialize(self):
        """Seed Redis with defaults if not already set."""
        for module_id, module in self._modules.items():
            enabled_key = f"module:enabled:{module_id}"
            val = await self._redis.get(enabled_key)
            if val is None:
                # Default: all enabled except proctoring
                default = "0" if module_id == "proctoring" else "1"
                await self._redis.set(enabled_key, default)

        # Seed weights if not set
        weights_key = "module:weights"
        raw = await self._redis.get(weights_key)
        if raw is None:
            await self._redis.set(
                weights_key,
                json.dumps(self._default_weights)
            )
        logger.info("module_registry.initialized", modules=list(self._modules.keys()))

    async def is_enabled(self, module_id: str) -> bool:
        val = await self._redis.get(f"module:enabled:{module_id}")
        return val == b"1"

    async def toggle(self, module_id: str, enabled: bool, institution_id: str = None) -> bool:
        if module_id not in self._modules:
            return False
        key = f"module:enabled:{module_id}"
        if institution_id:
            key = f"module:enabled:{institution_id}:{module_id}"
        await self._redis.set(key, "1" if enabled else "0")
        logger.info("module_registry.toggled", module=module_id, enabled=enabled)
        return True

    async def get_active_modules(
        self,
        requested: Optional[List[str]] = None,
        institution_id: str = None,
    ) -> List[BaseModule]:
        target_ids = requested or list(self._modules.keys())
        active = []
        for mid in target_ids:
            if mid not in self._modules:
                continue
            # Check institution-specific setting first, then global
            if institution_id:
                inst_key = f"module:enabled:{institution_id}:{mid}"
                val = await self._redis.get(inst_key)
                if val is not None:
                    if val == b"1":
                        active.append(self._modules[mid])
                    continue
            # Fall back to global
            if await self.is_enabled(mid):
                active.append(self._modules[mid])
        return active

    async def get_weights(self, institution_id: str = None) -> Dict[str, float]:
        key = f"module:weights:{institution_id}" if institution_id else "module:weights"
        raw = await self._redis.get(key)
        if raw:
            return json.loads(raw)
        return self._default_weights.copy()

    async def set_weights(
        self,
        weights: Dict[str, float],
        institution_id: str = None,
    ) -> bool:
        key = f"module:weights:{institution_id}" if institution_id else "module:weights"
        await self._redis.set(key, json.dumps(weights))
        logger.info("module_registry.weights_updated", weights=weights)
        return True

    def list_modules(self) -> List[dict]:
        return [
            {
                "module_id": m.module_id,
                "version": m.version,
                "default_weight": m.default_weight,
                "healthy": m.is_healthy,
            }
            for m in self._modules.values()
        ]

    def get_module(self, module_id: str) -> Optional[BaseModule]:
        return self._modules.get(module_id)
