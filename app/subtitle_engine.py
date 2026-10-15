import datetime
from pathlib import Path
from typing import List, Dict, Any

def format_timestamp_srt(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_timestamp_vtt(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def format_timestamp_ass(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centis = int(round((seconds - total_seconds) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centis:02d}"

def build_srt_file(scene_subtitles: List[Dict[str, Any]], output_file: Path) -> Path:
    """
    Each item in scene_subtitles:
      {
        'global_start': float,
        'global_end': float,
        'text': str
      }
    """
    lines = []
    idx = 1
    for item in scene_subtitles:
        start_str = format_timestamp_srt(item["global_start"])
        end_str = format_timestamp_srt(item["global_end"])
        text = item["text"].strip()
        if not text:
            continue
        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
        idx += 1
        
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_file

def build_vtt_file(scene_subtitles: List[Dict[str, Any]], output_file: Path) -> Path:
    lines = ["WEBVTT\n"]
    for idx, item in enumerate(scene_subtitles, 1):
        start_str = format_timestamp_vtt(item["global_start"])
        end_str = format_timestamp_vtt(item["global_end"])
        text = item["text"].strip()
        if not text:
            continue
        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
        
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_file

def build_ass_file(
    scene_subtitles: List[Dict[str, Any]],
    output_file: Path,
    width: int = 1920,
    height: int = 1080
) -> Path:
    """Generates modern viral YouTube-style ASS subtitles with high-contrast outlines."""
    font_size = 54 if width >= 1920 else 38
    margin_v = 75 if height >= 1080 else 50
    
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H0000D4FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3.5,1.5,2,30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for item in scene_subtitles:
        start_str = format_timestamp_ass(item["global_start"])
        end_str = format_timestamp_ass(item["global_end"])
        text = item["text"].strip().replace("\n", " ")
        if not text:
            continue
        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")
        
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return output_file
