import time
from typing import Optional, List
from modules.base import BaseModule, ModuleResult
import structlog

logger = structlog.get_logger()


class ProctoringModule(BaseModule):
    """
    Optional proctoring module.
    Analyzes submission behavioral metadata (timing, focus events, paste activity).
    In a full deployment, integrates with webcam/screen recording analysis.
    """
    module_id = "proctoring"
    version = "1.0.0"
    default_weight = 0.00  # Disabled by default in scoring

    @property
    def is_healthy(self) -> bool:
        return True

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        try:
            # Extract behavioral signals from metadata
            session_data = metadata.get("session", {})

            # Behavioral signals
            paste_events = session_data.get("paste_events", 0)
            tab_switches = session_data.get("tab_switches", 0)
            idle_periods = session_data.get("idle_periods", [])
            typing_speed_wpm = session_data.get("typing_speed_wpm", None)
            session_duration_min = session_data.get("duration_minutes", None)
            focus_lost_count = session_data.get("focus_lost_count", 0)

            flags = []
            score = 0.0

            # Paste activity (large paste = suspicious)
            if paste_events > 3:
                flags.append(f"High paste activity: {paste_events} events")
                score += min(paste_events / 10.0, 0.4)

            # Tab switching
            if tab_switches > 5:
                flags.append(f"Frequent tab switching: {tab_switches}")
                score += min(tab_switches / 20.0, 0.2)

            # Focus loss
            if focus_lost_count > 3:
                flags.append(f"Lost focus {focus_lost_count} times")
                score += min(focus_lost_count / 10.0, 0.2)

            # Typing speed anomaly
            if typing_speed_wpm:
                word_count = len(text.split())
                if session_duration_min and session_duration_min > 0:
                    actual_wpm = word_count / session_duration_min
                    if actual_wpm > typing_speed_wpm * 1.5:
                        flags.append(
                            f"Typing speed anomaly: {actual_wpm:.0f} WPM actual vs "
                            f"{typing_speed_wpm} WPM baseline"
                        )
                        score += 0.2

            # Long idle then sudden completion
            if idle_periods:
                long_idles = [p for p in idle_periods if p > 300]  # >5 min
                if long_idles:
                    flags.append(f"{len(long_idles)} long idle periods detected")
                    score += min(len(long_idles) / 5.0, 0.2)

            score = min(score, 1.0)
            confidence = 0.70 if (paste_events > 0 or tab_switches > 0) else 0.30

            return ModuleResult(
                module_id=self.module_id,
                score=round(score, 4),
                confidence=confidence,
                evidence={
                    "flags": flags,
                    "paste_events": paste_events,
                    "tab_switches": tab_switches,
                    "focus_lost_count": focus_lost_count,
                    "typing_speed_wpm": typing_speed_wpm,
                    "session_duration_min": session_duration_min,
                    "long_idle_count": len([p for p in idle_periods if p > 300]),
                    "behavioral_signals_available": bool(session_data),
                },
                processing_ms=self._elapsed_ms(t0),
            )

        except Exception as e:
            logger.error("proctoring.analyze_failed", error=str(e))
            return self._make_error_result(str(e), self._elapsed_ms(t0))
