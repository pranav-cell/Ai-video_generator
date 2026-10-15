import subprocess
from pathlib import Path
from typing import List, Optional

def generate_procedural_bgm(mood: str, duration: float, output_path: Path) -> Path:
    """Generates a soft, atmospheric background soundtrack procedurally via FFmpeg."""
    if mood == "cinematic":
        f1, f2, f3 = 110.0, 138.59, 164.81  # A2 minor deep cinematic
    elif mood == "mystery":
        f1, f2, f3 = 98.0, 116.54, 146.83   # G2 dark suspense
    elif mood == "chill":
        f1, f2, f3 = 174.61, 220.00, 261.63 # F3 lo-fi warm
    else:  # ambient
        f1, f2, f3 = 130.81, 164.81, 196.00 # C3 ambient clarity

    fade_out_start = max(0.5, duration - 2.5)
    
    filter_complex = (
        f"[0:a]volume=0.12[a0];[1:a]volume=0.12[a1];[2:a]volume=0.12[a2];[3:a]lowpass=f=250,volume=0.18[a3];"
        f"[a0][a1][a2][a3]amix=inputs=4,aecho=0.8:0.9:80:0.5,lowpass=f=950,afade=t=in:ss=0:d=1.5,afade=t=out:st={fade_out_start:.2f}:d=2.0[outa]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={f1}:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency={f2}:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency={f3}:duration={duration}",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={duration}:amplitude=0.015",
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def concatenate_voiceovers(scene_audio_files: List[Path], output_concat_file: Path) -> Path:
    """Concatenates all scene voiceovers sequentially into a single audio track."""
    output_concat_file.parent.mkdir(parents=True, exist_ok=True)
    list_file = output_concat_file.parent / "audio_concat_list.txt"
    
    with open(list_file, "w", encoding="utf-8") as f:
        for audio in scene_audio_files:
            # Escape path for ffmpeg concat demuxer
            safe_path = str(audio.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_concat_file)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    list_file.unlink(missing_ok=True)
    return output_concat_file

def mix_voice_and_music(
    voice_path: Path,
    bgm_path: Optional[Path],
    output_path: Path,
    bgm_volume: float = 0.12
) -> Path:
    """Mixes voiceover with ducked background music."""
    if not bgm_path or not bgm_path.exists():
        # Pure voiceover without music
        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    # Mix voice (100%) and bgm (ducked to ~12-15%)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(voice_path),
        "-i", str(bgm_path),
        "-filter_complex",
        f"[0:a]volume=1.0[voice];[1:a]volume={bgm_volume}[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path
