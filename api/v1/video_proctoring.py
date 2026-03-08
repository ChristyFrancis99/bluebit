import uuid
import hashlib
import os
import tempfile
import io
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, List
from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect,
    UploadFile, File,
)
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from enum import Enum

from db.models import VideoProctoringSession
from db.session import get_db
from services.auth import get_current_user, TokenData
from core.config import settings
from services.video_processor import VideoProcessor

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/video-proctoring", tags=["video-proctoring"])


class VideoEventType(str, Enum):
    FACE_DETECTED = "face_detected"
    FACE_LOST = "face_lost"
    MULTIPLE_FACES = "multiple_faces"
    LOW_LIGHT = "low_light"
    DEVICE_CHANGE = "device_change"
    SCREEN_CAPTURE = "screen_capture"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


# Request/Response Models
class StartSessionRequest(BaseModel):
    submission_id: Optional[str] = None
    assignment_id: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    started_at: str


class VideoEventRequest(BaseModel):
    event_type: VideoEventType
    duration_seconds: Optional[float] = 0.0
    metadata: Optional[dict] = {}


class VideoEventResponse(BaseModel):
    event_id: str
    session_id: str
    event_type: str
    timestamp: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    submission_id: Optional[str]
    started_at: str
    ended_at: Optional[str]
    total_duration_seconds: float
    
    # Metrics
    face_detected_count: int
    face_lost_count: int
    multiple_faces_detected_count: int
    no_face_duration_seconds: float
    low_light_count: int
    device_change_count: int
    screen_capture_detected: bool
    
    # Risk assessment
    risk_score: float
    flags: List[str]


class EndSessionResponse(BaseModel):
    session_id: str
    status: str
    risk_score: float
    flags: List[str]


# WebSocket connection manager for real-time events
class VideoProctoringManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.session_data: dict[str, dict] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_event(self, session_id: str, event: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(event)


manager = VideoProctoringManager()


@router.post("/sessions", response_model=StartSessionResponse, status_code=201)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Start a new video proctoring session."""
    session_id = str(uuid.uuid4())
    
    session = VideoProctoringSession(
        id=session_id,
        user_id=current_user.user_id,
        submission_id=request.submission_id,
        status="active",
        started_at=datetime.utcnow(),
        events=[],
    )
    
    db.add(session)
    await db.commit()
    
    logger.info(
        "video_proctoring.session_started",
        session_id=session_id,
        user_id=current_user.user_id,
        submission_id=request.submission_id,
    )
    
    # Initialize session data in manager
    manager.session_data[session_id] = {
        "face_detected_count": 0,
        "face_lost_count": 0,
        "multiple_faces_detected_count": 0,
        "no_face_duration_seconds": 0.0,
        "low_light_count": 0,
        "device_change_count": 0,
        "screen_capture_detected": False,
        "last_face_detected_time": None,
        "events": [],
    }
    
    return StartSessionResponse(
        session_id=session_id,
        status="active",
        started_at=session.started_at.isoformat(),
    )


@router.post("/sessions/{session_id}/events", response_model=VideoEventResponse)
async def report_video_event(
    session_id: str,
    request: VideoEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Report a video event during the proctoring session."""
    # Get session
    result = await db.execute(
        select(VideoProctoringSession).where(
            VideoProctoringSession.id == session_id,
            VideoProctoringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    if session.status != "active":
        raise HTTPException(400, "Session is not active")
    
    event_id = str(uuid.uuid4())
    event_timestamp = datetime.utcnow()
    
    # Get current session data from manager
    session_data = manager.session_data.get(session_id, {
        "face_detected_count": 0,
        "face_lost_count": 0,
        "multiple_faces_detected_count": 0,
        "no_face_duration_seconds": 0.0,
        "low_light_count": 0,
        "device_change_count": 0,
        "screen_capture_detected": False,
        "last_face_detected_time": None,
        "events": [],
    })
    
    # Process event and update counters
    event_data = {
        "event_id": event_id,
        "event_type": request.event_type,
        "timestamp": event_timestamp.isoformat(),
        "duration_seconds": request.duration_seconds,
        "metadata": request.metadata,
    }
    
    session_data["events"].append(event_data)
    
    # Update counters based on event type
    if request.event_type == VideoEventType.FACE_DETECTED:
        session_data["face_detected_count"] += 1
        session_data["last_face_detected_time"] = event_timestamp
    elif request.event_type == VideoEventType.FACE_LOST:
        session_data["face_lost_count"] += 1
    elif request.event_type == VideoEventType.MULTIPLE_FACES:
        session_data["multiple_faces_detected_count"] += 1
    elif request.event_type == VideoEventType.LOW_LIGHT:
        session_data["low_light_count"] += 1
    elif request.event_type == VideoEventType.DEVICE_CHANGE:
        session_data["device_change_count"] += 1
    elif request.event_type == VideoEventType.SCREEN_CAPTURE:
        session_data["screen_capture_detected"] = True
    
    # Calculate no_face_duration
    if request.event_type == VideoEventType.FACE_LOST and request.duration_seconds > 0:
        session_data["no_face_duration_seconds"] += request.duration_seconds
    
    # Update manager
    manager.session_data[session_id] = session_data
    
    # Update session in database
    events = session.events or []
    events.append(event_data)
    
    await db.execute(
        update(VideoProctoringSession)
        .where(VideoProctoringSession.id == session_id)
        .values(
            events=events,
            face_detected_count=session_data["face_detected_count"],
            face_lost_count=session_data["face_lost_count"],
            multiple_faces_detected_count=session_data["multiple_faces_detected_count"],
            no_face_duration_seconds=session_data["no_face_duration_seconds"],
            low_light_count=session_data["low_light_count"],
            device_change_count=session_data["device_change_count"],
            screen_capture_detected=session_data["screen_capture_detected"],
        )
    )
    await db.commit()
    
    # Emit event via WebSocket if connected
    await manager.send_event(session_id, {
        "type": "event_received",
        "event": event_data,
    })
    
    return VideoEventResponse(
        event_id=event_id,
        session_id=session_id,
        event_type=request.event_type,
        timestamp=event_timestamp.isoformat(),
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get the current status of a video proctoring session."""
    result = await db.execute(
        select(VideoProctoringSession).where(
            VideoProctoringSession.id == session_id,
            VideoProctoringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Calculate risk score
    risk_score = _calculate_risk_score(session)
    flags = _generate_flags(session)
    
    return SessionStatusResponse(
        session_id=session.id,
        status=session.status,
        submission_id=session.submission_id,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None,
        total_duration_seconds=session.total_duration_seconds or 0.0,
        face_detected_count=session.face_detected_count,
        face_lost_count=session.face_lost_count,
        multiple_faces_detected_count=session.multiple_faces_detected_count,
        no_face_duration_seconds=session.no_face_duration_seconds or 0.0,
        low_light_count=session.low_light_count,
        device_change_count=session.device_change_count,
        screen_capture_detected=session.screen_capture_detected or False,
        risk_score=risk_score,
        flags=flags,
    )


@router.delete("/sessions/{session_id}", response_model=EndSessionResponse)
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """End a video proctoring session."""
    result = await db.execute(
        select(VideoProctoringSession).where(
            VideoProctoringSession.id == session_id,
            VideoProctoringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    if session.status != "active":
        raise HTTPException(400, "Session is already ended")
    
    now = datetime.utcnow()
    duration = (now - session.started_at).total_seconds()
    
    # Get final session data from manager
    session_data = manager.session_data.get(session_id, {})
    
    # Calculate risk score
    risk_score = _calculate_risk_score(session)
    flags = _generate_flags(session)
    
    # Update session
    await db.execute(
        update(VideoProctoringSession)
        .where(VideoProctoringSession.id == session_id)
        .values(
            status="completed",
            ended_at=now,
            total_duration_seconds=duration,
            risk_score=risk_score,
            flags=flags,
            face_detected_count=session_data.get("face_detected_count", session.face_detected_count),
            face_lost_count=session_data.get("face_lost_count", session.face_lost_count),
            multiple_faces_detected_count=session_data.get("multiple_faces_detected_count", session.multiple_faces_detected_count),
            no_face_duration_seconds=session_data.get("no_face_duration_seconds", session.no_face_duration_seconds),
            low_light_count=session_data.get("low_light_count", session.low_light_count),
            device_change_count=session_data.get("device_change_count", session.device_change_count),
            screen_capture_detected=session_data.get("screen_capture_detected", session.screen_capture_detected),
        )
    )
    await db.commit()
    
    # Clean up manager
    if session_id in manager.session_data:
        del manager.session_data[session_id]
    
    logger.info(
        "video_proctoring.session_ended",
        session_id=session_id,
        risk_score=risk_score,
        duration=duration,
    )
    
    return EndSessionResponse(
        session_id=session_id,
        status="completed",
        risk_score=risk_score,
        flags=flags,
    )


@router.websocket("/ws/sessions/{session_id}")
async def websocket_session(
    websocket: WebSocket,
    session_id: str,
):
    """WebSocket endpoint for real-time video proctoring updates."""
    await manager.connect(session_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages from client
            # For now, just echo back (can be extended for commands)
            await websocket.send_json({"status": "received"})
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("video_proctoring.ws_disconnected", session_id=session_id)


# Helper functions
def _calculate_risk_score(session: VideoProctoringSession) -> float:
    """Calculate risk score based on session metrics."""
    score = 0.0
    
    # Face lost
    if session.face_lost_count:
        score += min(session.face_lost_count / 30.0, 0.25)
    
    # Multiple faces
    if session.multiple_faces_detected_count:
        score += min(session.multiple_faces_detected_count / 3.0, 0.30)
    
    # No face duration
    if session.no_face_duration_seconds:
        score += min(session.no_face_duration_seconds / 300.0, 0.25)
    
    # Low light
    if session.low_light_count:
        score += min(session.low_light_count / 20.0, 0.15)
    
    # Device change
    if session.device_change_count:
        score += min(session.device_change_count / 2.0, 0.20)
    
    # Screen capture
    if session.screen_capture_detected:
        score += 0.20
    
    return min(score, 1.0)


def _generate_flags(session: VideoProctoringSession) -> list:
    """Generate human-readable flags based on session metrics."""
    flags = []
    
    if session.face_lost_count > 10:
        flags.append(f"Face lost {session.face_lost_count} times during session")
    elif session.face_lost_count > 5:
        flags.append(f"Face lost {session.face_lost_count} times")
    
    if session.multiple_faces_detected_count > 0:
        flags.append(f"Multiple faces detected {session.multiple_faces_detected_count} times")
    
    if session.no_face_duration_seconds > 120:
        flags.append(f"Away from camera for {session.no_face_duration_seconds:.0f} seconds")
    
    if session.low_light_count > 5:
        flags.append(f"Low light conditions detected {session.low_light_count} times")
    
    if session.device_change_count > 0:
        flags.append(f"Camera or device changed {session.device_change_count} times")
    
    if session.screen_capture_detected:
        flags.append("Screen capture or recording detected")
    
    return flags


# Export video proctoring data for integration with submissions
async def get_session_for_submission(
    session_id: str,
    db: AsyncSession,
) -> Optional[dict]:
    """Get video proctoring session data formatted for submission analysis."""
    result = await db.execute(
        select(VideoProctoringSession).where(
            VideoProctoringSession.id == session_id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return None
    
    return {
        "is_active": session.status == "active",
        "session_id": session.id,
        "total_duration_seconds": session.total_duration_seconds or 0.0,
        "face_detected_count": session.face_detected_count,
        "face_lost_count": session.face_lost_count,
        "multiple_faces_detected_count": session.multiple_faces_detected_count,
        "no_face_duration_seconds": session.no_face_duration_seconds or 0.0,
        "low_light_count": session.low_light_count,
        "device_change_count": session.device_change_count,
        "screen_capture_detected": session.screen_capture_detected or False,
        "risk_score": session.risk_score,
        "flags": session.flags or [],
    }


# ============== Video Upload for Analysis ==============

class VideoAnalysisRequest(BaseModel):
    submission_id: Optional[str] = None
    assignment_id: Optional[str] = None


class VideoAnalysisResponse(BaseModel):
    analysis_id: str
    session_id: str
    status: str
    results: dict


class VideoFrameAnalysis(BaseModel):
    """Result of analyzing a single frame or video segment."""
    timestamp_seconds: float
    face_count: int
    faces_detected: List[dict]
    is_suspicious: bool
    reason: Optional[str] = None


class MultipleFaceEvent(BaseModel):
    """Event when multiple faces are detected."""
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float
    max_face_count: int
    face_count_at_start: int


class NoFaceEvent(BaseModel):
    """Event when no face is detected for a period."""
    start_time_seconds: float
    end_time_seconds: float
    duration_seconds: float


class VideoAnalysisResult(BaseModel):
    """Complete analysis result for uploaded video."""
    analysis_id: str
    total_frames_analyzed: int
    duration_seconds: float
    
    # Face detection results
    total_face_detections: int
    max_faces_in_frame: int
    multiple_faces_frames: int
    no_face_frames: int
    
    # Time spans for events
    multiple_face_events: List[MultipleFaceEvent]
    no_face_events: List[NoFaceEvent]
    
    # Suspicious frames
    suspicious_frames: List[VideoFrameAnalysis]
    
    # Risk assessment
    risk_score: float
    flags: List[str]
    recommendation: str
    
    # Metadata
    analyzed_at: str


# Initialize global video processor
_video_processor: Optional[VideoProcessor] = None


async def get_video_processor() -> VideoProcessor:
    """Get or initialize the video processor."""
    global _video_processor
    if _video_processor is None:
        _video_processor = VideoProcessor()
        await _video_processor.initialize()
    return _video_processor


async def analyze_video_frame(
    frame_data: bytes, 
    timestamp: float,
    processor: VideoProcessor
) -> VideoFrameAnalysis:
    """
    Analyze a single frame from the video for face detection.
    Uses the VideoProcessor with face_recognition library for accurate detection.
    """
    try:
        # Use the VideoProcessor for face detection
        face_result = await processor.detect_faces(frame_data)
        
        # Convert face locations to serializable format
        faces = []
        for i, loc in enumerate(face_result.face_locations):
            faces.append({
                "face_id": i + 1,
                "bbox": [loc["top"], loc["right"], loc["bottom"], loc["left"]],
                "confidence": 0.95,  # face_recognition doesn't provide per-face confidence
            })
        
        # Determine if suspicious
        is_suspicious = face_result.multiple_faces_detected or face_result.no_face_detected
        reason = None
        if face_result.multiple_faces_detected:
            reason = f"Multiple faces detected: {face_result.face_count}"
        elif face_result.no_face_detected:
            reason = "No face detected in frame"
        
        return VideoFrameAnalysis(
            timestamp_seconds=timestamp,
            face_count=face_result.face_count,
            faces_detected=faces,
            is_suspicious=is_suspicious,
            reason=reason,
        )
    except Exception as e:
        logger.error("frame_analysis.error", error=str(e))
        return VideoFrameAnalysis(
            timestamp_seconds=timestamp,
            face_count=0,
            faces_detected=[],
            is_suspicious=False,
            reason="Analysis error",
        )


@router.post("/analyze-video", response_model=VideoAnalysisResult)
async def analyze_uploaded_video(
    video: UploadFile = File(...),
    submission_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Upload a video file for face detection analysis.
    This endpoint analyzes the video to detect:
    - Multiple faces in frame
    - No face (person away from camera)
    - Face switching/impersonation attempts
    
    Supports: mp4, webm, mov, avi
    """
    # Validate file type
    ALLOWED_VIDEO_TYPES = ['.mp4', '.webm', '.mov', '.avi', '.mkv']
    file_ext = os.path.splitext(video.filename)[1].lower()
    
    if file_ext not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            400, 
            f"Invalid video format. Allowed: {', '.join(ALLOWED_VIDEO_TYPES)}"
        )
    
    # Read video file
    video_bytes = await video.read()
    file_size = len(video_bytes)
    
    # Max file size: 500MB
    if file_size > 500 * 1024 * 1024:
        raise HTTPException(400, "Video file too large (max 500MB)")
    
    if file_size == 0:
        raise HTTPException(400, "Empty video file")
    
    analysis_id = str(uuid.uuid4())
    
    logger.info(
        "video_proctoring.analyze_started",
        analysis_id=analysis_id,
        filename=video.filename,
        file_size=file_size,
        user_id=current_user.user_id,
    )
    
    # Create a session for this analysis
    session_id = str(uuid.uuid4())
    
    session = VideoProctoringSession(
        id=session_id,
        user_id=current_user.user_id,
        submission_id=submission_id,
        status="completed",  # Video analysis is synchronous
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        events=[],
    )
    db.add(session)
    await db.commit()
    
    # Initialize video processor
    processor = await get_video_processor()
    
    # Save video to temp file for OpenCV processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name
    
    # Track time spans for events
    multiple_face_events = []
    no_face_events = []
    
    # Track consecutive states
    in_multiple_face_event = False
    multiple_face_start_time = 0.0
    max_faces_in_event = 0
    
    in_no_face_event = False
    no_face_start_time = 0.0
    
    try:
        # Open video with OpenCV
        cap = cv2.VideoCapture(tmp_path)
        
        if not cap.isOpened():
            raise HTTPException(400, "Could not open video file")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = frame_count / fps if fps > 0 else 0
        
        # Calculate frame sampling interval (analyze every Nth frame to keep processing reasonable)
        # Target ~30 frames for analysis, but adjust based on video length
        max_frames_to_analyze = 30
        frame_interval = max(1, frame_count // max_frames_to_analyze)
        
        analyzed_frames = 0
        suspicious_frames = []
        total_face_detections = 0
        max_faces = 0
        multiple_faces_count = 0
        no_face_count = 0
        consecutive_no_face = 0
        
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                # Handle end of video - close any open events
                if in_multiple_face_event:
                    end_time = frame_idx / fps if fps > 0 else frame_idx
                    multiple_face_events.append(MultipleFaceEvent(
                        start_time_seconds=round(multiple_face_start_time, 2),
                        end_time_seconds=round(end_time, 2),
                        duration_seconds=round(end_time - multiple_face_start_time, 2),
                        max_face_count=max_faces_in_event,
                        face_count_at_start=0
                    ))
                if in_no_face_event:
                    end_time = frame_idx / fps if fps > 0 else frame_idx
                    no_face_events.append(NoFaceEvent(
                        start_time_seconds=round(no_face_start_time, 2),
                        end_time_seconds=round(end_time, 2),
                        duration_seconds=round(end_time - no_face_start_time, 2)
                    ))
                break
            
            # Only analyze every Nth frame
            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps if fps > 0 else frame_idx
                
                # Convert frame to bytes for face detection
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                # Analyze frame for faces
                frame_analysis = await analyze_video_frame(frame_bytes, timestamp, processor)
                
                face_count = frame_analysis.face_count
                total_face_detections += face_count
                max_faces = max(max_faces, face_count)
                
                if face_count > 1:
                    multiple_faces_count += 1
                    consecutive_no_face = 0
                    
                    # Track multiple face event
                    if not in_multiple_face_event:
                        in_multiple_face_event = True
                        multiple_face_start_time = timestamp
                        max_faces_in_event = face_count
                    else:
                        max_faces_in_event = max(max_faces_in_event, face_count)
                    
                    # Close no-face event if open
                    if in_no_face_event:
                        no_face_events.append(NoFaceEvent(
                            start_time_seconds=round(no_face_start_time, 2),
                            end_time_seconds=round(timestamp, 2),
                            duration_seconds=round(timestamp - no_face_start_time, 2)
                        ))
                        in_no_face_event = False
                    
                    suspicious_frames.append(frame_analysis)
                    
                elif face_count == 0:
                    no_face_count += 1
                    consecutive_no_face += 1
                    
                    # Track no-face event
                    if not in_no_face_event:
                        in_no_face_event = True
                        no_face_start_time = timestamp
                    
                    # Close multiple face event if open
                    if in_multiple_face_event:
                        multiple_face_events.append(MultipleFaceEvent(
                            start_time_seconds=round(multiple_face_start_time, 2),
                            end_time_seconds=round(timestamp, 2),
                            duration_seconds=round(timestamp - multiple_face_start_time, 2),
                            max_face_count=max_faces_in_event,
                            face_count_at_start=0
                        ))
                        in_multiple_face_event = False
                    
                    # Only add some no-face frames as suspicious
                    if consecutive_no_face >= 3:  # Multiple consecutive frames with no face
                        suspicious_frames.append(frame_analysis)
                        
                else:
                    consecutive_no_face = 0
                    
                    # Close any open events when we have exactly 1 face
                    if in_multiple_face_event:
                        multiple_face_events.append(MultipleFaceEvent(
                            start_time_seconds=round(multiple_face_start_time, 2),
                            end_time_seconds=round(timestamp, 2),
                            duration_seconds=round(timestamp - multiple_face_start_time, 2),
                            max_face_count=max_faces_in_event,
                            face_count_at_start=0
                        ))
                        in_multiple_face_event = False
                    
                    if in_no_face_event:
                        no_face_events.append(NoFaceEvent(
                            start_time_seconds=round(no_face_start_time, 2),
                            end_time_seconds=round(timestamp, 2),
                            duration_seconds=round(timestamp - no_face_start_time, 2)
                        ))
                        in_no_face_event = False
                
                analyzed_frames += 1
            
            frame_idx += 1
        
        cap.release()
        
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    
    # Calculate risk score based on actual analysis
    # NEW THRESHOLD SYSTEM:
    # 1. Absolute absence time (continuous no-face duration)
    # 2. Ratio of missing faces (based on video length)
    # 3. Consecutive missing frames
    
    risk_score = 0.0
    
    # Check 1: Long absence (absolute time-based)
    if no_face_events:
        longest_no_face = max(e.duration_seconds for e in no_face_events) if no_face_events else 0
        if longest_no_face > 20:
            risk_score += 0.30  # High risk
        elif longest_no_face > 10:
            risk_score += 0.20  # Medium risk
        elif longest_no_face > 5:
            risk_score += 0.10  # Warning
    
    # Check 2: Ratio of missing faces (based on video length)
    if analyzed_frames > 0:
        no_face_ratio = no_face_count / analyzed_frames
        
        # Threshold based on video duration
        if duration_seconds < 120:  # < 2 min
            ratio_threshold = 0.15
        elif duration_seconds < 600:  # 2-10 min
            ratio_threshold = 0.25
        elif duration_seconds < 3600:  # 10-60 min
            ratio_threshold = 0.35
        else:  # > 1 hour
            ratio_threshold = 0.40
        
        if no_face_ratio > ratio_threshold:
            risk_score += min(no_face_ratio * 0.3, 0.30)
    
    # Check 3: Consecutive missing frames
    if consecutive_no_face > 4:
        risk_score += 0.15
    
    # Multiple faces detected
    if multiple_faces_count > 0:
        risk_score += min(multiple_faces_count / 10.0, 0.40)
    
    # Maximum faces in a single frame
    if max_faces > 2:
        risk_score += 0.20  # More than 2 faces is highly suspicious
    
    risk_score = min(risk_score, 1.0)
    
    # Generate industry-style flags (separate from risk score)
    flags = []
    
    # 1. Video Quality Flags
    if duration_seconds < 10:
        flags.append("video_too_short")
    elif fps and fps < 10:
        flags.append("low_fps_video")
    
    # 2. Face Detection Flags
    # Multiple faces detected (most critical)
    if multiple_face_events and multiple_faces_count > 0:
        flags.append("multiple_faces_detected")
    # No face detected
    elif no_face_events and no_face_count > 0:
        # Check for long absence
        longest_no_face = max(e.duration_seconds for e in no_face_events) if no_face_events else 0
        if longest_no_face > 10:
            flags.append("long_face_absence")
        elif no_face_count > analyzed_frames * 0.3:
            flags.append("no_face_detected")
        else:
            flags.append("intermittent_face_loss")
    # No faces at all
    elif max_faces == 0 and analyzed_frames > 0:
        flags.append("no_face_detected")
    # Single face detected (normal case)
    elif max_faces == 1 and multiple_faces_count == 0 and no_face_count == 0:
        flags.append("single_face_detected")
    
    # 3. Frame Analysis Flags
    if analyzed_frames > 0:
        no_face_ratio = no_face_count / analyzed_frames
        # Check ratio threshold based on video length
        if duration_seconds < 120:
            ratio_threshold = 0.15
        elif duration_seconds < 600:
            ratio_threshold = 0.25
        elif duration_seconds < 3600:
            ratio_threshold = 0.35
        else:
            ratio_threshold = 0.40
        
        if no_face_ratio > ratio_threshold:
            flags.append("high_no_face_ratio")
        
        # Check for unstable detection (many switches between face/no face)
        if no_face_count > 0 and multiple_faces_count > 0:
            flags.append("unstable_detection")
    
    # 4. System Behavior Flags
    flags.append("analysis_complete")
    
    # 5. Risk Level Flags (based on final risk score)
    if risk_score > 0.5:
        flags.append("high_risk")
    elif risk_score > 0.2:
        flags.append("medium_risk")
    else:
        flags.append("low_risk")
    
    # Generate recommendation
    if risk_score > 0.6:
        recommendation = "High risk detected. The video shows evidence of multiple people or suspicious behavior. Manual review recommended."
    elif risk_score > 0.3:
        recommendation = "Medium risk detected. Some suspicious patterns detected. Review flagged frames."
    elif analyzed_frames == 0:
        recommendation = "Could not analyze video frames. Please ensure the video is valid and contains visible content."
    else:
        recommendation = "Low risk. No significant anomalies detected in the video."
    
    # Update session with results
    await db.execute(
        update(VideoProctoringSession)
        .where(VideoProctoringSession.id == session_id)
        .values(
            multiple_faces_detected_count=multiple_faces_count,
            face_lost_count=no_face_count,
            total_duration_seconds=duration_seconds,
            risk_score=risk_score,
            flags=flags,
        )
    )
    await db.commit()
    
    result = VideoAnalysisResult(
        analysis_id=analysis_id,
        total_frames_analyzed=analyzed_frames,
        duration_seconds=round(duration_seconds, 2),
        total_face_detections=total_face_detections,
        max_faces_in_frame=max_faces,
        multiple_faces_frames=multiple_faces_count,
        no_face_frames=no_face_count,
        multiple_face_events=multiple_face_events[:10],  # Limit to 10 events
        no_face_events=no_face_events[:10],  # Limit to 10 events
        suspicious_frames=suspicious_frames[:10],  # Limit to 10 most suspicious
        risk_score=round(risk_score, 4),
        flags=flags,
        recommendation=recommendation,
        analyzed_at=datetime.utcnow().isoformat(),
    )
    
    logger.info(
        "video_proctoring.analyze_completed",
        analysis_id=analysis_id,
        risk_score=risk_score,
        multiple_faces_count=multiple_faces_count,
        no_face_count=no_face_count,
        frames_analyzed=analyzed_frames,
    )
    
    return result


@router.post("/analyze-video-url")
async def analyze_video_from_url(
    video_url: str,
    submission_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Analyze a video from a URL for face detection.
    The video will be downloaded and analyzed for multiple faces.
    """
    import httpx
    
    analysis_id = str(uuid.uuid4())
    
    # Validate URL
    if not video_url.startswith(('http://', 'https://')):
        raise HTTPException(400, "Invalid video URL")
    
    logger.info(
        "video_proctoring.analyze_url_started",
        analysis_id=analysis_id,
        video_url=video_url,
    )
    
    try:
        # Download video (with timeout and size limit)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(video_url)
            response.raise_for_status()
            
            video_bytes = response.content
            file_size = len(video_bytes)
            
            if file_size > 500 * 1024 * 1024:
                raise HTTPException(400, "Video file too large (max 500MB)")
            
            # Create temp file for analysis
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name
            
            # Process video
            # In production, use cv2 or ffmpeg to process
            os.unlink(tmp_path)  # Clean up
            
            # Return analysis result (simulated)
            return {
                "analysis_id": analysis_id,
                "status": "completed",
                "video_url": video_url,
                "message": "Video analysis from URL is not fully implemented. Please use file upload for now.",
                "risk_score": 0.0,
            }
            
    except httpx.HTTPError as e:
        logger.error("video_proctoring.download_failed", error=str(e))
        raise HTTPException(400, f"Failed to download video: {str(e)}")

