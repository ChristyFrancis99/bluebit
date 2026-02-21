import uuid
import hashlib
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form,
    BackgroundTasks, WebSocket, WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db.models import Submission, IntegrityReport
from db.session import get_db
from services.auth import get_current_user, TokenData
from services.extractor import extract_text
from services.storage import get_storage
from services.report_generator import generate_pdf_report
from core.config import settings

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/submissions", tags=["submissions"])


class SubmissionResponse(BaseModel):
    submission_id: str
    status: str
    ws_url: str
    estimated_seconds: int = 8


class SubmissionStatus(BaseModel):
    submission_id: str
    status: str
    created_at: str
    completed_at: Optional[str]
    integrity_score: Optional[float]
    risk_level: Optional[str]


@router.post("", response_model=SubmissionResponse, status_code=202)
async def create_submission(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    modules: Optional[str] = Form(None),
    assignment_id: Optional[str] = Form(None),
    session_data: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    from api.main import controller, emitter

    # Validate file
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.MAX_FILE_SIZE_MB}MB)")

    if len(file_bytes) == 0:
        raise HTTPException(400, "Empty file")

    # Parse requested modules
    requested_modules = None
    if modules:
        requested_modules = [m.strip() for m in modules.split(",") if m.strip()]

    # Compute hashes
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for duplicate
    result = await db.execute(
        select(Submission).where(
            Submission.file_hash == file_hash,
            Submission.user_id == current_user.user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing and existing.status == "done":
        return SubmissionResponse(
            submission_id=existing.id,
            status="cached",
            ws_url=f"/ws/submissions/{existing.id}",
        )

    submission_id = str(uuid.uuid4())

    # Upload to storage
    storage = get_storage()
    s3_key = storage.build_key(submission_id, file.filename or "upload.txt")
    await storage.upload_file(file_bytes, s3_key)

    # Extract text (async)
    text, extraction_meta = await extract_text(file_bytes, file.filename or "upload.txt")
    if not text:
        raise HTTPException(422, "Could not extract text from file")

    text_hash = hashlib.sha256(text.encode()).hexdigest()

    # Create submission record
    submission = Submission(
        id=submission_id,
        user_id=current_user.user_id,
        institution_id=current_user.institution_id,
        file_path=s3_key,
        file_hash=file_hash,
        text_hash=text_hash,
        original_filename=file.filename,
        file_size_bytes=len(file_bytes),
        word_count=extraction_meta.get("word_count", 0),
        status="processing",
        modules_requested=requested_modules,
        assignment_id=assignment_id,
    )
    db.add(submission)
    await db.commit()

    # Parse session data for proctoring
    import json
    session = {}
    if session_data:
        try:
            session = json.loads(session_data)
        except Exception:
            pass

    # Run analysis in background
    metadata = {
        "submission_id": submission_id,
        "user_id": current_user.user_id,
        "institution_id": current_user.institution_id,
        "assignment_id": assignment_id,
        "session": session,
    }

    background_tasks.add_task(
        _run_analysis,
        submission_id=submission_id,
        text=text,
        metadata=metadata,
        requested_modules=requested_modules,
        institution_id=current_user.institution_id,
    )

    return SubmissionResponse(
        submission_id=submission_id,
        status="processing",
        ws_url=f"/ws/submissions/{submission_id}",
        estimated_seconds=8,
    )


async def _run_analysis(
    submission_id: str,
    text: str,
    metadata: dict,
    requested_modules: Optional[List[str]],
    institution_id: Optional[str],
):
    """Background task: run all modules and save report."""
    from api.main import controller
    from db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await controller.run(
                submission_id=submission_id,
                text=text,
                metadata=metadata,
                requested_modules=requested_modules,
                institution_id=institution_id,
            )

            # Save report
            report = IntegrityReport(
                id=str(uuid.uuid4()),
                submission_id=submission_id,
                integrity_score=result.integrity_score,
                risk_level=result.risk_level,
                confidence=result.confidence,
                module_results=result.breakdown,
                weights_used={},
                recommendation=result.recommendation,
                flags=result.flags,
            )
            db.add(report)

            # Update submission status
            sub_result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            submission = sub_result.scalar_one_or_none()
            if submission:
                submission.status = "done"
                submission.completed_at = datetime.utcnow()

            await db.commit()
            logger.info("analysis.saved", submission_id=submission_id)

        except Exception as e:
            logger.error("analysis.failed", submission_id=submission_id, error=str(e))
            sub_result = await db.execute(
                select(Submission).where(Submission.id == submission_id)
            )
            submission = sub_result.scalar_one_or_none()
            if submission:
                submission.status = "failed"
                await db.commit()


@router.get("/{submission_id}/status", response_model=SubmissionStatus)
async def get_status(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Submission not found")

    # Authorization check
    if sub.user_id != current_user.user_id and current_user.role not in ("educator", "admin"):
        raise HTTPException(403, "Access denied")

    report = None
    if sub.status == "done":
        rep_result = await db.execute(
            select(IntegrityReport).where(IntegrityReport.submission_id == submission_id)
        )
        report = rep_result.scalar_one_or_none()

    return SubmissionStatus(
        submission_id=submission_id,
        status=sub.status,
        created_at=sub.created_at.isoformat(),
        completed_at=sub.completed_at.isoformat() if sub.completed_at else None,
        integrity_score=report.integrity_score if report else None,
        risk_level=report.risk_level if report else None,
    )


@router.get("/{submission_id}/report")
async def get_report(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Submission not found")

    if sub.user_id != current_user.user_id and current_user.role not in ("educator", "admin"):
        raise HTTPException(403, "Access denied")

    rep_result = await db.execute(
        select(IntegrityReport).where(IntegrityReport.submission_id == submission_id)
    )
    report = rep_result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, "Report not yet available")

    return {
        "submission_id": submission_id,
        "integrity_score": report.integrity_score,
        "risk_level": report.risk_level,
        "confidence": report.confidence,
        "recommendation": report.recommendation,
        "flags": report.flags,
        "modules": report.module_results,
        "created_at": report.created_at.isoformat(),
        "pdf_download_url": f"/api/v1/submissions/{submission_id}/report/pdf",
    }


@router.get("/{submission_id}/report/pdf")
async def download_pdf_report(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    result = await db.execute(
        select(Submission, IntegrityReport).join(
            IntegrityReport, IntegrityReport.submission_id == Submission.id
        ).where(Submission.id == submission_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Report not found")

    sub, report = row
    if sub.user_id != current_user.user_id and current_user.role not in ("educator", "admin"):
        raise HTTPException(403, "Access denied")

    pdf_bytes = await asyncio.to_thread(
        generate_pdf_report,
        {
            "integrity_score": report.integrity_score,
            "risk_level": report.risk_level,
            "confidence": report.confidence,
            "recommendation": report.recommendation,
            "flags": report.flags or [],
            "breakdown": report.module_results or {},
        },
        {
            "id": submission_id,
            "original_filename": sub.original_filename,
            "word_count": sub.word_count,
            "student_email": current_user.email,
            "assignment_id": sub.assignment_id,
            "status": sub.status,
        },
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="integrity-report-{submission_id[:8]}.pdf"'
        },
    )


@router.get("")
async def list_submissions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    query = select(Submission).order_by(desc(Submission.created_at))

    if current_user.role == "student":
        query = query.where(Submission.user_id == current_user.user_id)
    elif current_user.role == "educator":
        if current_user.institution_id:
            query = query.where(
                Submission.institution_id == current_user.institution_id
            )

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    subs = result.scalars().all()

    return {
        "submissions": [
            {
                "id": s.id,
                "status": s.status,
                "original_filename": s.original_filename,
                "word_count": s.word_count,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in subs
        ],
        "total": len(subs),
        "limit": limit,
        "offset": offset,
    }
