"""
Video Proctoring Service
Provides face detection, liveness detection, and anomaly detection for proctoring.
"""
import io
import time
import base64
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger()


@dataclass
class FaceDetectionResult:
    """Result of face detection analysis."""
    face_count: int = 0
    multiple_faces_detected: bool = False
    no_face_detected: bool = False
    face_locations: List[Dict] = field(default_factory=list)
    face_encodings: List[Any] = field(default_factory=list)
    processing_ms: int = 0


@dataclass
class LivenessResult:
    """Result of liveness detection analysis."""
    is_live: bool = True
    blink_detected: bool = False
    movement_detected: bool = False
    blink_count: int = 0
    avg_eye_aspect_ratio: float = 0.0
    face_movement_score: float = 0.0
    flags: List[str] = field(default_factory=list)
    processing_ms: int = 0


@dataclass
class ProctoringAnalysisResult:
    """Complete proctoring analysis result."""
    face_detection: FaceDetectionResult
    liveness: LivenessResult
    anomalies: List[str] = field(default_factory=list)
    overall_risk_score: float = 0.0
    flags: List[str] = field(default_factory=list)
    evidence: Dict = field(default_factory=dict)
    processing_ms: int = 0


class VideoProcessor:
    """
    Video processing service for proctoring.
    Handles face detection, liveness detection, and anomaly detection.
    """
    
    def __init__(self):
        self._face_recognition_model = None
        self._initialized = False
        self._blink_detection_threshold = 0.2
        self._min_blinks_required = 1
        
    async def initialize(self) -> bool:
        """Initialize the video processor and load models."""
        if self._initialized:
            return True
            
        try:
            import face_recognition
            self._face_recognition_model = face_recognition
            self._initialized = True
            logger.info("video_processor.initialized", status="success")
            return True
        except ImportError as e:
            logger.error("video_processor.init_failed", error=str(e))
            return False
        except Exception as e:
            logger.error("video_processor.init_error", error=str(e))
            return False
    
    @property
    def is_healthy(self) -> bool:
        """Check if the video processor is healthy."""
        return self._initialized
    
    async def detect_faces(self, image_data: bytes) -> FaceDetectionResult:
        """
        Detect faces in an image.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            FaceDetectionResult with face detection details
        """
        t0 = time.monotonic_ns()
        
        try:
            if not self._initialized:
                await self.initialize()
            
            # Load image from bytes
            image = self._load_image(image_data)
            if image is None:
                return FaceDetectionResult(
                    processing_ms=self._elapsed_ms(t0)
                )
            
            # Convert to numpy array for face_recognition
            image_array = np.array(image)
            
            # Detect faces
            face_locations = self._face_recognition_model.face_locations(image_array)
            face_encodings = self._face_recognition_model.face_encodings(image_array, face_locations)
            
            face_count = len(face_locations)
            
            # Convert face locations to serializable format
            face_locs = []
            for i, loc in enumerate(face_locations):
                face_locs.append({
                    "top": int(loc[0]),
                    "right": int(loc[1]),
                    "bottom": int(loc[2]),
                    "left": int(loc[3])
                })
            
            result = FaceDetectionResult(
                face_count=face_count,
                multiple_faces_detected=face_count > 1,
                no_face_detected=face_count == 0,
                face_locations=face_locs,
                face_encodings=[],  # Don't serialize encodings
                processing_ms=self._elapsed_ms(t0)
            )
            
            logger.debug("face_detection.completed", 
                        face_count=face_count,
                        processing_ms=result.processing_ms)
            
            return result
            
        except Exception as e:
            logger.error("face_detection.failed", error=str(e))
            return FaceDetectionResult(processing_ms=self._elapsed_ms(t0))
    
    async def detect_liveness(self, frame_sequence: List[bytes]) -> LivenessResult:
        """
        Detect liveness from a sequence of video frames.
        
        Analyzes eye blink patterns and facial movements to determine
        if the person is live (not a photo/video spoof).
        
        Args:
            frame_sequence: List of image bytes (frames)
            
        Returns:
            LivenessResult with liveness detection details
        """
        t0 = time.monotonic_ns()
        
        try:
            if not self._initialized:
                await self.initialize()
            
            if len(frame_sequence) < 3:
                return LivenessResult(
                    flags=["insufficient_frames"],
                    processing_ms=self._elapsed_ms(t0)
                )
            
            blink_count = 0
            movement_scores = []
            eye_ar_history = []
            
            prev_face_locations = None
            prev_face_encodings = None
            
            for frame_data in frame_sequence:
                image = self._load_image(frame_data)
                if image is None:
                    continue
                    
                image_array = np.array(image)
                
                # Get face locations and encodings
                face_locations = self._face_recognition_model.face_locations(image_array)
                
                if face_locations:
                    face_encodings = self._face_recognition_model.face_encodings(
                        image_array, face_locations
                    )
                    
                    # Calculate movement
                    if prev_face_locations and prev_face_encodings:
                        movement = self._calculate_movement(
                            prev_face_locations, face_locations,
                            prev_face_encodings, face_encodings
                        )
                        movement_scores.append(movement)
                    
                    # Detect blinks (simplified - real implementation would use eye landmarks)
                    ear = self._estimate_eye_aspect_ratio(image_array, face_locations[0])
                    if ear > 0:
                        eye_ar_history.append(ear)
                    
                    prev_face_locations = face_locations
                    prev_face_encodings = face_encodings
            
            # Analyze blink pattern
            if len(eye_ar_history) >= 3:
                blink_count = self._detect_blinks(eye_ar_history)
            
            # Analyze movement
            avg_movement = sum(movement_scores) / len(movement_scores) if movement_scores else 0
            movement_detected = avg_movement > 0.1
            
            # Determine liveness
            is_live = True
            flags = []
            
            if blink_count < self._min_blinks_required:
                flags.append("low_blink_count")
                is_live = False
                
            if not movement_detected:
                flags.append("no_movement_detected")
                is_live = False
            
            # Check for static image (photo attack)
            if len(movement_scores) > 0 and max(movement_scores) < 0.05:
                flags.append("possible_static_image")
                is_live = False
            
            avg_ear = sum(eye_ar_history) / len(eye_ar_history) if eye_ar_history else 0
            
            result = LivenessResult(
                is_live=is_live,
                blink_detected=blink_count > 0,
                movement_detected=movement_detected,
                blink_count=blink_count,
                avg_eye_aspect_ratio=round(avg_ear, 4),
                face_movement_score=round(avg_movement, 4),
                flags=flags,
                processing_ms=self._elapsed_ms(t0)
            )
            
            logger.debug("liveness_detection.completed",
                        is_live=is_live,
                        blink_count=blink_count,
                        processing_ms=result.processing_ms)
            
            return result
            
        except Exception as e:
            logger.error("liveness_detection.failed", error=str(e))
            return LivenessResult(processing_ms=self._elapsed_ms(t0))
    
    async def analyze_frames(self, frames: List[bytes]) -> ProctoringAnalysisResult:
        """
        Complete proctoring analysis on a sequence of frames.
        
        Args:
            frames: List of video frame bytes
            
        Returns:
            Complete proctoring analysis result
        """
        t0 = time.monotonic_ns()
        
        # Analyze first frame for face detection
        face_result = FaceDetectionResult()
        if frames:
            face_result = await self.detect_faces(frames[0])
        
        # Analyze sequence for liveness
        liveness_result = await self.detect_liveness(frames)
        
        # Determine anomalies and flags
        anomalies = []
        flags = []
        
        if face_result.multiple_faces_detected:
            anomalies.append("multiple_faces_detected")
            flags.append("HIGH: Multiple faces in frame")
        
        if face_result.no_face_detected:
            anomalies.append("no_face_detected")
            flags.append("MEDIUM: No face detected in frame")
        
        if not liveness_result.is_live:
            anomalies.append("liveness_check_failed")
            flags.append(f"HIGH: Liveness check failed - {', '.join(liveness_result.flags)}")
        
        # Calculate risk score
        risk_score = 0.0
        
        if face_result.multiple_faces_detected:
            risk_score += 0.5
        
        if face_result.no_face_detected:
            risk_score += 0.3
        
        if not liveness_result.is_live:
            risk_score += 0.4
        
        risk_score = min(risk_score, 1.0)
        
        result = ProctoringAnalysisResult(
            face_detection=face_result,
            liveness=liveness_result,
            anomalies=anomalies,
            overall_risk_score=round(risk_score, 4),
            flags=flags,
            evidence={
                "frame_count": len(frames),
                "face_count": face_result.face_count,
                "liveness_flags": liveness_result.flags,
                "movement_score": liveness_result.face_movement_score,
                "blink_count": liveness_result.blink_count,
            },
            processing_ms=self._elapsed_ms(t0)
        )
        
        logger.info("proctoring_analysis.completed",
                  risk_score=risk_score,
                  flags_count=len(flags),
                  processing_ms=result.processing_ms)
        
        return result
    
    async def analyze_screenshot(self, image_data: bytes) -> Dict[str, Any]:
        """
        Analyze a screenshot for anomalies.
        
        Args:
            image_data: Screenshot bytes
            
        Returns:
            Analysis result dictionary
        """
        t0 = time.monotonic_ns()
        
        try:
            # Perform face detection
            face_result = await self.detect_faces(image_data)
            
            # Load image for additional analysis
            image = self._load_image(image_data)
            if image is None:
                return {"error": "Failed to load image", "processing_ms": self._elapsed_ms(t0)}
            
            # Analyze image quality
            quality_result = self._analyze_image_quality(image)
            
            # Build result
            result = {
                "face_detection": {
                    "face_count": face_result.face_count,
                    "multiple_faces": face_result.multiple_faces_detected,
                    "no_face": face_result.no_face_detected,
                },
                "image_quality": quality_result,
                "risk_flags": [],
                "processing_ms": self._elapsed_ms(t0)
            }
            
            # Add risk flags
            if face_result.multiple_faces_detected:
                result["risk_flags"].append("multiple_faces")
            
            if face_result.no_face_detected:
                result["risk_flags"].append("no_face")
            
            if not quality_result["is_acceptable"]:
                result["risk_flags"].append(f"quality_issues: {quality_result['issues']}")
            
            return result
            
        except Exception as e:
            logger.error("screenshot_analysis.failed", error=str(e))
            return {"error": str(e), "processing_ms": self._elapsed_ms(t0)}
    
    def _load_image(self, image_data: bytes) -> Optional[Image.Image]:
        """Load image from bytes."""
        try:
            return Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.error("image_load.failed", error=str(e))
            return None
    
    def _calculate_movement(
        self,
        prev_locations: List,
        curr_locations: List,
        prev_encodings: List,
        curr_encodings: List
    ) -> float:
        """Calculate facial movement score between frames."""
        if not prev_locations or not curr_locations:
            return 0.0
            
        # Calculate center movement
        prev_center = (
            (prev_locations[0][3] + prev_locations[0][1]) / 2,
            (prev_locations[0][0] + prev_locations[0][2]) / 2
        )
        curr_center = (
            (curr_locations[0][3] + curr_locations[0][1]) / 2,
            (curr_locations[0][0] + curr_locations[0][2]) / 2
        )
        
        # Normalize by image size (assuming typical webcam resolution)
        distance = ((curr_center[0] - prev_center[0])**2 + 
                   (curr_center[1] - prev_center[1])**2)**0.5 / 640.0
        
        return min(distance, 1.0)
    
    def _estimate_eye_aspect_ratio(self, image_array: np.ndarray, face_location: Tuple) -> float:
        """
        Estimate eye aspect ratio from face location.
        This is a simplified version - full implementation would use facial landmarks.
        """
        # Get face dimensions
        top, right, bottom, left = face_location
        face_height = bottom - top
        face_width = right - left
        
        # Estimate eye region (approximately 30% from top of face, centered)
        eye_region_height = face_height * 0.15
        eye_region_width = face_width * 0.25
        
        # Extract eye regions
        left_eye_y = int(top + face_height * 0.3)
        left_eye_x = int(left + face_width * 0.2)
        right_eye_y = int(top + face_height * 0.3)
        right_eye_x = int(left + face_width * 0.55)
        
        try:
            # Get eye regions
            left_eye = image_array[
                left_eye_y:int(left_eye_y + eye_region_height),
                left_eye_x:int(left_eye_x + eye_region_width)
            ]
            right_eye = image_array[
                right_eye_y:int(right_eye_y + eye_region_height),
                right_eye_x:int(right_eye_x + eye_region_width)
            ]
            
            if left_eye.size == 0 or right_eye.size == 0:
                return 0.0
            
            # Calculate aspect ratio based on edge density (simplified)
            # Closed eyes have different edge patterns than open eyes
            import cv2
            
            left_gray = cv2.cvtColor(left_eye, cv2.COLOR_RGB2GRAY)
            right_gray = cv2.cvtColor(right_eye, cv2.COLOR_RGB2GRAY)
            
            left_edges = cv2.Canny(left_gray, 50, 150)
            right_edges = cv2.Canny(right_gray, 50, 150)
            
            left_density = np.sum(left_edges > 0) / left_edges.size
            right_density = np.sum(right_edges > 0) / right_edges.size
            
            # Higher edge density suggests open eyes
            avg_density = (left_density + right_density) / 2
            
            # Map to EAR-like value (0.0 - 0.3 for closed, 0.2+ for open)
            ear_estimate = min(avg_density * 2, 0.35)
            
            return ear_estimate
            
        except Exception as e:
            logger.debug("eye_aspect_ratio.failed", error=str(e))
            return 0.0
    
    def _detect_blinks(self, eye_ar_history: List[float]) -> int:
        """Detect number of blinks from eye aspect ratio history."""
        if len(eye_ar_history) < 3:
            return 0
        
        blink_count = 0
        in_blink = False
        
        # Find local minima (potential blinks)
        for i in range(1, len(eye_ar_history) - 1):
            if (eye_ar_history[i] < eye_ar_history[i-1] and 
                eye_ar_history[i] < eye_ar_history[i+1] and
                eye_ar_history[i] < self._blink_detection_threshold):
                
                if not in_blink:
                    blink_count += 1
                    in_blink = True
            else:
                in_blink = False
        
        return blink_count
    
    def _analyze_image_quality(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze image quality for proctoring."""
        import cv2
        
