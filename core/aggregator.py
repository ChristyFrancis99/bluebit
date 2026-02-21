from dataclasses import dataclass, field
from typing import Dict, Optional
from modules.base import ModuleResult
import structlog

logger = structlog.get_logger()


@dataclass
class AggregatedResult:
    integrity_score: float        # 0.0 (clean) to 1.0 (high risk)
    risk_level: str               # LOW | MEDIUM | HIGH
    module_scores: Dict[str, float]
    confidence: float
    breakdown: Dict
    recommendation: str = ""
    flags: list = field(default_factory=list)


class RiskAggregator:
    THRESHOLDS = {"LOW": 0.35, "MEDIUM": 0.65}

    RECOMMENDATIONS = {
        "LOW": "Submission appears consistent with student's expected work.",
        "MEDIUM": "Review recommended. Some signals of integrity concern detected.",
        "HIGH": "Escalate for manual review. Multiple integrity flags detected.",
    }

    def aggregate(
        self,
        results: Dict[str, Optional[ModuleResult]],
        weights: Dict[str, float],
    ) -> AggregatedResult:
        total_weight = 0.0
        weighted_sum = 0.0
        breakdown = {}
        flags = []

        valid_results = {
            mid: r for mid, r in results.items()
            if r is not None and r.error is None
        }

        if not valid_results:
            return AggregatedResult(
                integrity_score=0.0,
                risk_level="LOW",
                module_scores={},
                confidence=0.0,
                breakdown={},
                recommendation="No modules produced results.",
            )

        for module_id, result in valid_results.items():
            w = weights.get(module_id, 1.0)
            if w == 0:
                continue

            weighted_sum += result.score * w
            total_weight += w

            contribution = result.score * w / max(total_weight, 1e-9)
            breakdown[module_id] = {
                "score": round(result.score, 4),
                "weight": w,
                "weighted_contribution": round(contribution, 4),
                "confidence": round(result.confidence, 4),
                "evidence": result.evidence,
                "processing_ms": result.processing_ms,
            }

            # Collect high-signal flags
            if result.score >= 0.65:
                flags.append({
                    "module": module_id,
                    "score": round(result.score, 4),
                    "severity": "HIGH" if result.score >= 0.80 else "MEDIUM",
                })

        score = weighted_sum / max(total_weight, 1e-9)
        score = round(min(max(score, 0.0), 1.0), 4)

        risk = self._categorize(score)

        confidences = [r.confidence for r in valid_results.values()]
        avg_confidence = round(sum(confidences) / max(len(confidences), 1), 4)

        # Recompute contributions with final total weight
        for mid in breakdown:
            w = weights.get(mid, 1.0)
            s = breakdown[mid]["score"]
            breakdown[mid]["weighted_contribution"] = round(
                (s * w) / max(total_weight, 1e-9), 4
            )

        return AggregatedResult(
            integrity_score=score,
            risk_level=risk,
            module_scores={
                mid: r.score for mid, r in valid_results.items()
            },
            confidence=avg_confidence,
            breakdown=breakdown,
            recommendation=self.RECOMMENDATIONS[risk],
            flags=flags,
        )

    def _categorize(self, score: float) -> str:
        if score < self.THRESHOLDS["LOW"]:
            return "LOW"
        elif score < self.THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        return "HIGH"
