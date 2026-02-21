import asyncio
import json
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from core.config import settings
from core.controller import IntegrityController
from core.registry import ModuleRegistry
from core.aggregator import RiskAggregator
from core.events import EventEmitter
from db.session import init_db

# Module implementations
from modules.ai_detection.detector import AIDetectionModule
from modules.plagiarism.detector import PlagiarismModule
from modules.writing_profile.profiler import WritingProfileModule
from modules.proctoring.detector import ProctoringModule

logger = structlog.get_logger()

# ── Global singletons ────────────────────────────────────────────────────────
redis_client = None
registry: ModuleRegistry = None
controller: IntegrityController = None
emitter: EventEmitter = EventEmitter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, registry, controller

    logger.info("app.starting", version=settings.APP_VERSION)

    # Connect to Redis
    try:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=False
        )
        await redis_client.ping()
        logger.info("redis.connected")
    except Exception as e:
        logger.warning("redis.unavailable_using_fakeredis", error=str(e))
        from fakeredis.aioredis import FakeRedis
        redis_client = FakeRedis()

    # Initialize DB
    try:
        await init_db()
    except Exception as e:
        logger.warning("db.init_failed", error=str(e))

    # Instantiate modules
    modules = [
        AIDetectionModule(),
        PlagiarismModule(),
        WritingProfileModule(),
        ProctoringModule(),
    ]

    # Warm up modules
    for module in modules:
        try:
            await module.warmup()
        except Exception as e:
            logger.warning("module.warmup_failed", module=module.module_id, error=str(e))

    # Wire up registry and controller
    registry = ModuleRegistry(redis_client, modules)
    await registry.initialize()

    aggregator = RiskAggregator()
    controller = IntegrityController(registry, aggregator, emitter)

    logger.info("app.ready", modules=[m.module_id for m in modules])

    yield

    # Cleanup
    if redis_client:
        await redis_client.aclose()
    logger.info("app.shutdown")


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Academic Integrity Analysis Platform",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
from api.v1.auth import router as auth_router
from api.v1.submissions import router as submissions_router
from api.v1.modules import router as modules_router
from api.v1.admin import router as admin_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(submissions_router, prefix="/api/v1")
app.include_router(modules_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


# ── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws/submissions/{submission_id}")
async def submission_websocket(ws: WebSocket, submission_id: str):
    await ws.accept()
    logger.info("ws.connected", submission_id=submission_id)

    try:
        async for event in emitter.stream_events(submission_id, timeout=60.0):
            await ws.send_json(event)
            if event.get("type") == "completed":
                break
    except WebSocketDisconnect:
        logger.info("ws.disconnected", submission_id=submission_id)
    except Exception as e:
        logger.error("ws.error", error=str(e))
        try:
            await ws.close()
        except Exception:
            pass


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    status = {"status": "ok", "version": settings.APP_VERSION}

    if registry:
        status["modules"] = [
            {"id": m["module_id"], "healthy": m["healthy"]}
            for m in registry.list_modules()
        ]

    redis_ok = False
    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    status["redis"] = "ok" if redis_ok else "unavailable"
    return status


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
    }
