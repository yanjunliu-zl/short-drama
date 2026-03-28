"""
对象存储服务 - 用于上传和管理视频文件到对象存储

支持的存储后端:
- S3 (AWS S3, MinIO, 兼容S3的存储)
- 本地存储 (开发/测试用)
"""

import logging
import os
import pathlib
import tempfile
from typing import Optional, BinaryIO, IO
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """存储配置"""
    type: str = "s3"  # s3, local
    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""
    region: str = "us-east-1"
    use_ssl: bool = False


class StorageService:
    """对象存储服务"""

    def __init__(self):
        self.config = StorageConfig(
            type=settings.STORAGE_TYPE or "s3",
            endpoint=settings.STORAGE_ENDPOINT or "http://minio:9000",
            access_key=settings.STORAGE_ACCESS_KEY or "admin",
            secret_key=settings.STORAGE_SECRET_KEY or "admin123",
            bucket=settings.STORAGE_BUCKET or "short-drama",
            region=settings.STORAGE_REGION or "us-east-1",
            use_ssl=settings.STORAGE_USE_SSL or False,
        )
        self.s3_client = None
        self.minio_client = None
        self._initialized = False

    async def initialize(self):
        """初始化存储服务"""
        if self._initialized:
            return

        logger.info(f"初始化对象存储服务: type={self.config.type}")

        if self.config.type == "local":
            # 初始化本地存储
            self._ensure_local_storage()
            logger.info("使用本地存储")
        else:
            # 初始化 S3/MinIO 客户端
            try:
                if self.config.endpoint and "minio" in self.config.endpoint.lower():
                    # 使用 MinIO 客户端
                    self.minio_client = Minio(
                        self.config.endpoint.replace("http://", "").replace("https://", ""),
                        access_key=self.config.access_key,
                        secret_key=self.config.secret_key,
                        secure=self.config.use_ssl,
                    )
                    # 检查桶是否存在
                    found = self.minio_client.bucket_exists(self.config.bucket)
                    if not found:
                        self.minio_client.make_bucket(self.config.bucket)
                        logger.info(f"创建 MinIO 桶: {self.config.bucket}")
                    logger.info(f"MinIO 客户端初始化成功: {self.config.endpoint}")
                else:
                    # 使用 AWS S3 客户端
                    self.s3_client = boto3.client(
                        "s3",
                        endpoint_url=self.config.endpoint,
                        aws_access_key_id=self.config.access_key,
                        aws_secret_access_key=self.config.secret_key,
                        region_name=self.config.region,
                    )
                    # 检查桶是否存在
                    try:
                        self.s3_client.head_bucket(Bucket=self.config.bucket)
                    except ClientError:
                        # 桶不存在，创建它
                        self.s3_client.create_bucket(
                            Bucket=self.config.bucket,
                            CreateBucketConfiguration={"LocationConstraint": self.config.region}
                        )
                        logger.info(f"创建 S3 桶: {self.config.bucket}")
                    logger.info(f"S3 客户端初始化成功: {self.config.endpoint}")

                self._initialized = True
                logger.info("对象存储服务初始化完成")

            except Exception as e:
                logger.error(f"对象存储服务初始化失败: {e}")
                self._initialized = True  # 即使失败也标记为已初始化，避免重复尝试

    def _ensure_local_storage(self):
        """确保本地存储目录存在"""
        local_path = "/app/storage"
        if not os.path.exists(local_path):
            os.makedirs(local_path, exist_ok=True)
            logger.info(f"创建本地存储目录: {local_path}")

    async def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: str = "video/mp4"
    ) -> str:
        """上传文件到对象存储

        Args:
            file_path: 本地文件路径
            object_name: 对象名称（在存储中的路径）
            content_type: 内容类型

        Returns:
            str: 文件的访问URL
        """
        if not self._initialized:
            await self.initialize()

        if self.config.type == "local":
            return await self._upload_to_local(file_path, object_name)

        try:
            if self.minio_client:
                # 使用 MinIO 客户端上传
                self.minio_client.fput_object(
                    self.config.bucket,
                    object_name,
                    file_path,
                    content_type=content_type,
                )
                # 返回预签名URL（7天有效）
                url = self.minio_client.presigned_get_object(
                    self.config.bucket,
                    object_name,
                    expires=7 * 24 * 3600,  # 7天
                )
            elif self.s3_client:
                # 使用 S3 客户端上传
                self.s3_client.upload_file(
                    file_path,
                    self.config.bucket,
                    object_name,
                    ExtraArgs={"ContentType": content_type},
                )
                # 返回URL
                url = f"{self.config.endpoint}/{self.config.bucket}/{object_name}"
                if self.config.use_ssl:
                    url = url.replace("http://", "https://")
            else:
                raise ValueError("存储客户端未初始化")

            logger.info(f"文件上传成功: {file_path} -> {object_name}")
            return url

        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            raise

    async def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "video/mp4"
    ) -> str:
        """上传字节数据到对象存储

        Args:
            data: 字节数据
            object_name: 对象名称
            content_type: 内容类型

        Returns:
            str: 文件的访问URL
        """
        if not self._initialized:
            await self.initialize()

        if self.config.type == "local":
            return await self._upload_bytes_to_local(data, object_name)

        try:
            if self.minio_client:
                # 使用 MinIO 客户端上传
                import io
                data_stream = io.BytesIO(data)
                self.minio_client.put_object(
                    self.config.bucket,
                    object_name,
                    data_stream,
                    len(data),
                    content_type=content_type,
                )
                # 返回预签名URL
                url = self.minio_client.presigned_get_object(
                    self.config.bucket,
                    object_name,
                    expires=7 * 24 * 3600,
                )
            elif self.s3_client:
                # 使用 S3 客户端上传
                import io
                data_stream = io.BytesIO(data)
                self.s3_client.upload_fileobj(
                    data_stream,
                    self.config.bucket,
                    object_name,
                    ExtraArgs={"ContentType": content_type},
                )
                url = f"{self.config.endpoint}/{self.config.bucket}/{object_name}"
                if self.config.use_ssl:
                    url = url.replace("http://", "https://")
            else:
                raise ValueError("存储客户端未初始化")

            logger.info(f"字节数据上传成功: {object_name}")
            return url

        except Exception as e:
            logger.error(f"字节数据上传失败: {e}")
            raise

    async def _upload_to_local(self, file_path: str, object_name: str) -> str:
        """上传文件到本地存储"""
        local_path = os.path.join("/app/storage", object_name)
        local_dir = os.path.dirname(local_path)

        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        with open(file_path, "rb") as src:
            with open(local_path, "wb") as dst:
                dst.write(src.read())

        logger.info(f"文件上传到本地存储: {file_path} -> {object_name}")
        return f"/storage/{object_name}"

    async def _upload_bytes_to_local(self, data: bytes, object_name: str) -> str:
        """上传字节数据到本地存储"""
        local_path = os.path.join("/app/storage", object_name)
        local_dir = os.path.dirname(local_path)

        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(data)

        logger.info(f"字节数据上传到本地存储: {object_name}")
        return f"/storage/{object_name}")

    async def download_file(self, object_name: str, file_path: str) -> bool:
        """从对象存储下载文件

        Args:
            object_name: 对象名称
            file_path: 本地文件路径

        Returns:
            bool: 下载是否成功
        """
        if not self._initialized:
            await self.initialize()

        if self.config.type == "local":
            try:
                src = os.path.join("/app/storage", object_name)
                with open(src, "rb") as f:
                    with open(file_path, "wb") as dst:
                        dst.write(f.read())
                return True
            except Exception as e:
                logger.error(f"本地文件下载失败: {e}")
                return False

        try:
            if self.minio_client:
                self.minio_client.fget_object(
                    self.config.bucket,
                    object_name,
                    file_path,
                )
            elif self.s3_client:
                self.s3_client.download_file(
                    self.config.bucket,
                    object_name,
                    file_path,
                )
            else:
                raise ValueError("存储客户端未初始化")

            logger.info(f"文件下载成功: {object_name} -> {file_path}")
            return True

        except Exception as e:
            logger.error(f"文件下载失败: {e}")
            return False

    async def delete_file(self, object_name: str) -> bool:
        """从对象存储删除文件

        Args:
            object_name: 对象名称

        Returns:
            bool: 删除是否成功
        """
        if not self._initialized:
            await self.initialize()

        if self.config.type == "local":
            try:
                local_path = os.path.join("/app/storage", object_name)
                if os.path.exists(local_path):
                    os.remove(local_path)
                logger.info(f"本地文件删除: {object_name}")
                return True
            except Exception as e:
                logger.error(f"本地文件删除失败: {e}")
                return False

        try:
            if self.minio_client:
                self.minio_client.remove_object(
                    self.config.bucket,
                    object_name,
                )
            elif self.s3_client:
                self.s3_client.delete_object(
                    Bucket=self.config.bucket,
                    Key=object_name,
                )
            else:
                raise ValueError("存储客户端未初始化")

            logger.info(f"文件删除: {object_name}")
            return True

        except Exception as e:
            logger.error(f"文件删除失败: {e}")
            return False

    def get_file_url(self, object_name: str) -> str:
        """获取文件的公开URL

        Args:
            object_name: 对象名称

        Returns:
            str: 文件URL
        """
        if self.config.type == "local":
            return f"/storage/{object_name}"

        if self.minio_client:
            return self.minio_client.presigned_get_object(
                self.config.bucket,
                object_name,
                expires=7 * 24 * 3600,
            )

        if self.s3_client:
            return f"{self.config.endpoint}/{self.config.bucket}/{object_name}"

        return ""


# 全局实例
_storage_service_instance: Optional[StorageService] = None


async def get_storage_service() -> StorageService:
    """获取存储服务实例（单例模式）"""
    global _storage_service_instance

    if _storage_service_instance is None:
        _storage_service_instance = StorageService()
        await _storage_service_instance.initialize()

    return _storage_service_instance


async def initialize_storage_service():
    """初始化存储服务"""
    await get_storage_service()
