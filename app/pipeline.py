import asyncio
import uuid
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
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
    aspect_ratio: str = "16:9", # '16:9' or '9:16'
    voice: str = DEFAULT_VOICE,
    visual_mode: str = "ai_image", # 'ai_image', 'stock_broll', 'hybrid'
    bgm_mood: str = "cinematic", # 'cinematic', 'ambient', 'mystery', 'chill', 'none'
    gemini_api_key: Optional[str] = None,
    pexels_api_key: Optional[str] = None,
    job_id: Optional[str] = None
) -> str:
    """
    Executes the complete video generation pipeline.
    Emits real-time state updates to JOBS[job_id].
    """
    if not job_id:
        job_id = str(uuid.uuid4())[:8]

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
        "step_message": "Initializing project workspace...",
        "created_at": time.time(),
        "video_url": None,
        "vtt_url": None,
        "scenes_data": [],
        "error": None
    }

    try:
        # Step 1: Script & Storyboard Generation
        JOBS[job_id]["status"] = "scripting"
        JOBS[job_id]["step_message"] = "Crafting engaging storyboard and multi-chapter script with AI..."
        JOBS[job_id]["progress"] = 15
        
        script_data = await generate_script(topic, duration_minutes=duration_minutes, api_key=gemini_api_key)
        scenes = script_data.get("scenes", [])
        video_title = script_data.get("title", f"Video about {topic}")
        JOBS[job_id]["title"] = video_title
        JOBS[job_id]["scenes_count"] = len(scenes)

        # Step 2: Voiceover & Audio Synthesis (Edge-TTS)
        JOBS[job_id]["status"] = "voicing"
        JOBS[job_id]["step_message"] = "Generating natural neural voiceovers for each scene..."
        JOBS[job_id]["progress"] = 30

        scene_audio_files = []
        scene_subtitles = []
        global_timeline_sec = 0.0
        
        for idx, scene in enumerate(scenes):
            scene_id = scene.get("scene_id", idx + 1)
            narration = scene.get("narration", "")
            audio_out = scenes_dir / f"scene_{scene_id:03d}_voice.mp3"
            
            # Synthesize audio with exact duration and boundaries
            tts_res = await synthesize_scene_audio(narration, audio_out, voice=voice)
            dur = tts_res["duration"]
            scene_audio_files.append(audio_out)

            # Record timeline subtitle entry
            scene_subtitles.append({
                "global_start": global_timeline_sec,
                "global_end": global_timeline_sec + dur,
                "text": narration
            })
            global_timeline_sec += dur

            # Update progress
            sub_prog = 30 + int(20 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog
            JOBS[job_id]["step_message"] = f"Voiceover synthesized for scene {idx + 1}/{len(scenes)}..."

        # Save global subtitles (SRT, VTT, ASS)
        srt_path = job_dir / "subtitles.srt"
        vtt_path = job_dir / "subtitles.vtt"
        ass_path = job_dir / "subtitles.ass"
        build_srt_file(scene_subtitles, srt_path)
        build_vtt_file(scene_subtitles, vtt_path)
        build_ass_file(scene_subtitles, ass_path, width=width, height=height)

        # Step 3: Visual Assets (Pollinations AI Images / Pexels Stock Video)
        JOBS[job_id]["status"] = "visualizing"
        JOBS[job_id]["step_message"] = "Generating photorealistic visual assets with FLUX / stock footage..."
        JOBS[job_id]["progress"] = 55

        scene_visuals = []
        for idx, scene in enumerate(scenes):
            visual_info = await get_scene_visual(
                scene,
                scenes_dir,
                visual_mode=visual_mode,
                width=width,
                height=height,
                pexels_api_key=pexels_api_key
            )
            scene_visuals.append(visual_info)
            
            sub_prog = 55 + int(15 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog
            JOBS[job_id]["step_message"] = f"Visual asset ready for scene {idx + 1}/{len(scenes)}..."

        # Step 4: Render Individual Video Clips with Ken Burns Motion
        JOBS[job_id]["status"] = "rendering_clips"
        JOBS[job_id]["step_message"] = "Rendering dynamic camera pans and cinematic motion for each scene..."
        JOBS[job_id]["progress"] = 72

        rendered_clips = []
        for idx, (visual_info, scene) in enumerate(zip(scene_visuals, scenes)):
            # Audio duration for this scene
            dur = scene_subtitles[idx]["global_end"] - scene_subtitles[idx]["global_start"]
            clip_path = scenes_dir / f"scene_{idx + 1:03d}_clip.mp4"
            
            render_scene_clip(
                visual_info,
                duration=dur,
                output_clip_path=clip_path,
                width=width,
                height=height,
                fps=30
            )
            rendered_clips.append(clip_path)

            sub_prog = 72 + int(15 * (idx + 1) / len(scenes))
            JOBS[job_id]["progress"] = sub_prog

        # Step 5: Sound Design & Final Assembly
        JOBS[job_id]["status"] = "assembling"
        JOBS[job_id]["step_message"] = "Mixing master audio, ducking background music, and compiling final MP4..."
        JOBS[job_id]["progress"] = 90

        # Concat voiceovers
        raw_voice_concat = job_dir / "voice_concat.aac"
        concatenate_voiceovers(scene_audio_files, raw_voice_concat)

        # BGM Generation
        master_audio = job_dir / "master_audio.aac"
        if bgm_mood != "none":
            bgm_file = job_dir / "background_music.aac"
            generate_procedural_bgm(bgm_mood, duration=global_timeline_sec + 2.0, output_path=bgm_file)
            mix_voice_and_music(raw_voice_concat, bgm_file, master_audio, bgm_volume=0.12)
        else:
            mix_voice_and_music(raw_voice_concat, None, master_audio)

        # Assemble final video
        final_video_file = job_dir / "final_video.mp4"
        assemble_final_video(
            scene_clips=rendered_clips,
            master_audio_path=master_audio,
            srt_subtitles_path=srt_path,
            output_video_path=final_video_file
        )

        # Save metadata JSON
        meta_file = job_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "title": video_title,
                "topic": topic,
                "duration_seconds": round(global_timeline_sec, 2),
                "scenes_count": len(scenes),
                "aspect_ratio": aspect_ratio,
                "voice": voice,
                "created_at": time.time()
            }, f, indent=2)

        # Mark completed
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["progress"] = 100
        JOBS[job_id]["step_message"] = "Video generation complete! Ready to watch and download."
        JOBS[job_id]["video_url"] = f"/api/video/{job_id}/stream"
        JOBS[job_id]["vtt_url"] = f"/api/video/{job_id}/subtitles.vtt"
        JOBS[job_id]["total_duration"] = round(global_timeline_sec, 1)

    except Exception as e:
        import traceback
        traceback.print_exc()
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["step_message"] = f"Error during generation: {e}"

    return job_id
