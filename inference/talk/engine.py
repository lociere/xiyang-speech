"""MuseTalk inference engine, refactored from scripts/inference.py for use inside a FastAPI worker.

The upstream inference script mixes argparse, a YAML task loop and model loading. This
module exposes a small ``MuseTalkEngine`` class that loads the models once and exposes a
``generate`` method taking a single image/video + audio pair.
"""
import copy
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import torch
from transformers import WhisperModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MUSETALK_ROOT = PROJECT_ROOT / "third_party" / "MuseTalk"

# MuseTalk relies on many hardcoded relative paths ("models/...", "./musetalk/utils/..."),
# so the process working directory must be the MuseTalk repository root.
os.chdir(MUSETALK_ROOT)
sys.path.insert(0, str(MUSETALK_ROOT))
sys.path.insert(0, str(MUSETALK_ROOT / "musetalk" / "utils"))

# Importing preprocessing immediately loads the mmpose/DWPose and S3FD models.
from musetalk.utils.blending import get_image  # noqa: E402
from musetalk.utils.face_parsing import FaceParsing  # noqa: E402
from musetalk.utils.audio_processor import AudioProcessor  # noqa: E402
from musetalk.utils.utils import (  # noqa: E402
    datagen,
    get_file_type,
    get_video_fps,
    load_all_model,
)
from musetalk.utils.preprocessing import (  # noqa: E402
    coord_placeholder,
    fa,
    get_landmark_and_bbox,
)


def validate_portrait(image_path: str) -> None:
    """Reject unreadable images and unsupported faces before loading speech models."""
    frame = cv2.imread(image_path)
    if frame is None:
        raise ValueError("无法读取图片，请上传有效的 JPG 或 PNG 图片。")
    detections = fa.get_detections_for_batch(np.asarray([frame]))
    if not detections or all(box is None for box in detections):
        raise ValueError(
            "未检测到可用人脸，请上传清晰的单人正脸人像。"
            "卡通、非人类角色或脸部遮挡可能无法被 MuseTalk 识别。"
        )


class MuseTalkEngine:
    """Loads MuseTalk once and generates lip-synced videos from image/video + audio."""

    def __init__(
        self,
        version: str = "v15",
        use_float16: bool = True,
        gpu_id: int = 0,
        vae_type: str = "sd-vae",
        whisper_dir: str = "models/whisper",
        left_cheek_width: int = 90,
        right_cheek_width: int = 90,
    ) -> None:
        if version not in ("v1", "v15"):
            raise ValueError(f"unsupported version: {version}")

        self.version = version
        self.device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")

        if version == "v15":
            unet_model_path = "models/musetalkV15/unet.pth"
            unet_config = "models/musetalkV15/musetalk.json"
        else:
            unet_model_path = "models/musetalk/pytorch_model.bin"
            unet_config = "models/musetalk/musetalk.json"

        self.vae, self.unet, self.pe = load_all_model(
            unet_model_path=unet_model_path,
            vae_type=vae_type,
            unet_config=unet_config,
            device=self.device,
        )
        self.timesteps = torch.tensor([0], device=self.device)

        if use_float16:
            self.pe = self.pe.half()
            self.vae.vae = self.vae.vae.half()
            self.unet.model = self.unet.model.half()

        self.pe = self.pe.to(self.device)
        self.vae.vae = self.vae.vae.to(self.device)
        self.unet.model = self.unet.model.to(self.device)

        self.audio_processor = AudioProcessor(feature_extractor_path=whisper_dir)
        weight_dtype = self.unet.model.dtype
        self.whisper = WhisperModel.from_pretrained(whisper_dir)
        self.whisper = self.whisper.to(device=self.device, dtype=weight_dtype).eval()
        self.whisper.requires_grad_(False)

        if version == "v15":
            self.fp = FaceParsing(
                left_cheek_width=left_cheek_width,
                right_cheek_width=right_cheek_width,
            )
        else:
            self.fp = FaceParsing()

    @torch.no_grad()
    def generate(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        fps: int = 25,
        batch_size: int = 8,
        extra_margin: int = 10,
        parsing_mode: str = "jaw",
        audio_padding_length_left: int = 2,
        audio_padding_length_right: int = 2,
        progress_cb=None,
    ) -> str:
        """Generate a lip-synced video from an image/video and an audio file.

        Returns the absolute path to the generated mp4 (same as ``output_path``).
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # --- Resolve input frames -------------------------------------------------
        file_type = get_file_type(image_path)
        if file_type == "video":
            temp_frame_dir = tempfile.mkdtemp(prefix="musetalk_frames_")
            cmd = ["ffmpeg", "-v", "fatal", "-i", image_path, "-start_number", "0",
                   f"{temp_frame_dir}/%08d.png"]
            subprocess.run(cmd, check=True)
            input_img_list = sorted(glob.glob(os.path.join(temp_frame_dir, "*.[jpJP][pnPN]*[gG]")))
            fps = int(get_video_fps(image_path))
        elif file_type == "image":
            input_img_list = [image_path]
            temp_frame_dir = None
        else:
            raise ValueError(f"{image_path} is not a supported image or video file")

        # --- Audio features -------------------------------------------------------
        whisper_input_features, librosa_length = self.audio_processor.get_audio_feature(audio_path)
        if whisper_input_features is None:
            raise ValueError(f"audio file not found or unreadable: {audio_path}")

        whisper_chunks = self.audio_processor.get_whisper_chunk(
            whisper_input_features,
            self.device,
            self.unet.model.dtype,
            self.whisper,
            librosa_length,
            fps=fps,
            audio_padding_length_left=audio_padding_length_left,
            audio_padding_length_right=audio_padding_length_right,
        )

        # --- Face crop + VAE latents ---------------------------------------------
        try:
            coord_list, frame_list = get_landmark_and_bbox(input_img_list, 0)
        except ZeroDivisionError as exc:
            raise ValueError(
                "人脸定位失败，请使用清晰的单人正脸人像；当前图片可能不适合 MuseTalk。"
            ) from exc

        input_latent_list = []
        for bbox, frame in zip(coord_list, frame_list):
            if bbox == coord_placeholder:
                continue
            x1, y1, x2, y2 = bbox
            if self.version == "v15":
                y2 = y2 + extra_margin
                y2 = min(y2, frame.shape[0])
            crop_frame = frame[y1:y2, x1:x2]
            crop_frame = cv2.resize(crop_frame, (256, 256), interpolation=cv2.INTER_LANCZOS4)
            input_latent_list.append(self.vae.get_latents_for_unet(crop_frame))

        if not input_latent_list:
            raise ValueError("no face detected in the input image/video")

        # Mirror head/tail so audio longer than the frame count can cycle.
        frame_list_cycle = frame_list + frame_list[::-1]
        coord_list_cycle = coord_list + coord_list[::-1]
        input_latent_list_cycle = input_latent_list + input_latent_list[::-1]

        # --- Batched UNet inference ----------------------------------------------
        video_num = len(whisper_chunks)
        total_batches = int(np.ceil(float(video_num) / batch_size))
        gen = datagen(
            whisper_chunks=whisper_chunks,
            vae_encode_latents=input_latent_list_cycle,
            batch_size=batch_size,
            delay_frame=0,
            device=self.device,
        )

        res_frame_list = []
        for i, (whisper_batch, latent_batch) in enumerate(gen):
            audio_feature_batch = self.pe(whisper_batch)
            latent_batch = latent_batch.to(dtype=self.unet.model.dtype)
            pred_latents = self.unet.model(
                latent_batch, self.timesteps, encoder_hidden_states=audio_feature_batch
            ).sample
            recon = self.vae.decode_latents(pred_latents)
            for res_frame in recon:
                res_frame_list.append(res_frame)
            if progress_cb is not None:
                progress_cb(i + 1, total_batches)

        # --- Blend generated face back into the original frame --------------------
        result_img_dir = tempfile.mkdtemp(prefix="musetalk_result_")
        for i, res_frame in enumerate(res_frame_list):
            bbox = coord_list_cycle[i % len(coord_list_cycle)]
            ori_frame = copy.deepcopy(frame_list_cycle[i % len(frame_list_cycle)])
            x1, y1, x2, y2 = bbox
            if self.version == "v15":
                y2 = y2 + extra_margin
                y2 = min(y2, frame_list[0].shape[0])
            try:
                res_frame = cv2.resize(res_frame.astype(np.uint8), (x2 - x1, y2 - y1))
            except Exception:
                continue

            if self.version == "v15":
                combine_frame = get_image(ori_frame, res_frame, [x1, y1, x2, y2],
                                          mode=parsing_mode, fp=self.fp)
            else:
                combine_frame = get_image(ori_frame, res_frame, [x1, y1, x2, y2], fp=self.fp)
            cv2.imwrite(f"{result_img_dir}/{str(i).zfill(8)}.png", combine_frame)

        # --- Assemble video with ffmpeg ------------------------------------------
        temp_vid_path = os.path.join(tempfile.gettempdir(), f"musetalk_{os.getpid()}_video.mp4")
        cmd_img2video = [
            "ffmpeg", "-y", "-v", "warning", "-r", str(fps), "-f", "image2",
            "-i", f"{result_img_dir}/%08d.png", "-vcodec", "libx264",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p", "-crf", "18", temp_vid_path,
        ]
        subprocess.run(cmd_img2video, check=True)

        cmd_combine_audio = [
            "ffmpeg", "-y", "-v", "warning", "-i", audio_path, "-i", temp_vid_path,
            output_path,
        ]
        subprocess.run(cmd_combine_audio, check=True)

        # --- Cleanup --------------------------------------------------------------
        shutil.rmtree(result_img_dir, ignore_errors=True)
        if temp_frame_dir is not None:
            shutil.rmtree(temp_frame_dir, ignore_errors=True)
        if os.path.exists(temp_vid_path):
            os.remove(temp_vid_path)

        return output_path
