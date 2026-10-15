import hashlib
import random
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from PIL import Image, ImageDraw, ImageFont

async def download_ai_image(
    prompt: str,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    seed: Optional[int] = None
) -> Path:
    """Downloads a photorealistic AI image from Pollinations.ai with FLUX/SDXL quality."""
    if seed is None:
        seed = random.randint(1000, 999999)
        
    encoded_prompt = urllib.parse.quote(prompt.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&seed={seed}&nologo=true&enhance=true"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
            
    return output_path

async def fetch_pexels_video(
    query: str,
    output_path: Path,
    api_key: str,
    orientation: str = "landscape"
) -> Optional[Path]:
    """Fetches a free stock B-roll clip from Pexels API if key is present."""
    if not api_key:
        return None
        
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=3&orientation={orientation}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
            videos = data.get("videos", [])
            if not videos:
                return None
                
            # Pick first video and find best HD MP4 link
            video_files = videos[0].get("video_files", [])
            mp4_files = [f for f in video_files if f.get("file_type") == "video/mp4"]
            if not mp4_files:
                return None
                
            # Sort by resolution, pick ~1080p
            mp4_files.sort(key=lambda x: (x.get("width", 0) or 0), reverse=True)
            download_url = mp4_files[0]["link"]
            
            # Download clip
            dl_resp = await client.get(download_url, follow_redirects=True)
            dl_resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(dl_resp.content)
            return output_path
    except Exception as e:
        print(f"[VisualEngine] Pexels download error: {e}")
        return None

def create_fallback_graphic(
    title: str,
    subtitle: str,
    output_path: Path,
    width: int = 1920,
    height: int = 1080
) -> Path:
    """Creates a sleek, modern dark-gradient visual if network asset is unavailable."""
    # Create dark gradient background
    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    # Draw soft radial/linear gradient lines
    for y in range(height):
        r = int(15 + (y / height) * 25)
        g = int(23 + (y / height) * 15)
        b = int(42 + (y / height) * 45)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # Draw glowing accent glow circle
    draw.ellipse([width//4, height//4, 3*width//4, 3*height//4], fill=(30, 41, 70), outline=(99, 102, 241, 100))
    
    # Simple text rendering
    draw.text((width // 2, height // 2 - 40), title[:60], fill=(255, 255, 255), anchor="mm")
    draw.text((width // 2, height // 2 + 30), subtitle[:80], fill=(148, 163, 184), anchor="mm")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=90)
    return output_path

async def get_scene_visual(
    scene: Dict[str, Any],
    scene_dir: Path,
    visual_mode: str = "ai_image", # 'ai_image', 'stock_broll', 'hybrid'
    width: int = 1920,
    height: int = 1080,
    pexels_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Acquires visual media for a scene:
    Returns dict:
      {
        'type': 'image' | 'video',
        'file_path': Path,
        'camera_motion': str
      }
    """
    scene_id = scene.get("scene_id", 1)
    prompt = scene.get("image_prompt", "")
    broll_query = scene.get("broll_query", "cinematic landscape")
    motion = scene.get("camera_motion", "zoom_in")
    
    # 1. If stock B-roll preferred or hybrid
    if visual_mode in ("stock_broll", "hybrid") and pexels_api_key:
        video_path = scene_dir / f"scene_{scene_id:03d}_broll.mp4"
        if not video_path.exists():
            orientation = "portrait" if height > width else "landscape"
            clip = await fetch_pexels_video(broll_query, video_path, pexels_api_key, orientation)
            if clip and clip.exists():
                return {"type": "video", "file_path": clip, "camera_motion": "none"}
                
    # 2. Free AI Image via Pollinations
    image_path = scene_dir / f"scene_{scene_id:03d}_ai.jpg"
    if not image_path.exists():
        try:
            await download_ai_image(prompt, image_path, width=width, height=height)
            return {"type": "image", "file_path": image_path, "camera_motion": motion}
        except Exception as e:
            print(f"[VisualEngine] Pollinations error for scene {scene_id}: {e}. Creating fallback.")
            create_fallback_graphic(scene.get("chapter", "Scene"), scene.get("narration", "")[:60], image_path, width, height)
            return {"type": "image", "file_path": image_path, "camera_motion": motion}
            
    return {"type": "image", "file_path": image_path, "camera_motion": motion}
