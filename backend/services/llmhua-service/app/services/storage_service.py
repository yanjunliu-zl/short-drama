"""
Ceph 对象存储服务 (通过 S3 兼容 API)

使用 boto3 与 Ceph RGW 交互，支持:
- 从 HTTP URL 下载文件并上传到 Ceph
- 从本地文件路径上传到 Ceph
- 从字节数据上传到 Ceph
- 生成预签名 URL
- 删除对象
"""

import logging
import os
import uuid
import mimetypes
from typing import Any, Optional, Tuple
from datetime import datetime

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Ceph 对象存储服务 (S3 兼容)"""

    def __init__(self):
        self.endpoint = settings.STORAGE_ENDPOINT
        self.public_endpoint = getattr(settings, 'STORAGE_PUBLIC_ENDPOINT', 'http://localhost:9000')
        self.access_key = settings.STORAGE_ACCESS_KEY
        self.secret_key = settings.STORAGE_SECRET_KEY
        self.bucket = settings.STORAGE_BUCKET
        self.region = settings.STORAGE_REGION
        self.type = settings.STORAGE_TYPE
        self.local_base_path = settings.STORAGE_LOCAL_BASE_PATH
        self._client = None
        self._public_client = None
        self._initialized = False

    def _make_client(self, endpoint: str) -> Any:
        """创建 S3 兼容客户端"""
        use_ssl = endpoint.startswith("https://")
        endpoint_url = endpoint if "://" in endpoint else f"http://{endpoint}"
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            use_ssl=use_ssl,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 3},
                connect_timeout=10,
                read_timeout=30,
            ),
        )

    async def initialize(self):
        """初始化存储客户端"""
        if self._initialized:
            return

        try:
            if self.type == "local":
                os.makedirs(self.local_base_path, exist_ok=True)
                logger.info(f"使用本地存储: {self.local_base_path}")
            else:
                # 内部客户端（用于上传/下载）
                self._client = self._make_client(self.endpoint)
                await self._ensure_bucket()

                # 外部客户端（用于生成预签名URL），如果 public_endpoint 不同则单独创建
                if self.public_endpoint and self.public_endpoint != self.endpoint:
                    self._public_client = self._make_client(self.public_endpoint)
                    logger.info(f"外部端点已配置: {self.public_endpoint}")
                else:
                    self._public_client = self._client

                logger.info(f"存储服务初始化: endpoint={self.endpoint}, bucket={self.bucket}")

            self._initialized = True

        except Exception as e:
            logger.error(f"存储服务初始化失败: {e}")
            raise

    async def _ensure_bucket(self):
        """确保 Bucket 存在，不存在则创建"""
        try:
            self._client.head_bucket(Bucket=self.bucket)
            logger.info(f"Bucket 已存在: {self.bucket}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404" or error_code == "NoSuchBucket":
                try:
                    self._client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": self.region},
                    )
                    logger.info(f"Bucket 已创建: {self.bucket}")
                except Exception as create_err:
                    logger.error(f"创建 Bucket 失败: {create_err}")
                    raise
            else:
                raise

    async def close(self):
        """关闭存储客户端"""
        self._client = None
        self._initialized = False
        logger.info("存储服务已关闭")

    async def download_from_url(self, url: str, timeout: int = 120) -> Optional[bytes]:
        """
        从 HTTP URL 下载文件内容

        返回: 文件字节数据，失败返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"下载文件失败: url={url}, error={e}")
            return None

    def _generate_object_key(
        self,
        media_type: str,        # "image" or "video"
        related_entity_type: str = "unknown",
        related_entity_id: str = "unknown",
        file_extension: str = "",
    ) -> str:
        """
        生成 Ceph 对象 Key

        格式: {media_type}/{date}/{entity_type}/{entity_id}/{uuid}.{ext}
        """
        date_str = datetime.now().strftime("%Y/%m/%d")
        unique_id = uuid.uuid4().hex[:12]
        ext = file_extension.lstrip(".")

        if ext:
            return f"{media_type}/{date_str}/{related_entity_type}/{related_entity_id}/{unique_id}.{ext}"
        else:
            return f"{media_type}/{date_str}/{related_entity_type}/{related_entity_id}/{unique_id}"

    async def upload_from_url(
        self,
        url: str,
        media_type: str,
        content_type: str = "application/octet-stream",
        related_entity_type: str = "unknown",
        related_entity_id: str = "unknown",
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """
        从 HTTP URL 下载文件并上传到 Ceph

        参数:
            url: 源文件 URL
            media_type: 媒体类型 ("image" / "video")
            content_type: MIME 类型
            related_entity_type: 关联实体类型 (如 "scene", "storyboard")
            related_entity_id: 关联实体 ID

        返回: (object_key, presigned_url, file_size) 或 (None, None, None)
        """
        if not self._initialized:
            await self.initialize()

        # 下载文件
        data = await self.download_from_url(url)
        if data is None:
            return None, None, None

        file_size = len(data)

        # 推断文件扩展名
        ext = mimetypes.guess_extension(content_type) or ""
        if not ext and url:
            # 从 URL 推断扩展名
            url_path = url.split("?")[0]
            _, ext = os.path.splitext(url_path)

        # 生成对象 Key
        object_key = self._generate_object_key(
            media_type=media_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            file_extension=ext,
        )

        # 上传
        presigned_url = await self.upload_bytes(
            data=data,
            object_key=object_key,
            content_type=content_type,
        )

        if presigned_url is None:
            return None, None, None

        logger.info(
            f"从URL上传成功: {url[:80]}... -> {object_key} "
            f"(size={file_size}, type={content_type})"
        )
        return object_key, presigned_url, file_size

    async def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """
        上传字节数据到 Ceph

        返回: 预签名 URL，失败返回 None
        """
        if self.type == "local":
            return await self._upload_bytes_local(data, object_key)

        if self._client is None:
            logger.error("存储客户端未初始化")
            return None

        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type,
                ACL="public-read",
            )

            # 生成预签名 URL（使用外部端点，浏览器可直接访问）
            url_client = self._public_client or self._client
            presigned_url = url_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=7 * 24 * 3600,
            )

            logger.info(f"上传成功: {object_key} ({len(data)} bytes)")
            return presigned_url

        except Exception as e:
            logger.error(f"上传到 Ceph 失败: {object_key}, error={e}")
            return None

    async def _upload_bytes_local(self, data: bytes, object_key: str) -> Optional[str]:
        """上传到本地存储"""
        try:
            file_path = os.path.join(self.local_base_path, object_key)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(data)

            relative_url = f"/storage/{object_key}"
            logger.info(f"上传到本地: {file_path} ({len(data)} bytes)")
            return relative_url
        except Exception as e:
            logger.error(f"上传到本地失败: {object_key}, error={e}")
            return None

    async def upload_file(
        self,
        file_path: str,
        object_key: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """
        从本地文件路径上传到 Ceph

        返回: 预签名 URL，失败返回 None
        """
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        try:
            with open(file_path, "rb") as f:
                data = f.read()
            return await self.upload_bytes(data, object_key, content_type)
        except Exception as e:
            logger.error(f"上传文件失败: {file_path}, error={e}")
            return None

    async def delete_object(self, object_key: str) -> bool:
        """从 Ceph 删除对象"""
        if self.type == "local":
            return self._delete_local(object_key)

        if self._client is None:
            return False

        try:
            self._client.delete_object(Bucket=self.bucket, Key=object_key)
            logger.info(f"删除成功: {object_key}")
            return True
        except Exception as e:
            logger.error(f"删除失败: {object_key}, error={e}")
            return False

    def _delete_local(self, object_key: str) -> bool:
        """删除本地文件"""
        try:
            file_path = os.path.join(self.local_base_path, object_key)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"本地文件已删除: {file_path}")
            return True
        except Exception as e:
            logger.error(f"删除本地文件失败: {object_key}, error={e}")
            return False

    def get_object_url(self, object_key: str) -> str:
        """获取对象的公开 URL"""
        if self.type == "local":
            return f"/storage/{object_key}"

        # 构造 S3 对象 URL
        endpoint = self.endpoint.rstrip("/")
        return f"{endpoint}/{self.bucket}/{object_key}"


# 全局存储服务实例
_storage_service: Optional[StorageService] = None


async def get_storage_service() -> StorageService:
    """获取全局存储服务实例"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
        await _storage_service.initialize()
    return _storage_service


async def close_storage_service():
    """关闭全局存储服务实例"""
    global _storage_service
    if _storage_service:
        await _storage_service.close()
        _storage_service = None
