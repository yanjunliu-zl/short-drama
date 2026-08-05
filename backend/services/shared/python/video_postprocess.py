"""
FFmpeg Video Post-Processing — 红果短剧 & 快手短剧 Platform Compliance.

Converts AI-generated video to platform submission standards:
  - 16:9 → 9:16 vertical (smart crop or AI outpainting)
  - 720p → 1080p upscale
  - 24fps → 30fps frame rate conversion
  - Silent audio track injection (placeholder for TTS)
  - Metadata injection (title, episode, creator)

Usage:
  processor = VideoPostProcessor()
  result = await processor.process(input_path, output_path,
      aspect="9:16", fps=30, upscale=True)
"""
import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoSpec:
    """Target video specification for platform submission."""
    width: int = 1080
    height: int = 1920       # 9:16 vertical
    fps: int = 30
    codec: str = "libx264"   # H.264
    preset: str = "medium"   # Encode speed/quality tradeoff
    crf: int = 18            # Quality (lower=better, 18=visually lossless)
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"
    pixel_format: str = "yuv420p"  # Maximum compatibility


@dataclass
class ProcessingResult:
    """Post-processing result."""
    input_path: str
    output_path: str
    original_spec: dict = field(default_factory=dict)
    target_spec: dict = field(default_factory=dict)
    success: bool = False
    duration_ms: int = 0
    error: str = ""


class VideoPostProcessor:
    """FFmpeg-based video post-processing for platform compliance.

    红果短剧 requirements:
      - 9:16 vertical aspect ratio (1080×1920 or 720×1280)
      - 25/30fps
      - H.264/AAC, 2-8 Mbps
      - Watermark-free
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg = ffmpeg_bin
        self.target = VideoSpec()

    # ── Public API ──

    async def process(self, input_path: str, output_path: str,
                      aspect: str = "9:16",
                      fps: int = 30,
                      upscale_to_1080p: bool = True,
                      add_audio_placeholder: bool = True,
                      title: str = "",
                      episode: int = 0) -> ProcessingResult:
        """Convert video to platform-compliant format.

        Args:
            input_path: Source video (from Seedance API).
            output_path: Output path for compliant video.
            aspect: Target aspect ratio ("9:16" vertical or "16:9" horizontal).
            fps: Target frame rate (25 or 30).
            upscale_to_1080p: If True, upscale to 1080p.
            add_audio_placeholder: If True, add silent audio track.
            title: Series title for metadata.
            episode: Episode number.

        Returns:
            ProcessingResult with status and metadata.
        """
        import time
        t0 = time.time()
        result = ProcessingResult(
            input_path=input_path,
            output_path=output_path,
        )

        if aspect == "9:16":
            self.target.width = 1080
            self.target.height = 1920
        else:
            self.target.width = 1920
            self.target.height = 1080

        self.target.fps = fps

        # Build ffmpeg command
        filters = []
        output_args = []

        # 1. Scale + Aspect Ratio conversion
        if upscale_to_1080p:
            filters.append(
                f"scale={self.target.width}:{self.target.height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={self.target.width}:{self.target.height}:"
                f"(ow-iw)/2:(oh-ih)/2"
            )
        else:
            filters.append(f"scale={self.target.width}:{self.target.height}")

        # 2. Frame rate conversion
        if fps:
            filters.append(f"fps=fps={fps}")

        # 3. Pixel format
        filters.append(f"format={self.target.pixel_format}")

        filter_complex = ",".join(filters)

        # Build full command
        cmd = [
            self.ffmpeg,
            "-i", input_path,
            "-vf", filter_complex,
            "-c:v", self.target.codec,
            "-preset", self.target.preset,
            "-crf", str(self.target.crf),
            "-pix_fmt", self.target.pixel_format,
        ]

        # Audio: silent placeholder for TTS
        if add_audio_placeholder:
            cmd.extend([
                "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:a", self.target.audio_codec,
                "-b:a", self.target.audio_bitrate,
                "-shortest",
            ])

        # Metadata
        if title:
            cmd.extend(["-metadata", f"title={title}"])
        if episode > 0:
            cmd.extend(["-metadata", f"episode={episode}"])

        cmd.extend([
            "-movflags", "+faststart",  # Web-optimized
            "-y",                        # Overwrite output
            output_path,
        ])

        logger.debug(f"FFmpeg: {' '.join(cmd[:8])}...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                err = stderr.decode()[:500] if stderr else "unknown"
                result.error = err
                logger.error(f"FFmpeg failed (rc={proc.returncode}): {err}")
            else:
                result.success = True
                # Get output file info
                probe_cmd = [
                    self.ffmpeg, "-i", output_path,
                    "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams",
                ]
                probe = await asyncio.create_subprocess_exec(
                    *probe_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                pout, _ = await probe.communicate()
                if pout:
                    try:
                        result.original_spec = json.loads(pout)
                    except json.JSONDecodeError:
                        pass
        except FileNotFoundError:
            result.error = "ffmpeg binary not found — install ffmpeg"
            logger.warning(result.error)
        except Exception as e:
            result.error = str(e)

        result.duration_ms = int((time.time() - t0) * 1000)
        return result

    # ── Batch Processing ──

    async def process_batch(self, input_paths: list, output_dir: str,
                            **kwargs) -> list:
        """Process multiple videos in parallel (max 4 concurrent)."""
        sem = asyncio.Semaphore(4)
        tasks = []
        for i, path in enumerate(input_paths):
            out = os.path.join(output_dir, f"episode_{i+1:03d}.mp4")
            tasks.append(self._process_with_sem(sem, path, out, **kwargs))
        return await asyncio.gather(*tasks)

    async def _process_with_sem(self, sem, input_path, output_path, **kwargs):
        async with sem:
            return await self.process(input_path, output_path, **kwargs)


# ── Audio Verification ──

class AudioVerifier:
    """Verify that Seedance-generated video contains an audio track.

    Seedance 2.0 natively generates audio from the video prompt.
    This module validates the output for platform compliance.
    """

    @staticmethod
    async def has_audio(video_path: str) -> bool:
        """Check if video file contains an audio stream."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                video_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            return b"audio" in stdout
        except Exception:
            return False

    @staticmethod
    async def get_audio_info(video_path: str) -> dict:
        """Get audio stream metadata from video file."""
        try:
            import json
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-select_streams", "a",
                video_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            data = json.loads(stdout)
            streams = data.get("streams", [])
            if streams:
                s = streams[0]
                return {
                    "codec": s.get("codec_name", "unknown"),
                    "channels": s.get("channels", 0),
                    "sample_rate": s.get("sample_rate", 0),
                    "bitrate": s.get("bit_rate", "unknown"),
                }
        except Exception:
            pass
        return {}

