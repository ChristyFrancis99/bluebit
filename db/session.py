from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from core.config import settings
from db.models import Base
import structlog

logger = structlog.get_logger()

def _make_engine():
    url = settings.DATABASE_URL

    # SQLite fallback for local dev (no PostgreSQL needed)
    if "postgresql" in url:
        try:
            import asyncpg  # noqa
            return create_async_engine(
                url, echo=settings.DEBUG, pool_pre_ping=True, poolclass=NullPool
            )
        except Exception as e:
            logger.warning("db.postgres_unavailable_falling_back_to_sqlite", error=str(e))

    # Use SQLite
    sqlite_url = "sqlite+aiosqlite:///./integrity_dev.db"
    logger.info("db.using_sqlite", path="./integrity_dev.db")
    return create_async_engine(
        sqlite_url,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


engine = _make_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db.tables_created")


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
