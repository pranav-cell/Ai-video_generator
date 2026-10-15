import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = BASE_DIR / "cache"
STATIC_DIR = BASE_DIR / "static"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Free / Optional API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# Default Edge TTS Voices
VOICES = {
    "en-US-ChristopherNeural": {"name": "Christopher (Deep Documentary)", "gender": "Male", "accent": "US"},
    "en-US-GuyNeural": {"name": "Guy (Casual & Tech)", "gender": "Male", "accent": "US"},
    "en-US-JennyNeural": {"name": "Jenny (Warm & Natural)", "gender": "Female", "accent": "US"},
    "en-US-AriaNeural": {"name": "Aria (Dynamic & Engaging)", "gender": "Female", "accent": "US"},
    "en-GB-RyanNeural": {"name": "Ryan (British Sophisticated)", "gender": "Male", "accent": "UK"},
    "en-IN-PrabhatNeural": {"name": "Prabhat (Indian English Clear)", "gender": "Male", "accent": "IN"}
}

DEFAULT_VOICE = "en-US-ChristopherNeural"
DEFAULT_FPS = 30
DEFAULT_RESOLUTION = (1920, 1080) # 16:9 YouTube Landscape
SHORTS_RESOLUTION = (1080, 1920)  # 9:16 Shorts/Reels/TikTok
