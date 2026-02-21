from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Optional
import time


class ModuleResult(BaseModel):
    module_id: str
    score: float          # 0.0 - 1.0 (higher = more suspicious)
    confidence: float     # 0.0 - 1.0
    evidence: dict        # Module-specific evidence payload
    metadata: dict = {}
    processing_ms: int
    error: Optional[str] = None


class ErrorResult(ModuleResult):
    """Returned when a module fails or times out."""
    pass


class BaseModule(ABC):
    module_id: str = "base"
    version: str = "1.0.0"
    default_weight: float = 1.0

    @abstractmethod
    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        """Core analysis logic. Must be stateless."""
        ...

    @property
    def is_healthy(self) -> bool:
        """Health check for module availability."""
        return True

    async def warmup(self) -> None:
        """Optional: preload models at startup."""
        pass

    def _make_error_result(self, error: str, elapsed_ms: int = 0) -> ModuleResult:
        return ModuleResult(
            module_id=self.module_id,
            score=0.0,
            confidence=0.0,
            evidence={"error": error},
            processing_ms=elapsed_ms,
            error=error,
        )

    def _elapsed_ms(self, t0_ns: int) -> int:
        return (time.monotonic_ns() - t0_ns) // 1_000_000
