import asyncio
import uuid
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import OUTPUTS_DIR, CACHE_DIR, DEFAULT_VOICE, DEFAULT_RESOLUTION, SHORTS_RESOLUTION
from app.script_engine import generate_script
from app.tts_engine import synthesize_scene_audio
from app.visual_engine import get_scene_visual
from app.subtitle_engine import build_srt_file, build_vtt_file, build_ass_file
from app.audio_engine import generate_procedural_bgm, concatenate_voiceovers, mix_voice_and_music
from app.video_renderer import render_scene_clip, assemble_final_video

# In-memory job store
JOBS: Dict[str, Dict[str, Any]] = {}

def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    return JOBS.get(job_id)

async def run_video_pipeline(
    topic: str,
    duration_minutes: int = 1,
    aspect_ratio: str = "16:9",
    voice: str = DEFAULT_VOICE,
    visual_mode: str = "ai_image",
    bgm_mood: str = "cinematic",
    gemini_api_key: Optional[str] = None,
    pexels_api_key: Optional[str] = None,
    job_id: Optional[str] = None,
    art_style: str = "anime"
) -> str:
    """
    Executes the video generation pipeline:
    - 1 image per sentence (visual changes immediately after each sentence completes)
    - Strictly calibrates duration to requested length (e.g. exactly 60.0s for 1 min)
    - Uses local diffusion with customizable art styles (Simple Anime, Photorealistic, etc.)
    """
    if not job_id:
        job_id = str(uuid.uuid4())[:8]

    target_total_seconds = float(duration_minutes * 60.0)
    width, height = DEFAULT_RESOLUTION if aspect_ratio == "16:9" else SHORTS_RESOLUTION
    job_dir = OUTPUTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    scenes_dir = job_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    JOBS[job_id] = {
        "job_id": job_id,
        "topic": topic,
        "status": "starting",
        "progress": 5,
        "step_message": f"Initializing {duration_minutes}-minute video studio workspace...",
        "created_at": time.time(),
        "video_url": None,
        "vtt_url": None,
        "scenes_data": [],
        "error": None
    }

    try:
        # Step 1: Script & Storyboard (Strictly 1 sentence per scene)
        JOBS[job_id]["status"] = "scripting"
        JOBS[job_id]["step_message"] = "Crafting calibrated single-sentence storyboard with AI..."
        JOBS[job_id]["progress"] = 15
        
        script_data = await generate_script(topic, duration_minutes=duration_minutes, api_key=gemini_api_key, art_style=art_style)
        scenes = script_data.get("scenes", [])
        video_title = script_data.get("title", f"Video about {topic}")
        JOBS[job_id]["title"] = video_title
        JOBS[job_id]["scenes_count"] = len(scenes)

        # Step 2: Voiceover & Audio Synthesis (Edge-TTS)
        JOBS[job_id]["status"] = "voicing"
        JOBS[job_id]["step_message"] = f"Synthesizing voiceovers for all {len(scenes)} sentences..."
        JOBS[job_id]["progress"] = 28

        scene_audio_files = []
        scene_subtitles = []
        scene_durations = []
        global_timeline_sec = 0.0
        
        for idx, scene in enumerate(scenes):
            scene_id = scene.get("scene_id", idx + 1)
            narration = scene.get("narration", "")
            audio_out = scenes_dir / f"scene_{scene_id:03d}_voice.mp3"
            
            # Synthesize single sentence audio
            tts_res = await synthesize_scene_audio(narration, audio_out, voice=voice)
            dur = tts_res["duration"]
            scene_audio_files.append(audio_out)
            scene_durations.append(dur)

            # Record subtitle entry
            scene_subtitles.append({
                "global_start": global_timeline_sec,
                "global_end": global_timeline_sec + dur,
                "text": narration
            })
            global_timeline_sec += dur

            sub_prog = 28 + int(20 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog
            JOBS[job_id]["step_message"] = f"Voiceover ready for sentence {idx + 1}/{len(scenes)}..."

        # Save global subtitles
        srt_path = job_dir / "subtitles.srt"
        vtt_path = job_dir / "subtitles.vtt"
        ass_path = job_dir / "subtitles.ass"
        build_srt_file(scene_subtitles, srt_path)
        build_vtt_file(scene_subtitles, vtt_path)
        build_ass_file(scene_subtitles, ass_path, width=width, height=height)

        # Step 3: Visual Generation (Local AI Images on Apple Silicon GPU for each sentence)
        JOBS[job_id]["status"] = "visualizing"
        JOBS[job_id]["step_message"] = f"Generating {len(scenes)} custom AI images locally on Apple M5 GPU..."
        JOBS[job_id]["progress"] = 50
        JOBS[job_id]["scenes_data"] = []

        scene_visuals = []
        for idx, scene in enumerate(scenes):
            scene_id = scene.get("scene_id", idx + 1)
            narration = scene.get("narration", "")
            visual_info = await get_scene_visual(
                scene,
                scenes_dir,
                visual_mode=visual_mode,
                width=width,
                height=height,
                pexels_api_key=pexels_api_key,
                art_style=art_style
            )
            scene_visuals.append(visual_info)
            
            # Stream generated image immediately to real-time client preview
            JOBS[job_id]["scenes_data"].append({
                "scene_id": scene_id,
                "narration": narration,
                "image_url": f"/api/scene_image/{job_id}/{scene_id}",
                "status": "ready"
            })
            
            sub_prog = 50 + int(20 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog
            JOBS[job_id]["step_message"] = f"Real-time AI visual ready for scene {idx + 1}/{len(scenes)}..."

        # Step 4: Calibrate Clip Durations & Render Ken Burns Motion
        # Visual cuts occur exactly when each sentence finishes speaking
        JOBS[job_id]["status"] = "rendering_clips"
        JOBS[job_id]["step_message"] = "Rendering dynamic camera movement synchronized to sentences..."
        JOBS[job_id]["progress"] = 72

        # Duration calibration:
        # If speech is slightly under target_total_seconds (e.g. 56s vs 60s),
        # extend the last scene's visual hold to achieve exactly 60.0 seconds!
        total_speech = sum(scene_durations)
        final_scene_extra = max(0.0, target_total_seconds - total_speech)

        rendered_clips = []
        for idx, (visual_info, scene) in enumerate(zip(scene_visuals, scenes)):
            dur = scene_durations[idx]
            # If this is the last scene, add extra hold so total video is exactly target_total_seconds
            if idx == len(scenes) - 1 and final_scene_extra > 0:
                dur += final_scene_extra

            clip_path = scenes_dir / f"scene_{idx + 1:03d}_clip.mp4"
            await asyncio.to_thread(
                render_scene_clip,
                visual_info,
                duration=dur,
                output_clip_path=clip_path,
                width=width,
                height=height,
                fps=30
            )
            rendered_clips.append(clip_path)

            sub_prog = 72 + int(16 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog

        # Step 5: Sound Design, Ducking & Assembly
        JOBS[job_id]["status"] = "assembling"
        JOBS[job_id]["step_message"] = f"Compiling exact {duration_minutes}-minute video with ducked audio..."
        JOBS[job_id]["progress"] = 90

        raw_voice_concat = job_dir / "voice_concat.aac"
        await asyncio.to_thread(concatenate_voiceovers, scene_audio_files, raw_voice_concat)

        master_audio = job_dir / "master_audio.aac"
        if bgm_mood != "none":
            bgm_file = job_dir / "background_music.aac"
            # Background music plays for full target duration with smooth outro fade
            await asyncio.to_thread(generate_procedural_bgm, bgm_mood, duration=target_total_seconds + 1.0, output_path=bgm_file)
            await asyncio.to_thread(mix_voice_and_music, raw_voice_concat, bgm_file, master_audio, bgm_volume=0.12)
        else:
            await asyncio.to_thread(mix_voice_and_music, raw_voice_concat, None, master_audio)

        final_video_file = job_dir / "final_video.mp4"
        await asyncio.to_thread(
            assemble_final_video,
            scene_clips=rendered_clips,
            master_audio_path=master_audio,
            srt_subtitles_path=srt_path,
            output_video_path=final_video_file,
            target_duration=target_total_seconds
        )

        # Save metadata
        meta_file = job_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "title": video_title,
                "topic": topic,
                "duration_seconds": target_total_seconds,
                "scenes_count": len(scenes),
                "aspect_ratio": aspect_ratio,
                "voice": voice,
                "created_at": time.time()
            }, f, indent=2)

        # Completed
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["progress"] = 100
        JOBS[job_id]["step_message"] = f"Done! Exactly {duration_minutes}-minute video ready with sentence-synced cuts."
        JOBS[job_id]["video_url"] = f"/api/video/{job_id}/stream"
        JOBS[job_id]["vtt_url"] = f"/api/video/{job_id}/subtitles.vtt"
        JOBS[job_id]["total_duration"] = target_total_seconds

    except Exception as e:
        import traceback
        traceback.print_exc()
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["step_message"] = f"Error during generation: {e}"

    return job_id
