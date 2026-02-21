import asyncio
from typing import List, Optional, Dict
from core.registry import ModuleRegistry
from core.aggregator import RiskAggregator, AggregatedResult
from core.events import EventEmitter
from modules.base import ModuleResult
from core.config import settings
import structlog

logger = structlog.get_logger()


class IntegrityController:
    def __init__(
        self,
        registry: ModuleRegistry,
        aggregator: RiskAggregator,
        emitter: EventEmitter,
    ):
        self.registry = registry
        self.aggregator = aggregator
        self.emitter = emitter

    async def run(
        self,
        submission_id: str,
        text: str,
        metadata: dict,
        requested_modules: Optional[List[str]] = None,
        institution_id: str = None,
    ) -> AggregatedResult:
        logger.info(
            "controller.run_started",
            submission_id=submission_id,
            word_count=len(text.split()),
        )

        # Emit: analysis started
        await self.emitter.emit(submission_id, {
            "type": "analysis_started",
            "submission_id": submission_id,
        })

        # Resolve active modules
        active_modules = await self.registry.get_active_modules(
            requested=requested_modules,
            institution_id=institution_id,
        )

        if not active_modules:
            logger.warning("controller.no_active_modules", submission_id=submission_id)
            await self.emitter.emit(submission_id, {
                "type": "completed",
                "error": "No active modules",
            })
            return self.aggregator.aggregate({}, {})

        # Launch all modules in parallel
        tasks = {
            m.module_id: asyncio.create_task(
                self._run_module_safe(submission_id, m, text, metadata)
            )
            for m in active_modules
        }

        results: Dict[str, Optional[ModuleResult]] = {}

        # Collect results and emit partial updates
        for module_id, task in tasks.items():
            result = await task
            results[module_id] = result

            await self.emitter.emit(submission_id, {
                "type": "module_complete",
                "module_id": module_id,
                "score": result.score if result else None,
                "confidence": result.confidence if result else None,
                "status": "error" if (result and result.error) else "done",
                "processing_ms": result.processing_ms if result else 0,
            })

        # Aggregate
        weights = await self.registry.get_weights(institution_id=institution_id)
        final = self.aggregator.aggregate(results, weights)

        # Emit: completed
        await self.emitter.emit(submission_id, {
            "type": "completed",
            "submission_id": submission_id,
            "integrity_score": final.integrity_score,
            "risk_level": final.risk_level,
        })

        logger.info(
            "controller.run_completed",
            submission_id=submission_id,
            score=final.integrity_score,
            risk=final.risk_level,
        )

        return final

    async def _run_module_safe(
        self,
        submission_id: str,
        module,
        text: str,
        metadata: dict,
    ) -> Optional[ModuleResult]:
        try:
            result = await asyncio.wait_for(
                module.analyze(text, metadata),
                timeout=settings.MODULE_TIMEOUT_SECONDS,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(
                "controller.module_timeout",
                module=module.module_id,
                submission_id=submission_id,
            )
            return module._make_error_result(
                f"Module timed out after {settings.MODULE_TIMEOUT_SECONDS}s"
            )
        except Exception as e:
            logger.error(
                "controller.module_error",
                module=module.module_id,
                error=str(e),
            )
            return module._make_error_result(str(e))
