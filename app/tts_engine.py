import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import edge_tts
from app.config import DEFAULT_VOICE, VOICES

def get_audio_duration(file_path: Path) -> float:
    """Uses ffprobe to obtain exact audio duration in seconds."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())

async def synthesize_scene_audio(
    text: str,
    output_audio_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> Dict[str, Any]:
    """
    Synthesizes speech using edge-tts.
    Returns:
      {
        'audio_path': Path,
        'duration': float,
        'srt': str,
        'boundaries': list
      }
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    submaker = edge_tts.SubMaker()
    boundaries = []
    
    with open(output_audio_path, "wb") as fp:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
                boundaries.append({
                    "type": chunk["type"],
                    "offset_sec": chunk["offset"] / 10_000_000.0,
                    "duration_sec": chunk["duration"] / 10_000_000.0,
                    "text": chunk.get("text", "")
                })
                
    duration = get_audio_duration(output_audio_path)
    srt_content = submaker.get_srt()
    
    return {
        "audio_path": output_audio_path,
        "duration": duration,
        "srt": srt_content,
        "boundaries": boundaries
    }

def get_available_voices() -> Dict[str, Any]:
    return VOICES
