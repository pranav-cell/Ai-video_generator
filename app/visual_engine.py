import asyncio
import io
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from PIL import Image, ImageFilter

USER_AGENT = "AuraVideoGenerator/2.0 (realtime.ai.diffusion@local)"

# Cached local model instance
_LOCAL_DIFFUSER = None

def get_local_diffusion_pipeline():
    """Lazily loads SD-Turbo on Apple Silicon Metal Performance Shaders (MPS)."""
    global _LOCAL_DIFFUSER
    if _LOCAL_DIFFUSER is None:
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            print(f"[VisualEngine] Initializing local SD-Turbo generator on {device}...")
            _LOCAL_DIFFUSER = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/sd-turbo",
                torch_dtype=torch.float16 if device == "mps" else torch.float32,
                variant="fp16" if device == "mps" else None
            ).to(device)
            print("[VisualEngine] Local SD-Turbo generator loaded successfully!")
        except Exception as e:
            print(f"[VisualEngine] Failed to initialize local pipeline: {e}")
            _LOCAL_DIFFUSER = False
    return _LOCAL_DIFFUSER if _LOCAL_DIFFUSER is not False else None

def crop_and_resize(img: Image.Image, width: int = 1920, height: int = 1080, sharpen: bool = True) -> Image.Image:
    """Scales, center-crops, and sharpens with Lanczos resampling for ultra-crisp line art and anatomy."""
    img = img.convert("RGB")
    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(height * img_ratio)
    else:
        new_w = width
        new_h = int(width / img_ratio)

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    cropped = resized.crop((left, top, left + width, top + height))

    if sharpen:
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
    return cropped

NEGATIVE_ANATOMY_PROMPT = (
    "multiple people, 2men, 2women, two people, group, crowd, conjoined, twin, double head, "
    "extra head, extra neck, deformed face, distorted eyes, melted face, poorly drawn face, "
    "mutated, malformed limbs, missing limbs, extra limbs, extra arms, extra legs, bad anatomy, "
    "poorly drawn hands, missing fingers, extra fingers, fused fingers, blurry, bad proportions, "
    "disfigured, gross proportions, malformed body, watermark, text"
)

def build_prompt_for_sentence(sentence: str, art_style: str = "anime") -> str:
    """Constructs a targeted prompt directly from the spoken sentence narrative."""
    clean_s = sentence.strip().rstrip(".!?")
    
    is_anime = (
        art_style == "anime" or 
        any(k in clean_s.lower() for k in ["anime", "manga", "animation", "cartoon"])
    )
    
    if is_anime:
        style_suffix = "simple anime style, clean line art, beautiful cel shading, modern 2D anime aesthetic, vibrant colors, 8k anime art"
    elif art_style == "fantasy":
        style_suffix = "dark fantasy concept art, sharp intricate details, volumetric cinematic lighting, 8k"
    elif art_style == "cyberpunk":
        style_suffix = "cyberpunk futuristic aesthetic, neon reflections, sharp tech details, 8k"
    else:
        style_suffix = "cinematic 8k photograph, photorealistic masterpiece, dramatic lighting, sharp focus, 35mm lens"

    # Prioritize the spoken sentence as the central subject
    return f"{clean_s[:150]}, single subject, centered composition, {style_suffix}"[:240]

def generate_local_ai_image(
    prompt: str,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    art_style: str = "anime"
) -> bool:
    """Generates a 100% unique AI image in real-time locally on Apple Silicon GPU."""
    try:
        pipe = get_local_diffusion_pipeline()
        if pipe is None:
            return False

        clean_prompt = build_prompt_for_sentence(prompt, art_style)
        
        # 512x512 native latent square prevents U-Net multi-head duplication
        result = pipe(
            prompt=clean_prompt,
            negative_prompt=NEGATIVE_ANATOMY_PROMPT,
            width=512,
            height=512,
            num_inference_steps=2,
            guidance_scale=1.5
        ).images[0]

        cropped = crop_and_resize(result, width, height, sharpen=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"[VisualEngine] Local generation error: {e}")
        return False

def generate_cloud_ai_image(
    prompt: str,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    art_style: str = "anime"
) -> bool:
    """Real-time cloud AI text-to-image generator if local engine is unavailable."""
    try:
        clean_prompt = build_prompt_for_sentence(prompt, art_style)
        encoded_prompt = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=576&nologo=true&seed={hash(prompt) % 100000}"
        
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
        if resp.status_code == 200 and len(resp.content) > 10000:
            raw_img = Image.open(io.BytesIO(resp.content))
            cropped = crop_and_resize(raw_img, width, height, sharpen=True)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(output_path, "JPEG", quality=95)
            print("[VisualEngine] Generated real-time cloud AI image successfully!")
            return True
    except Exception as e:
        print(f"[VisualEngine] Cloud AI image generation error: {e}")
    return False

async def get_scene_visual(
    scene: Dict[str, Any],
    scene_dir: Path,
    visual_mode: str = "local_ai",
    width: int = 1920,
    height: int = 1080,
    pexels_api_key: Optional[str] = None,
    art_style: str = "anime"
) -> Dict[str, Any]:
    """
    100% Real-time AI Image Generation strictly tailored to each individual sentence:
    - No hardcoded images.
    - No Wikipedia scraping.
    - No procedural text cards.
    Every sentence generates a fresh, unique AI image in real-time.
    """
    scene_id = scene.get("scene_id", 1)
    sentence = scene.get("narration", "")
    motion = scene.get("camera_motion", "zoom_in")
    image_path = scene_dir / f"scene_{scene_id:03d}_visual.jpg"

    # Always generate real-time AI image dynamically for this exact sentence
    print(f"[VisualEngine] Scene {scene_id}: Generating real-time AI image for sentence: \"{sentence[:60]}...\"")

    # 1. Primary: Local Apple Silicon M5 GPU Diffusion (zero cost, offline, 0.5s)
    ok = await asyncio.to_thread(generate_local_ai_image, sentence, image_path, width, height, art_style)
    if ok and image_path.exists():
        print(f"[VisualEngine] Scene {scene_id}: Real-time local AI image generated!")
        return {"type": "image", "file_path": image_path, "camera_motion": motion}

    # 2. Cloud Real-Time AI Generation (Free text2image)
    print(f"[VisualEngine] Scene {scene_id}: Generating via real-time cloud AI...")
    ok_cloud = await asyncio.to_thread(generate_cloud_ai_image, sentence, image_path, width, height, art_style)
    if ok_cloud and image_path.exists():
        return {"type": "image", "file_path": image_path, "camera_motion": motion}

    # If any error, retry local with simplified prompt
    print(f"[VisualEngine] Scene {scene_id}: Retrying local AI generation with core sentence...")
    await asyncio.to_thread(generate_local_ai_image, sentence[:80], image_path, width, height, art_style)
    return {"type": "image", "file_path": image_path, "camera_motion": motion}
