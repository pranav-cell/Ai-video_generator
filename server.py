import asyncio
import os
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import OUTPUTS_DIR, STATIC_DIR, VOICES, DEFAULT_VOICE
from app.pipeline import run_video_pipeline, get_job_status, JOBS

app = FastAPI(title="AI Faceless Video Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    topic: str
    duration_minutes: int = 1
    aspect_ratio: str = "16:9"
    voice: str = DEFAULT_VOICE
    visual_mode: str = "ai_image"
    bgm_mood: str = "cinematic"
    gemini_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None

@app.get("/api/voices")
def list_voices():
    return VOICES

@app.post("/api/generate")
async def start_generation(req: GenerateRequest, background_tasks: BackgroundTasks):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic prompt cannot be empty.")
        
    import uuid
    job_id = str(uuid.uuid4())[:8]
    
    # Launch in background
    background_tasks.add_task(
        run_video_pipeline,
        topic=req.topic.strip(),
        duration_minutes=req.duration_minutes,
        aspect_ratio=req.aspect_ratio,
        voice=req.voice,
        visual_mode=req.visual_mode,
        bgm_mood=req.bgm_mood,
        gemini_api_key=req.gemini_api_key,
        pexels_api_key=req.pexels_api_key,
        job_id=job_id
    )
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/status/{job_id}")
def check_status(job_id: str):
    job = get_job_status(job_id)
    if not job:
        # Check if exists on disk
        job_dir = OUTPUTS_DIR / job_id
        meta_file = job_dir / "metadata.json"
        video_file = job_dir / "final_video.mp4"
        if meta_file.exists() and video_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "step_message": "Video ready",
                "video_url": f"/api/video/{job_id}/stream",
                "vtt_url": f"/api/video/{job_id}/subtitles.vtt",
                "title": data.get("title", "Generated Video"),
                "total_duration": data.get("duration_seconds", 0)
            }
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/video/{job_id}/stream")
def stream_video(job_id: str):
    video_path = OUTPUTS_DIR / job_id / "final_video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")

@app.get("/api/video/{job_id}/subtitles.vtt")
def get_vtt_subtitles(job_id: str):
    vtt_path = OUTPUTS_DIR / job_id / "subtitles.vtt"
    if not vtt_path.exists():
        raise HTTPException(status_code=404, detail="Subtitles not found")
    return FileResponse(vtt_path, media_type="text/vtt")

@app.get("/api/video/{job_id}/download")
def download_video(job_id: str):
    video_path = OUTPUTS_DIR / job_id / "final_video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    meta_file = OUTPUTS_DIR / job_id / "metadata.json"
    filename = "ai_video.mp4"
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                filename = f"{meta.get('title', 'video')[:30].replace(' ', '_')}.mp4"
        except Exception:
            pass
    return FileResponse(video_path, media_type="video/mp4", filename=filename)

@app.get("/api/history")
def get_history():
    videos = []
    if not OUTPUTS_DIR.exists():
        return []
    for d in sorted(OUTPUTS_DIR.iterdir(), key=os.path.getmtime, reverse=True):
        if d.is_dir() and (d / "final_video.mp4").exists():
            meta_file = d / "metadata.json"
            meta = {}
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass
            videos.append({
                "job_id": d.name,
                "title": meta.get("title", f"Video {d.name}"),
                "topic": meta.get("topic", "Faceless Video"),
                "duration_seconds": meta.get("duration_seconds", 0),
                "scenes_count": meta.get("scenes_count", 0),
                "aspect_ratio": meta.get("aspect_ratio", "16:9"),
                "video_url": f"/api/video/{d.name}/stream"
            })
    return videos

# Mount static files for the dashboard frontend
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting AI Faceless Video Generator Server on http://localhost:8050")
    uvicorn.run("server:app", host="0.0.0.0", port=8050, reload=True)
