import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

def render_scene_clip(
    media_info: Dict[str, Any],
    duration: float,
    output_clip_path: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30
) -> Path:
    """
    Renders an individual scene's visual media to an MP4 clip with camera motion and exact duration.
    """
    output_clip_path.parent.mkdir(parents=True, exist_ok=True)
    media_type = media_info.get("type", "image")
    file_path = media_info.get("file_path")
    motion = media_info.get("camera_motion", "zoom_in")
    
    total_frames = max(30, int(duration * fps))

    if media_type == "image":
        # Configure motion formulas
        if motion == "zoom_out":
            zp_filter = f"zoompan=z='if(lte(zoom,1.0),1.22,max(1.0,zoom-0.0012))':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
        elif motion == "pan_left":
            zp_filter = f"zoompan=z=1.18:x='if(lte(on,-1),(iw-iw/zoom),max(0,x-1.5))':y='(ih-ih/zoom)/2':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion == "pan_right":
            zp_filter = f"zoompan=z=1.18:x='if(lte(on,-1),0,min(iw-iw/zoom,x+1.5))':y='(ih-ih/zoom)/2':d={total_frames}:s={width}x{height}:fps={fps}"
        else: # default zoom_in
            zp_filter = f"zoompan=z='min(zoom+0.0015,1.25)':d={total_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"

        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},{zp_filter}"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(file_path),
            "-vf", vf,
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-an",
            str(output_clip_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    else: # Video clip from stock footage
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(file_path),
            "-vf", vf,
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-an",
            str(output_clip_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    return output_clip_path

def assemble_final_video(
    scene_clips: List[Path],
    master_audio_path: Path,
    srt_subtitles_path: Optional[Path],
    output_video_path: Path
) -> Path:
    """
    Concatenates all visual clips, muxes master audio, and embeds subtitle tracks.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_video_path.parent
    clips_list_file = temp_dir / "clips_concat_list.txt"
    concat_video_file = temp_dir / "temp_concat_video.mp4"

    # Write concat list
    with open(clips_list_file, "w", encoding="utf-8") as f:
        for clip in scene_clips:
            safe_path = str(clip.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    # Step 1: Concatenate video streams
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(clips_list_file),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        str(concat_video_file)
    ]
    subprocess.run(concat_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 2: Mux audio and optional subtitle track
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(concat_video_file),
        "-i", str(master_audio_path)
    ]

    if srt_subtitles_path and srt_subtitles_path.exists():
        mux_cmd.extend(["-i", str(srt_subtitles_path)])
        mux_cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-shortest",
            str(output_video_path)
        ])
    else:
        mux_cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_video_path)
        ])

    subprocess.run(mux_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Clean up temporary intermediary files
    clips_list_file.unlink(missing_ok=True)
    concat_video_file.unlink(missing_ok=True)

    return output_video_path
