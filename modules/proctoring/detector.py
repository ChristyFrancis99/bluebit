import time
from typing import Optional, List
from modules.base import BaseModule, ModuleResult
import structlog

logger = structlog.get_logger()


class ProctoringModule(BaseModule):
    """
    Optional proctoring module.
    Analyzes submission behavioral metadata (timing, focus events, paste activity).
    Also analyzes video proctoring data (face detection, multiple faces, environment conditions).
    """
    module_id = "proctoring"
    version = "1.1.0"
    default_weight = 0.00  # Disabled by default in scoring

    @property
    def is_healthy(self) -> bool:
        return True

    async def analyze(self, text: str, metadata: dict) -> ModuleResult:
        t0 = time.monotonic_ns()

        try:
            # Extract behavioral signals from metadata
            session_data = metadata.get("session", {})
            
            # Extract video proctoring signals
            video_data = metadata.get("video_proctoring", {})

            # Behavioral signals (browser-based)
            paste_events = session_data.get("paste_events", 0)
            tab_switches = session_data.get("tab_switches", 0)
            idle_periods = session_data.get("idle_periods", [])
            typing_speed_wpm = session_data.get("typing_speed_wpm", None)
            session_duration_min = session_data.get("duration_minutes", None)
            focus_lost_count = session_data.get("focus_lost_count", 0)

            flags = []
            score = 0.0

            # === Browser-based behavioral analysis ===
            
            # Paste activity (large paste = suspicious)
            if paste_events > 3:
                flags.append(f"High paste activity: {paste_events} events")
                score += min(paste_events / 10.0, 0.3)

            # Tab switching
            if tab_switches > 5:
                flags.append(f"Frequent tab switching: {tab_switches}")
                score += min(tab_switches / 20.0, 0.15)

            # Focus loss
            if focus_lost_count > 3:
                flags.append(f"Lost focus {focus_lost_count} times")
                score += min(focus_lost_count / 10.0, 0.15)

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
                        score += 0.15

            # Long idle then sudden completion
            if idle_periods:
                long_idles = [p for p in idle_periods if p > 300]  # >5 min
                if long_idles:
                    flags.append(f"{len(long_idles)} long idle periods detected")
                    score += min(len(long_idles) / 5.0, 0.15)

            # === Video proctoring analysis ===
            video_score, video_flags, video_evidence = self._analyze_video_proctoring(video_data)
            score += video_score
            flags.extend(video_flags)

            # Calculate final score and confidence
            score = min(score, 1.0)
            
            # Confidence calculation
            browser_signals = paste_events > 0 or tab_switches > 0 or focus_lost_count > 0
            video_signals = video_data.get("is_active", False)
            
            if video_signals and browser_signals:
                confidence = 0.85
            elif video_signals:
                confidence = 0.80
            elif browser_signals:
                confidence = 0.70
            else:
                confidence = 0.30

            return ModuleResult(
                module_id=self.module_id,
                score=round(score, 4),
                confidence=confidence,
                evidence={
                    "flags": flags,
                    # Browser signals
                    "paste_events": paste_events,
                    "tab_switches": tab_switches,
                    "focus_lost_count": focus_lost_count,
                    "typing_speed_wpm": typing_speed_wpm,
                    "session_duration_min": session_duration_min,
                    "long_idle_count": len([p for p in idle_periods if p > 300]),
                    "behavioral_signals_available": bool(session_data),
                    # Video proctoring
                    "video_proctoring": video_evidence,
                },
                processing_ms=self._elapsed_ms(t0),
            )

        except Exception as e:
            logger.error("proctoring.analyze_failed", error=str(e))
            return self._make_error_result(str(e), self._elapsed_ms(t0))

    def _analyze_video_proctoring(self, video_data: dict) -> tuple:
        """
        Analyze video proctoring data and return score, flags, and evidence.
        
        Returns:
            tuple: (score, flags, evidence)
        """
        flags = []
        score = 0.0
        
        if not video_data or not video_data.get("is_active", False):
            return score, flags, {"is_active": False}
        
        evidence = {
            "is_active": True,
            "session_id": video_data.get("session_id"),
            "total_duration_seconds": video_data.get("total_duration_seconds", 0),
        }
        
        # Face detection metrics
        face_detected_count = video_data.get("face_detected_count", 0)
        face_lost_count = video_data.get("face_lost_count", 0)
        multiple_faces_count = video_data.get("multiple_faces_detected_count", 0)
        no_face_duration = video_data.get("no_face_duration_seconds", 0)
        
        evidence["face_detected_count"] = face_detected_count
        evidence["face_lost_count"] = face_lost_count
        evidence["multiple_faces_count"] = multiple_faces_count
        evidence["no_face_duration_seconds"] = no_face_duration
        
        # Environment metrics
        low_light_count = video_data.get("low_light_count", 0)
        device_change_count = video_data.get("device_change_count", 0)
        screen_capture = video_data.get("screen_capture_detected", False)
        
        evidence["low_light_count"] = low_light_count
        evidence["device_change_count"] = device_change_count
        evidence["screen_capture_detected"] = screen_capture
        
        # Calculate risk scores for each violation
        
        # Face lost too many times
        if face_lost_count > 10:
            flags.append(f"Face lost {face_lost_count} times during session")
            score += min(face_lost_count / 30.0, 0.25)
        elif face_lost_count > 5:
            flags.append(f"Face lost {face_lost_count} times")
            score += min(face_lost_count / 25.0, 0.15)
            
        # Multiple faces detected (possible cheating)
        if multiple_faces_count > 0:
            flags.append(f"Multiple faces detected {multiple_faces_count} times")
            score += min(multiple_faces_count / 3.0, 0.30)
            
        # No face for extended period
        if no_face_duration > 120:  # 2 minutes
            flags.append(f"Away from camera for {no_face_duration:.0f} seconds")
            score += min(no_face_duration / 300.0, 0.25)
        elif no_face_duration > 30:
            flags.append(f"Away from camera for {no_face_duration:.0f} seconds")
            score += min(no_face_duration / 150.0, 0.15)
            
        # Low light conditions
        if low_light_count > 5:
            flags.append(f"Low light conditions detected {low_light_count} times")
            score += min(low_light_count / 20.0, 0.15)
            
        # Device/camera change
        if device_change_count > 0:
            flags.append(f"Camera or device changed {device_change_count} times")
            score += min(device_change_count / 2.0, 0.20)
            
        # Screen capture detected
        if screen_capture:
            flags.append("Screen capture or recording detected")
            score += 0.20
            
        # Short session relative to submission length
        total_duration = video_data.get("total_duration_seconds", 0)
        if total_duration < 60 and total_duration > 0:
            flags.append(f"Very short video session: {total_duration:.0f} seconds")
            score += 0.15
            
        return score, flags, evidence
