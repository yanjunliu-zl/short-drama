"""
Google Veo 视频生成服务 — 对标 Seedance，为海外市场提供视频生成能力。

Veo 2 是 Google DeepMind 的视频生成模型，通过 Vertex AI API 访问。
支持 text-to-video 和 image-to-video，在物理一致性、长视频生成方面领先。

API 文档: https://cloud.google.com/vertex-ai/generative-ai/docs/video/overview

集成方式:
  - 与 SeedanceService 相同的接口签名 (generate_video, generate_image)
  - 可在 VideoProviderRouter 中与 Seedance 互备
  - 通过 GOOGLE_APPLICATION_CREDENTIALS 认证
"""
import logging
import asyncio
import time
import base64
import json
import uuid
from typing import Dict, Any, Optional, Tuple

import httpx
from PIL import Image
import io

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Veo API 配置 ──
_VEO_API_VERSION = "v1"
_VEO_MODEL = "veo-2.0-generate-preview"  # Veo 2 preview
_VEO_IMAGE_MODEL = "imagen-3.0-generate-001"  # Imagen 3 for image generation

# 内容审核关键词
_CONTENT_FILTER_KEYWORDS = [
    "content moderation", "safety filter", "blocked",
    "inappropriate", "policy violation",
]

# Veo 支持的分辨率和时长
_VEO_RESOLUTIONS = {
    "1080p": "1920x1080",
    "720p": "1280x720",
    "portrait": "1080x1920",     # 竖屏短剧
    "square": "1080x1080",
}


class VeoService:
    """Google Veo AI 视频生成服务。

    环境变量:
        GOOGLE_APPLICATION_CREDENTIALS: 服务账号 JSON 密钥路径
        GOOGLE_CLOUD_PROJECT: GCP 项目 ID
        GOOGLE_CLOUD_LOCATION: Vertex AI 区域 (默认: us-central1)
        VEO_ENABLED: 是否启用 Veo (默认: false)
    """

    def __init__(self):
        self._project = getattr(settings, 'GOOGLE_CLOUD_PROJECT', None) or ""
        self._location = getattr(settings, 'GOOGLE_CLOUD_LOCATION', None) or "us-central1"
        self._enabled = getattr(settings, 'VEO_ENABLED', None) or False
        self._api_endpoint = (
            f"https://{self._location}-aiplatform.googleapis.com"
            f"/v1/projects/{self._project}/locations/{self._location}"
            f"/publishers/google/models/{_VEO_MODEL}:predict"
        )
        self._image_endpoint = (
            f"https://{self._location}-aiplatform.googleapis.com"
            f"/v1/projects/{self._project}/locations/{self._location}"
            f"/publishers/google/models/{_VEO_IMAGE_MODEL}:predict"
        )
        self.timeout = getattr(settings, 'VEO_TIMEOUT', 600)
        self._initialized = False
        self._client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

        # Retry config
        self._max_retries: int = 3
        self._retry_delay: float = 3.0

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._project)

    async def initialize(self):
        """Initialize Veo service — auth + httpx client."""
        if self._initialized:
            return
        try:
            if not self.enabled:
                logger.info("Veo: not enabled (set VEO_ENABLED=true and GOOGLE_CLOUD_PROJECT)")
                self._initialized = True
                return

            logger.info(f"Veo: initializing (project={self._project}, location={self._location})")
            self._client = httpx.AsyncClient(timeout=self.timeout)
            await self._refresh_token()
            self._initialized = True
            logger.info("Veo: initialized ✓")
        except Exception as e:
            logger.error(f"Veo: init failed: {e}")
            self._initialized = True  # Mark as initialized even if failed (graceful degradation)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._initialized = False

    # ═══════════════════════════════════════════════════════════
    # Authentication
    # ═══════════════════════════════════════════════════════════

    async def _refresh_token(self):
        """Get OAuth2 access token from service account credentials."""
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if not self._project and project:
                self._project = project

            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            self._access_token = credentials.token
            self._token_expiry = time.time() + 1800  # 30 min
            logger.debug("Veo: access token refreshed")
        except ImportError:
            logger.warning("Veo: google-auth not installed — using API key fallback")
            # Fallback: use API key from env
            api_key = getattr(settings, 'GOOGLE_API_KEY', None) or ""
            if api_key:
                self._access_token = api_key
                self._token_expiry = time.time() + 3600
        except Exception as e:
            logger.error(f"Veo: auth failed: {e}")
            raise

    async def _ensure_token(self):
        """Ensure access token is valid."""
        if not self._access_token or time.time() > self._token_expiry - 60:
            await self._refresh_token()

    # ═══════════════════════════════════════════════════════════
    # Image Generation (via Imagen 3)
    # ═══════════════════════════════════════════════════════════

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "写实风格",
        width: int = 1920,
        height: int = 1080,
        user_id: str = "",
        db_session=None,
    ) -> Dict[str, Any]:
        """Generate image via Google Imagen 3.

        Same interface as SeedanceService.generate_image for drop-in compatibility.
        """
        if not self.enabled or not self._client:
            logger.warning("Veo: image generation skipped (not enabled)")
            return {"success": False, "error": "Veo not enabled", "image_url": ""}

        await self._ensure_token()
        t0 = time.time()

        try:
            body = {
                "instances": [{
                    "prompt": prompt,
                }],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": f"{width}:{height}" if width and height else "16:9",
                    "negativePrompt": negative_prompt or "",
                },
            }

            response = await self._client.post(
                self._image_endpoint,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()

            # Extract image
            predictions = data.get("predictions", [])
            if predictions:
                img_bytes = base64.b64decode(predictions[0].get("bytesBase64Encoded", ""))
                image_url = await self._upload_to_storage(
                    img_bytes, "image/png", "image", user_id, db_session
                )
                elapsed = time.time() - t0
                logger.info(f"Veo: image generated ({width}x{height}, {elapsed:.1f}s)")
                return {"success": True, "image_url": image_url, "provider": "veo-imagen"}

            return {"success": False, "error": "No prediction returned", "image_url": ""}

        except Exception as e:
            logger.error(f"Veo: image generation failed: {e}")
            # Fallback: return error, caller should handle
            return {"success": False, "error": str(e), "image_url": ""}

    # ═══════════════════════════════════════════════════════════
    # Video Generation (Veo 2)
    # ═══════════════════════════════════════════════════════════

    async def generate_video(
        self,
        image_url: str = "",
        prompt: str = "",
        duration: float = 5.0,
        resolution: str = "portrait",
        fps: int = 24,
        user_id: str = "",
        db_session=None,
    ) -> Dict[str, Any]:
        """Generate video via Google Veo 2.

        Supports both text-to-video (no image_url) and image-to-video (with image_url).

        Args:
            image_url: Optional source image URL for i2v mode.
            prompt: Text prompt describing the video content.
            duration: Video duration in seconds (max 60s for Veo 2).
            resolution: "1080p", "720p", "portrait", or "square".
            fps: Frames per second (24 or 30).
            user_id: User ID for storage.
            db_session: DB session for media asset tracking.

        Returns:
            {"success": bool, "video_url": str, "provider": "veo", "task_id": str}
        """
        if not self.enabled or not self._client:
            logger.warning("Veo: video generation skipped (not enabled)")
            return {"success": False, "error": "Veo not enabled", "video_url": ""}

        await self._ensure_token()
        t0 = time.time()

        try:
            # Build the Veo 2 request
            instance = {"prompt": prompt}

            if image_url:
                # Image-to-video mode
                image_bytes = await self._download_image(image_url)
                if image_bytes:
                    instance["image"] = {
                        "bytesBase64Encoded": base64.b64encode(image_bytes).decode(),
                    }

            params = {
                "durationSeconds": min(int(duration), 60),
                "aspectRatio": "9:16" if resolution == "portrait" else (
                    "16:9" if resolution in ("1080p", "720p") else "1:1"
                ),
                "frameRate": fps,
            }

            body = {
                "instances": [instance],
                "parameters": params,
            }

            logger.info(
                f"Veo: submitting video generation (duration={duration}s, "
                f"resolution={resolution}, has_image={bool(image_url)})"
            )

            # Submit
            response = await self._client.post(
                self._api_endpoint,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()

            # Veo returns the video directly or via a polling job
            predictions = data.get("predictions", [])
            if predictions and predictions[0].get("bytesBase64Encoded"):
                # Synchronous response (short videos)
                video_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                video_url = await self._upload_to_storage(
                    video_bytes, "video/mp4", "video", user_id, db_session
                )
                elapsed = time.time() - t0
                logger.info(f"Veo: video generated (sync, {elapsed:.1f}s)")
                return {
                    "success": True,
                    "video_url": video_url,
                    "provider": "veo",
                    "elapsed_ms": int(elapsed * 1000),
                }

            # Async: poll for completion
            task_id = data.get("name", str(uuid.uuid4()))
            logger.info(f"Veo: async job submitted, task_id={task_id}")
            video_url = await self._poll_veo_job(task_id)

            elapsed = time.time() - t0
            return {
                "success": bool(video_url),
                "video_url": video_url or "",
                "provider": "veo",
                "task_id": task_id,
                "elapsed_ms": int(elapsed * 1000),
            }

        except Exception as e:
            logger.error(f"Veo: video generation failed: {e}")
            return {"success": False, "error": str(e), "video_url": ""}

    async def generate_video_from_image(
        self, image_url: str, prompt: str, **kwargs
    ) -> Dict[str, Any]:
        """Image-to-video via Veo. Same signature as SeedanceService."""
        return await self.generate_video(image_url=image_url, prompt=prompt, **kwargs)

    # ═══════════════════════════════════════════════════════════
    # Polling
    # ═══════════════════════════════════════════════════════════

    async def _poll_veo_job(self, task_id: str, max_wait: int = 300) -> Optional[str]:
        """Poll Veo async generation job until completion."""
        poll_endpoint = (
            f"https://{self._location}-aiplatform.googleapis.com"
            f"/v1/{task_id}"
        )
        deadline = time.time() + max_wait
        poll_interval = 5.0

        while time.time() < deadline:
            try:
                await self._ensure_token()
                response = await self._client.get(
                    poll_endpoint,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                response.raise_for_status()
                data = response.json()

                state = data.get("state", "")
                if state == "JOB_STATE_SUCCEEDED":
                    # Extract video bytes
                    predictions = data.get("predictions", [])
                    if predictions:
                        video_b64 = predictions[0].get("bytesBase64Encoded", "")
                        if video_b64:
                            video_bytes = base64.b64decode(video_b64)
                            return await self._upload_to_storage(
                                video_bytes, "video/mp4", "video", "", None
                            )
                elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
                    logger.error(f"Veo: job {task_id} failed: {data.get('error', {})}")
                    return None

                await asyncio.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 30.0)

            except Exception as e:
                logger.warning(f"Veo: poll error: {e}")
                await asyncio.sleep(poll_interval)

        logger.error(f"Veo: job {task_id} timed out after {max_wait}s")
        return None

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL for i2v."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            logger.warning(f"Veo: failed to download image from {url[:80]}: {e}")
            return None

    async def _upload_to_storage(
        self, data: bytes, content_type: str, media_type: str,
        user_id: str = "", db_session=None,
    ) -> str:
        """Upload generated media to object storage (MinIO/Ceph)."""
        from app.services.storage_service import get_storage_service
        try:
            storage = await get_storage_service()
            import tempfile, os
            suffix = ".mp4" if "video" in content_type else ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            object_name = f"veo/{media_type}/{uuid.uuid4()}{suffix}"
            url = storage.upload_file(
                file_path=tmp_path,
                object_name=object_name,
                content_type=content_type,
            )
            os.unlink(tmp_path)
            return url or ""
        except Exception as e:
            logger.warning(f"Veo: storage upload failed: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════
# Video Provider Router — locale-aware video generation
# ═══════════════════════════════════════════════════════════════

class VideoProviderRouter:
    """Video generation provider router — locale-aware routing.

    Routes:
      - zh-CN → Seedance (ByteDance, best Chinese content)
      - en-US / es-MX → Veo (Google, best English/Western content)
      - ar-SA / tr-TR → Veo (Google, better multilingual support)
      - ja-JP / ko-KR → Seedance (closer to Asian aesthetics)
      - Other → Seedance (default)
    """

    _LOCALE_PROVIDER: Dict[str, str] = {
        "zh-CN": "seedance",
        "en-US": "veo",
        "en-GB": "veo",
        "es-MX": "veo",
        "es-ES": "veo",
        "ar-SA": "veo",
        "tr-TR": "veo",
        "ja-JP": "seedance",
        "ko-KR": "seedance",
        "th-TH": "seedance",
    }

    def __init__(self, seedance_service=None, veo_service=None):
        self._seedance = seedance_service
        self._veo = veo_service

    def get_provider(self, target_locale: str = "zh-CN") -> str:
        """Get preferred video provider for locale."""
        return self._LOCALE_PROVIDER.get(target_locale, "seedance")

    async def generate_video(
        self,
        target_locale: str = "zh-CN",
        image_url: str = "",
        prompt: str = "",
        duration: float = 5.0,
        resolution: str = "portrait",
        user_id: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate video using the best provider for the target locale.

        Falls back to the other provider if the preferred one fails.
        """
        provider = self.get_provider(target_locale)
        primary = self._seedance if provider == "seedance" else self._veo
        fallback = self._veo if provider == "seedance" else self._seedance
        primary_name = provider
        fallback_name = "veo" if provider == "seedance" else "seedance"

        # Try primary
        if primary and getattr(primary, '_initialized', True):
            try:
                result = await primary.generate_video(
                    image_url=image_url, prompt=prompt,
                    duration=duration, user_id=user_id, **kwargs,
                )
                if result.get("success") or result.get("video_url"):
                    result["provider"] = primary_name
                    result["routed_by"] = f"locale={target_locale}"
                    return result
                logger.warning(
                    f"VideoRouter: {primary_name} returned no video, "
                    f"trying {fallback_name}"
                )
            except Exception as e:
                logger.warning(
                    f"VideoRouter: {primary_name} failed: {e}, "
                    f"trying {fallback_name}"
                )

        # Try fallback
        if fallback and getattr(fallback, '_initialized', True):
            try:
                result = await fallback.generate_video(
                    image_url=image_url, prompt=prompt,
                    duration=duration, user_id=user_id, **kwargs,
                )
                result["provider"] = fallback_name
                result["routed_by"] = f"locale={target_locale} (fallback from {primary_name})"
                return result
            except Exception as e:
                logger.error(f"VideoRouter: both providers failed: {e}")

        return {
            "success": False,
            "error": "No video provider available",
            "video_url": "",
        }
