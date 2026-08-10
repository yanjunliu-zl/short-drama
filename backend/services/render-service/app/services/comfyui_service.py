"""
本地 ComfyUI + Minimax H3 视频生成服务

与 SeedanceService 相同接口，可在 VideoProviderRouter 中并存。
ComfyUI API: POST /prompt → GET /history/{prompt_id}
"""
import logging
import asyncio
import time
import json
import uuid
import urllib.parse
from typing import Dict, Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── ComfyUI 默认 Minimax H3 workflow (image-to-video) ──
_DEFAULT_I2V_WORKFLOW = {
    "3": {
        "inputs": {
            "seed": 0,
            "steps": 20,
            "cfg": 4.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],          # Minimax H3 model node
            "positive": ["6", 0],        # CLIP text encode
            "negative": ["7", 0],
            "latent_image": ["5", 0],    # VAE encode output
        },
        "class_type": "KSampler",
    },
    "4": {
        "inputs": {"unet_name": "minimax_h3_fp16.safetensors"},
        "class_type": "UNETLoader",
    },
    "5": {
        "inputs": {
            "pixels": ["8", 0],         # Load image output
            "vae": ["9", 0],
        },
        "class_type": "VAEEncode",
    },
    "6": {
        "inputs": {
            "text": "PLACEHOLDER_POSITIVE",
            "clip": ["10", 0],
        },
        "class_type": "CLIPTextEncode",
    },
    "7": {
        "inputs": {
            "text": "PLACEHOLDER_NEGATIVE",
            "clip": ["10", 0],
        },
        "class_type": "CLIPTextEncode",
    },
    "8": {
        "inputs": {"image": "PLACEHOLDER_IMAGE_BASE64"},
        "class_type": "LoadImage",
    },
    "9": {
        "inputs": {"vae_name": "h3_vae.safetensors"},
        "class_type": "VAELoader",
    },
    "10": {
        "inputs": {
            "clip_name": "h3_clip.safetensors",
            "type": "h3",
        },
        "class_type": "CLIPLoader",
    },
}

# ── Minimax H3 I2V workflow (image-to-video, 首帧图引导) ──
# 基于 T2V workflow，加入 LoadImage 节点连接到 MiniMaxH3ImageToVideo.first_frame
_MINIMAX_H3_I2V_WORKFLOW = {
    "92": {
        "inputs": {"filename_prefix": "video/MiniMax_H3", "format": "auto", "codec": "auto", "video": ["105:91", 0]},
        "class_type": "SaveVideo", "_meta": {"title": "保存视频"}
    },
    "115": {
        "inputs": {"aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": 0.4, "multiple": 32},
        "class_type": "ResolutionSelector", "_meta": {"title": "分辨率选择器"}
    },
    "105:11": {
        "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
        "class_type": "VAELoader", "_meta": {"title": "加载VAE"}
    },
    "105:24": {
        "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
        "class_type": "VAELoader", "_meta": {"title": "加载VAE"}
    },
    "105:23": {
        "inputs": {"samples": ["105:14", 0], "vae": ["105:24", 0]},
        "class_type": "VAEDecodeAudio", "_meta": {"title": "VAE解码（音频）"}
    },
    "105:10": {
        "inputs": {"samples": ["105:14", 0], "vae": ["105:11", 0]},
        "class_type": "VAEDecode", "_meta": {"title": "VAE解码"}
    },
    "105:17": {
        "inputs": {"sampler_name": "res_multistep"},
        "class_type": "KSamplerSelect", "_meta": {"title": "K采样器选择"}
    },
    "105:9": {
        "inputs": {"scheduler": "simple", "steps": 20, "denoise": 1, "model": ["105:6", 0]},
        "class_type": "BasicScheduler", "_meta": {"title": "基本调度器"}
    },
    "105:14": {
        "inputs": {"noise": ["105:15", 0], "guider": ["105:16", 0], "sampler": ["105:17", 0],
                     "sigmas": ["105:9", 0], "latent_image": ["105:104", 1]},
        "class_type": "SamplerCustomAdvanced", "_meta": {"title": "自定义采样器（高级）"}
    },
    "105:16": {
        "inputs": {"model": ["105:6", 0], "conditioning": ["105:104", 0]},
        "class_type": "BasicGuider", "_meta": {"title": "基本引导器"}
    },
    "105:6": {
        "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"},
        "class_type": "UNETLoader", "_meta": {"title": "UNet加载器"}
    },
    "105:13": {
        "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"},
        "class_type": "CLIPLoader", "_meta": {"title": "加载CLIP"}
    },
    "105:15": {
        "inputs": {"noise_seed": 681714770551225},
        "class_type": "RandomNoise", "_meta": {"title": "随机噪波"}
    },
    "105:91": {
        "inputs": {"fps": 24, "bit_depth": 8, "images": ["105:10", 0], "audio": ["105:23", 0]},
        "class_type": "CreateVideo", "_meta": {"title": "创建视频"}
    },
    "105:104": {
        "inputs": {
            "prompt": "PLACEHOLDER_PROMPT", "width": ["115", 0], "height": ["115", 1],
            "length": ["105:107", 1], "clip": ["105:13", 0], "vae": ["105:11", 0],
            "first_frame": ["105:200", 0]
        },
        "class_type": "MiniMaxH3ImageToVideo", "_meta": {"title": "MiniMax H3 Image to Video"}
    },
    "105:107": {
        "inputs": {"expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17", "values.a": ["105:111", 0]},
        "class_type": "ComfyMathExpression", "_meta": {"title": "数学表达式"}
    },
    "105:111": {
        "inputs": {"value": 5},
        "class_type": "PrimitiveFloat", "_meta": {"title": "Float (duration)"}
    },
    "105:200": {
        "inputs": {"image": "PLACEHOLDER_IMAGE_URL"},
        "class_type": "LoadImage", "_meta": {"title": "加载首帧图"}
    },
}


class ComfyUIService:
    """ComfyUI 视频生成服务 — 调用本地 ComfyUI API"""

    def __init__(self):
        self._initialized = False
        self._base_url = settings.COMFYUI_API_URL.rstrip("/")
        self._enabled = settings.COMFYUI_ENABLED
        self._timeout = settings.COMFYUI_TIMEOUT

    async def initialize(self):
        if not self._enabled:
            logger.info("ComfyUI 未启用 (COMFYUI_ENABLED=false)")
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self._base_url}/system_stats")
                if r.status_code < 500:
                    self._initialized = True
                    logger.info("ComfyUI 连接成功: %s", self._base_url)
                    return
        except Exception as e:
            logger.warning("ComfyUI 连接失败 (%s): %s", self._base_url, e)
        self._initialized = False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._initialized

    # ═══════════════════════════════════════════
    # Flux.2 Dev 默认 txt2img workflow
    # ═══════════════════════════════════════════

    _FLUX_IMG_WORKFLOW = {
        "3": {
            "inputs": {"seed": 0, "steps": 20, "cfg": 3.5, "sampler_name": "euler",
                        "scheduler": "simple", "denoise": 1.0,
                        "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                        "latent_image": ["5", 0]},
            "class_type": "KSampler",
        },
        "4": {"inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"},
               "class_type": "UNETLoader"},
        "5": {"inputs": {"width": 1080, "height": 1920, "batch_size": 1},
               "class_type": "EmptyLatentImage"},
        "6": {"inputs": {"text": "PLACEHOLDER", "clip": ["11", 0]}, "class_type": "CLIPTextEncode"},
        "7": {"inputs": {"text": "", "clip": ["11", 0]}, "class_type": "CLIPTextEncode"},
        "8": {"inputs": {"samples": ["3", 0], "vae": ["9", 0]}, "class_type": "VAEDecode"},
        "9": {"inputs": {"vae_name": "full_encoder_small_decoder.safetensors"}, "class_type": "VAELoader"},
        "10": {"inputs": {"filename_prefix": "flux2", "images": ["8", 0]}, "class_type": "SaveImage"},
        "11": {"inputs": {"clip_name": "mistral_3_small_flux2_bf16.safetensors", "type": "flux2"},
                "class_type": "CLIPLoader"},
    }

    # ═══════════════════════════════════════════
    # Image generation — ComfyUI Flux.2 Dev
    # ═══════════════════════════════════════════

    async def generate_image_from_scene(self, scene_description: str = "", style: str = "",
                                         seed: int = -1, width: int = 1080, height: int = 1920,
                                         enhance_prompt: bool = False, **kwargs) -> Dict[str, Any]:
        """Same interface as SeedanceService — txt2img via ComfyUI Flux.2 Dev"""
        prompt = scene_description
        if style and style not in scene_description:
            prompt = f"{style}风格，{scene_description}"
        return await self.generate_image(prompt=prompt, width=width, height=height, seed=seed, **kwargs)

    async def generate_image(self, prompt: str, negative_prompt: str = "",
                              width: int = 1080, height: int = 1920,
                              seed: int = -1, **kwargs) -> Dict[str, Any]:
        """txt2img via ComfyUI Flux.2 Dev (同步轮询，仅 SSE/兼容路径使用)"""
        if not self.enabled:
            return {"success": False, "error": "ComfyUI not available"}

        result = await self.submit_image_prompt(prompt, negative_prompt, width, height, seed)
        if not result.get("success"):
            return result
        prompt_id = result["prompt_id"]

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for attempt in range(150):
                    await asyncio.sleep(2)
                    img_result = await self._check_image_result(client, prompt_id)
                    if img_result is not None:
                        elapsed = time.time() - t0
                        if img_result:
                            img_result["elapsed"] = elapsed
                            img_result["provider"] = "comfyui"
                            return img_result
                        return {"success": False, "error": "ComfyUI completed but no image output"}
                    await asyncio.sleep(0)  # actually, sleep is already 2s above
                logger.warning("ComfyUI Flux.2 img timeout (300s): %s", prompt_id)
                return {"success": False, "error": "ComfyUI Flux.2 timeout (300s)"}
        except httpx.HTTPError as e:
            logger.error("ComfyUI Flux.2 HTTP error polling: %s", e)
            return {"success": False, "error": f"ComfyUI Flux.2 HTTP error: {e}"}

    async def submit_image_prompt(self, prompt: str, negative_prompt: str = "",
                                   width: int = 1080, height: int = 1920,
                                   seed: int = -1) -> Dict[str, Any]:
        """提交 Flux.2 图片生成 prompt，仅提交不轮询，返回 {success, prompt_id}"""
        if not self.enabled:
            return {"success": False, "error": "ComfyUI not available"}
        try:
            workflow = json.loads(json.dumps(self._FLUX_IMG_WORKFLOW))
            workflow["6"]["inputs"]["text"] = prompt
            workflow["7"]["inputs"]["text"] = negative_prompt or "blurry, low quality, distorted"
            workflow["5"]["inputs"]["width"] = width
            workflow["5"]["inputs"]["height"] = height
            if seed >= 0:
                workflow["3"]["inputs"]["seed"] = seed

            client_id = str(uuid.uuid4())[:12]
            async with httpx.AsyncClient(timeout=30) as client:
                submit_resp = await client.post(
                    f"{self._base_url}/prompt",
                    json={"prompt": workflow, "client_id": client_id},
                )
                submit_resp.raise_for_status()
                prompt_id = submit_resp.json().get("prompt_id", "")
                if not prompt_id:
                    return {"success": False, "error": "ComfyUI returned no prompt_id"}
                logger.info("ComfyUI Flux.2 img prompt submitted: %s", prompt_id)
                return {"success": True, "prompt_id": prompt_id}
        except httpx.HTTPError as e:
            body = getattr(e, 'response', None)
            body_text = ""
            if body is not None:
                try:
                    body_text = body.text[:500]
                except Exception:
                    pass
            logger.error("ComfyUI Flux.2 submit HTTP error: %s body=%s", e, body_text)
            return {"success": False, "error": f"ComfyUI Flux.2 HTTP error: {e}"}
        except Exception as e:
            logger.error("ComfyUI Flux.2 submit error: %s", e)
            return {"success": False, "error": str(e)}

    async def get_image_result(self, prompt_id: str) -> Dict[str, Any]:
        """按 prompt_id 查询 ComfyUI 图片生成结果。
        返回 {success, status: 'processing'|'completed'|'error', image_url?, error?}
        """
        if not prompt_id:
            return {"success": False, "error": "prompt_id required"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                return await self._check_image_result(client, prompt_id) or \
                       {"success": True, "status": "processing"}
        except httpx.HTTPError as e:
            logger.error("ComfyUI get_image_result HTTP error: %s", e)
            return {"success": False, "error": str(e)}

    async def _check_image_result(self, client: httpx.AsyncClient, prompt_id: str) -> Optional[Dict[str, Any]]:
        """内部方法：检查 ComfyUI history，完成/出错返回 dict，仍在处理返回 None"""
        try:
            history_resp = await client.get(f"{self._base_url}/history/{prompt_id}")
            history_resp.raise_for_status()
            history = history_resp.json()
        except Exception:
            return None  # 网络抖动，返回 None 继续等

        prompt_data = history.get(prompt_id, {})
        status = prompt_data.get("status", {})

        if status.get("completed", False):
            image_url = self._extract_image_from_outputs(prompt_data.get("outputs", {}))
            if image_url:
                return {"success": True, "status": "completed", "image_url": image_url}
            return {"success": False, "status": "completed", "error": "ComfyUI completed but no image output"}

        if status.get("status_str", "") == "error":
            return {"success": False, "status": "error", "error": "ComfyUI execution error"}

        return None  # still processing

    @staticmethod
    def _extract_image_from_outputs(outputs: dict) -> str:
        """Extract image URL from ComfyUI output nodes, return proxy URL."""
        import urllib.parse
        for node_output in outputs.values():
            if isinstance(node_output, dict):
                for media_list in node_output.values():
                    if isinstance(media_list, list):
                        for item in media_list:
                            if isinstance(item, dict):
                                fname = item.get("filename", "")
                                subfolder = item.get("subfolder", "")
                                ftype = item.get("type", "")
                                if ftype == "output" and fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
                                    params = urllib.parse.urlencode({
                                        "filename": fname, "subfolder": subfolder, "type": ftype,
                                    })
                                    return f"/api/v1/render/comfyui-proxy?{params}"
        return ""

    # ═══════════════════════════════════════════
    # Video generation (image-to-video)
    # ═══════════════════════════════════════════

    async def generate_video(
        self,
        image_url: str = "",
        prompt: str = "",
        negative_prompt: str = "blurry, low quality, distorted, watermark",
        duration: float = 5.0,
        width: int = 1080,
        height: int = 1920,
        seed: int = -1,
        user_id: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """图片转视频 — ComfyUI Minimax H3 workflow"""
        if not self.enabled:
            return {"success": False, "error": "ComfyUI not available"}

        t0 = time.time()
        try:
            # 1. Build workflow — inject prompt + image
            workflow = json.loads(json.dumps(_MINIMAX_H3_I2V_WORKFLOW))
            # Inject prompt into MiniMaxH3ImageToVideo node
            workflow["105:104"]["inputs"]["prompt"] = prompt
            # Inject image URL into LoadImage node — convert proxy URLs to direct
            # ComfyUI URLs since LoadImage can't resolve the render-service proxy
            if image_url:
                workflow["105:200"]["inputs"]["image"] = await self._resolve_load_url(image_url)
            # Set duration
            workflow["105:111"]["inputs"]["value"] = float(duration)
            # Set seed
            if seed >= 0:
                workflow["105:15"]["inputs"]["noise_seed"] = seed
            # Override aspect ratio if provided (e.g. "9:16 (Portrait Widescreen)", "16:9 (Widescreen)")
            ratio = kwargs.get("ratio")
            if ratio:
                workflow["115"]["inputs"]["aspect_ratio"] = ratio

            # 2. Submit prompt to ComfyUI
            task_id = str(uuid.uuid4())[:12]
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                submit_resp = await client.post(
                    f"{self._base_url}/prompt",
                    json={"prompt": workflow, "client_id": task_id},
                )
                submit_resp.raise_for_status()
                submit_data = submit_resp.json()
                prompt_id = submit_data.get("prompt_id", "")
                # Log full response for debugging workflow issues
                if not prompt_id:
                    logger.error("ComfyUI /prompt response (no prompt_id): %s", submit_data)

                if not prompt_id:
                    return {"success": False, "error": f"ComfyUI returned no prompt_id: {submit_data}"}

                logger.info("ComfyUI prompt submitted: %s task=%s", prompt_id, task_id)

                # 3. Poll for result (max 120 polls × 3s = 360s)
                for attempt in range(120):
                    await asyncio.sleep(3)
                    try:
                        history_resp = await client.get(
                            f"{self._base_url}/history/{prompt_id}"
                        )
                        history_resp.raise_for_status()
                        history = history_resp.json()
                    except Exception:
                        continue

                    prompt_data = history.get(prompt_id, {})
                    status = prompt_data.get("status", {})

                    if status.get("completed", False):
                        # Extract video from outputs
                        video_url = self._extract_video_from_outputs(
                            prompt_data.get("outputs", {})
                        )
                        elapsed = time.time() - t0
                        if video_url:
                            logger.info("ComfyUI video done: %s elapsed=%.1fs", prompt_id, elapsed)
                            return {
                                "success": True,
                                "status": "completed",
                                "video_url": video_url,
                                "prompt_id": prompt_id,
                                "elapsed": elapsed,
                                "provider": "comfyui",
                            }
                        return {
                            "success": False,
                            "error": f"ComfyUI completed but no video output, elapsed={elapsed:.1f}s",
                        }

                    if status.get("status_str", "") == "error":
                        return {
                            "success": False,
                            "error": f"ComfyUI execution error: {json.dumps(status)}",
                        }

                return {"success": False, "error": "ComfyUI timeout (360s)"}

        except httpx.HTTPError as e:
            body = getattr(e, 'response', None)
            body_text = ""
            if body is not None:
                try:
                    body_text = body.text[:500]
                except Exception:
                    pass
            logger.error("ComfyUI video HTTP error: %s body=%s", e, body_text)
            return {"success": False, "error": f"ComfyUI HTTP error: {e} (body={body_text})"}
        except Exception as e:
            logger.error("ComfyUI unexpected error: %s", e)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _extract_video_from_outputs(outputs: dict) -> str:
        """Extract video URL/file from ComfyUI output nodes, return proxy URL."""
        for node_id, node_output in outputs.items():
            if isinstance(node_output, dict):
                for media_list in node_output.values():
                    if isinstance(media_list, list):
                        for item in media_list:
                            if isinstance(item, dict):
                                fname = item.get("filename", "")
                                subfolder = item.get("subfolder", "")
                                ftype = item.get("type", "")
                                if fname.endswith((".mp4", ".webm", ".gif", ".mov")):
                                    import urllib.parse
                                    params = urllib.parse.urlencode({
                                        "filename": fname, "subfolder": subfolder, "type": ftype or "output",
                                    })
                                    return f"/api/v1/render/comfyui-proxy?{params}"
        return ""

    async def _resolve_load_url(self, url: str) -> str:
        """将各种图像 URL 转为 ComfyUI LoadImage 节点可接受的文件名。

        ComfyUI 的 LoadImage 只接受相对于 input/ 目录的文件名。
        因此需要：下载图片 → 上传到 ComfyUI input 目录 → 返回文件名。
        """
        if not url:
            return url
        # 如果看起来像是一个本地文件名（不含协议和路径分隔符），直接返回
        if not url.startswith(('http://', 'https://', 'data:', '/', '.')):
            return url

        try:
            # 1. 确定下载 URL
            download_url = url
            if not url.startswith('http://') and not url.startswith('https://'):
                if url.startswith('/api/v1/render/comfyui-proxy?'):
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    filename = params.get('filename', [''])[0]
                    subfolder = params.get('subfolder', [''])[0]
                    ftype = params.get('type', ['output'])[0]
                    if filename:
                        download_url = (f"http://host.docker.internal:8188/view?"
                                        f"filename={urllib.parse.quote(filename)}"
                                        f"&subfolder={urllib.parse.quote(subfolder)}"
                                        f"&type={urllib.parse.quote(ftype)}")
                    else:
                        return url
                else:
                    return url

            # 2. 下载图片
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(download_url)
                resp.raise_for_status()
                img_bytes = resp.content

            # 3. 上传到 ComfyUI input 目录
            upload_name = f"i2v_{uuid.uuid4().hex[:12]}.png"
            async with httpx.AsyncClient(timeout=30) as client:
                files = {'image': (upload_name, img_bytes, 'image/png')}
                upload_resp = await client.post(
                    f"{self._base_url}/upload/image",
                    files=files,
                )
                upload_resp.raise_for_status()
                upload_result = upload_resp.json()
                # ComfyUI 返回 {"name": "i2v_xxx.png", "subfolder": "", "type": "input"}
                saved_name = upload_result.get('name', upload_name)
                logger.info(f"Uploaded image to ComfyUI input: {saved_name}")
                return saved_name

        except Exception as e:
            logger.warning(f"Failed to resolve image URL {url[:80]}: {e}")
            return url  # fallback

    async def generate_video_from_image(
        self, image_url: str = "", prompt: str = "", **kwargs
    ) -> Dict[str, Any]:
        """Convenience wrapper — same signature as SeedanceService"""
        return await self.generate_video(image_url=image_url, prompt=prompt, **kwargs)

    async def close(self):
        pass
