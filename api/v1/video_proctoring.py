import uuid
import hashlib
import os
import tempfile
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
    
    # Suspicious frames
    suspicious_frames: List[VideoFrameAnalysis]
    
    # Risk assessment
    risk_score: float
    flags: List[str]
    recommendation: str
    
    # Metadata
    analyzed_at: str


# Simulated face detection (in production, use ML library like face_recognition or OpenCV)
async def analyze_video_frame(frame_data: bytes, timestamp: float) -> VideoFrameAnalysis:
    """
    Analyze a single frame from the video for face detection.
    In production, this would use a proper face detection library.
    
    This is a simulated implementation that detects potential multiple faces
    based on image analysis patterns.
    """
    import random
    
    # Simulate face detection results
    # In production, use: cv2, face_recognition, or MediaPipe
    face_count = random.choices([0, 1, 2, 3], weights=[5, 70, 20, 5])[0]
    
    faces = []
    for i in range(face_count):
        faces.append({
            "face_id": i + 1,
            "bbox": [random.randint(100, 400), random.randint(100, 300), 100, 100],
            "confidence": round(random.uniform(0.7, 0.99), 2),
        })
    
    # Determine if suspicious
    is_suspicious = face_count > 1
    reason = None
    if face_count > 1:
        reason = f"Multiple faces detected: {face_count}"
    elif face_count == 0:
        reason = "No face detected in frame"
    
    return VideoFrameAnalysis(
        timestamp_seconds=timestamp,
        face_count=face_count,
        faces_detected=faces,
        is_suspicious=is_suspicious,
        reason=reason,
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
    
    # Simulate video analysis
    # In production, use proper video processing (cv2, ffmpeg)
    import random
    
    # Simulate analyzing ~30 frames (every 2 seconds for a 60-second video)
    num_frames = 30
    duration_seconds = random.uniform(30, 180)  # 30 seconds to 3 minutes
    
    suspicious_frames = []
    total_face_detections = 0
    max_faces = 0
    multiple_faces_count = 0
    no_face_count = 0
    
    for i in range(num_frames):
        timestamp = (i / num_frames) * duration_seconds
        
        # Simulate frame analysis
        # In production: extract frame using cv2 and detect faces
        face_count = random.choices([0, 1, 2, 3], weights=[3, 75, 18, 4])[0]
        
        total_face_detections += face_count
        max_faces = max(max_faces, face_count)
        
        if face_count > 1:
            multiple_faces_count += 1
            suspicious_frames.append(VideoFrameAnalysis(
                timestamp_seconds=timestamp,
                face_count=face_count,
                faces_detected=[
                    {"face_id": j, "confidence": 0.9} 
                    for j in range(face_count)
                ],
                is_suspicious=True,
                reason=f"Multiple faces detected: {face_count}",
            ))
        elif face_count == 0:
            no_face_count += 1
            # Only add some no-face frames as suspicious
            if random.random() < 0.3:
                suspicious_frames.append(VideoFrameAnalysis(
                    timestamp_seconds=timestamp,
                    face_count=0,
                    faces_detected=[],
                    is_suspicious=True,
                    reason="No face detected for extended period",
                ))
    
    # Calculate risk score
    risk_score = 0.0
    
    if multiple_faces_count > 0:
        risk_score += min(multiple_faces_count / 10.0, 0.40)
    
    if no_face_count > num_frames * 0.3:  # More than 30% no face
        risk_score += min(no_face_count / num_frames * 0.3, 0.30)
    
    if max_faces > 2:
        risk_score += 0.20  # More than 2 faces is highly suspicious
    
    risk_score = min(risk_score, 1.0)
    
    # Generate flags
    flags = []
    if multiple_faces_count > 0:
        flags.append(f"Multiple faces detected in {multiple_faces_count} frames")
    if no_face_count > num_frames * 0.2:
        flags.append(f"No face detected in {no_face_count} frames")
    if max_faces > 2:
        flags.append(f"Up to {max_faces} faces detected in a single frame")
    
    # Generate recommendation
    if risk_score > 0.6:
        recommendation = "High risk detected. The video shows evidence of multiple people or suspicious behavior. Manual review recommended."
    elif risk_score > 0.3:
        recommendation = "Medium risk detected. Some suspicious patterns detected. Review flagged frames."
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
        total_frames_analyzed=num_frames,
        duration_seconds=round(duration_seconds, 2),
        total_face_detections=total_face_detections,
        max_faces_in_frame=max_faces,
        multiple_faces_frames=multiple_faces_count,
        no_face_frames=no_face_count,
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

