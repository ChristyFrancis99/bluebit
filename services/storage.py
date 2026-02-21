import hashlib
import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
import boto3
from botocore.exceptions import ClientError
from core.config import settings
import structlog

logger = structlog.get_logger()


class StorageService:
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self._bucket = settings.S3_BUCKET

    def ensure_bucket(self):
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)
            logger.info("storage.bucket_created", bucket=self._bucket)

    async def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to S3 and return the S3 key."""
        def _upload():
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
        await asyncio.to_thread(_upload)
        logger.info("storage.uploaded", key=key, size=len(file_bytes))
        return key

    async def download_file(self, key: str) -> bytes:
        def _download():
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        return await asyncio.to_thread(_download)

    async def generate_presigned_url(self, key: str, expires: int = 3600) -> str:
        def _sign():
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires,
            )
        return await asyncio.to_thread(_sign)

    async def delete_file(self, key: str):
        def _delete():
            self._client.delete_object(Bucket=self._bucket, Key=key)
        await asyncio.to_thread(_delete)

    @staticmethod
    def compute_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def build_key(submission_id: str, filename: str) -> str:
        ext = Path(filename).suffix or ".bin"
        return f"submissions/{submission_id}/original{ext}"


class FallbackStorageService(StorageService):
    """File-system fallback if MinIO is unavailable."""
    BASE_PATH = Path("/tmp/academic_integrity_storage")

    def __init__(self):
        self.BASE_PATH.mkdir(parents=True, exist_ok=True)

    def ensure_bucket(self):
        self.BASE_PATH.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file_bytes: bytes, key: str, **kwargs) -> str:
        path = self.BASE_PATH / key.replace("/", "_")
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(file_bytes)
        return key

    async def download_file(self, key: str) -> bytes:
        path = self.BASE_PATH / key.replace("/", "_")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def generate_presigned_url(self, key: str, expires: int = 3600) -> str:
        return f"/api/v1/files/{key}"

    async def delete_file(self, key: str):
        path = self.BASE_PATH / key.replace("/", "_")
        if path.exists():
            path.unlink()


def get_storage() -> StorageService:
    try:
        svc = StorageService()
        svc.ensure_bucket()
        return svc
    except Exception as e:
        logger.warning("storage.s3_unavailable_using_fallback", error=str(e))
        svc = FallbackStorageService()
        svc.ensure_bucket()
        return svc
