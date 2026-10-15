import json
import re
import urllib.parse
import httpx
from typing import List, Dict, Any, Optional

SYSTEM_PROMPT = """You are an elite YouTube documentary scriptwriter and director specialized in viral, engaging faceless videos.
Your task is to take a topic and generate a structured multi-scene storyboard.

Each scene represents approximately 4-8 seconds of video.
Provide:
1. `title`: Catchy video title.
2. `topic`: Clean topic summary.
3. `scenes`: An array of scene objects. Each scene must contain:
   - `scene_id`: integer starting from 1
   - `chapter`: Name of the chapter (e.g. 'The Hook', 'The Mystery Unfolds', 'The Evidence', 'The Turning Point', 'The Resolution')
   - `narration`: Exactly what the voiceover speaks. Punchy, dramatic, highly engaging.
   - `image_prompt`: A detailed photorealistic prompt for AI image generation (e.g. 'Cinematic wide shot of an ancient Roman colosseum at sunset with dramatic lighting, 8k resolution, photorealistic, atmospheric mist').
   - `broll_query`: 2-3 search keywords for stock video search (e.g. 'roman colosseum', 'ancient ruins').
   - `camera_motion`: One of 'zoom_in', 'zoom_out', 'pan_left', 'pan_right'.

Format your response strictly as valid JSON, with NO preamble, NO markdown ticks, and NO commentary."""

def parse_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    # Remove markdown code block if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        # Search for first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError("Could not parse JSON from model output")

async def generate_script_gemini(topic: str, target_scenes: int, api_key: str) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    prompt = f"{SYSTEM_PROMPT}\n\nTOPIC: {topic}\nTarget total scenes: {target_scenes}\nOutput strict JSON only."
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json_from_text(raw_text)

async def generate_script_pollinations(topic: str, target_scenes: int) -> Dict[str, Any]:
    prompt = (
        f"You are a video scriptwriter. Generate a JSON video storyboard for: '{topic}'.\n"
        f"Generate exactly {target_scenes} sequential scenes.\n"
        "Return strictly valid JSON with this schema:\n"
        "{\n"
        '  "title": "...",\n'
        '  "scenes": [\n'
        "    {\n"
        '      "scene_id": 1,\n'
        '      "chapter": "The Hook",\n'
        '      "narration": "Narration text here (15-25 words)...",\n'
        '      "image_prompt": "Cinematic visual prompt...",\n'
        '      "broll_query": "broll keywords",\n'
        '      "camera_motion": "zoom_in"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Output ONLY pure JSON. Do not include markdown code ticks."
    )
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.get(url)
        res.raise_for_status()
        return parse_json_from_text(res.text)

def generate_fallback_storyboard(topic: str, target_scenes: int) -> Dict[str, Any]:
    """Bulletproof deterministic fallback that generates a compelling storyboard for any topic."""
    motions = ["zoom_in", "zoom_out", "pan_left", "pan_right"]
    chapters = [
        ("The Hook", f"What if everything you thought you knew about {topic} was only the surface of a much deeper reality?"),
        ("The Origins", f"To understand {topic}, we have to go back to how it all began and the pivotal forces that shaped it."),
        ("The Turning Point", f"A crucial breakthrough shifted the entire landscape, challenging the greatest minds of our time."),
        ("The Hidden Truth", f"Beneath the common narrative lies a complex web of discoveries that few people ever talk about."),
        ("The Breakthrough", f"Recent developments have accelerated this evolution faster than anyone could have predicted."),
        ("The Controversy", f"Yet, with immense progress came intense debate, skepticism, and unanswered questions."),
        ("The Future Vision", f"As we look ahead, the implications of {topic} will redefine how we live, work, and perceive reality."),
        ("The Takeaway", f"One thing is certain: the story of {topic} is still being written, and the next chapter begins today.")
    ]
    
    scenes = []
    for i in range(target_scenes):
        ch_idx = min(i * len(chapters) // target_scenes, len(chapters) - 1)
        chapter_name, narration_base = chapters[ch_idx]
        motion = motions[i % len(motions)]
        
        scenes.append({
            "scene_id": i + 1,
            "chapter": f"{chapter_name} (Part {i+1})",
            "narration": f"{narration_base} When examining {topic}, every detail offers a glimpse into a much larger puzzle.",
            "image_prompt": f"Cinematic atmospheric shot illustrating {topic}, {chapter_name.lower()} scene, 8k resolution, dramatic photorealistic lighting, masterpiece",
            "broll_query": f"{topic} {chapter_name.lower().split()[0]}",
            "camera_motion": motion
        })
        
    return {
        "title": f"The Untold Truth of {topic.title()}",
        "topic": topic,
        "scenes": scenes
    }

async def generate_script(topic: str, duration_minutes: int = 1, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    duration_minutes:
      1 min -> ~6-8 scenes
      3 mins -> ~18-20 scenes
      5 mins -> ~30-35 scenes
      10 mins -> ~60-70 scenes
    """
    scenes_count = max(4, int(duration_minutes * 7)) # ~7 scenes per minute (~8.5s per scene)
    
    # Try Gemini if key is provided
    if api_key and api_key.strip():
        try:
            return await generate_script_gemini(topic, scenes_count, api_key.strip())
        except Exception as e:
            print(f"[ScriptEngine] Gemini generation error: {e}. Falling back to Pollinations...")
            
    # Try free Pollinations AI
    try:
        data = await generate_script_pollinations(topic, scenes_count)
        if "scenes" in data and len(data["scenes"]) > 0:
            return data
    except Exception as e:
        print(f"[ScriptEngine] Pollinations generation error: {e}. Using smart fallback...")
        
    # Failsafe fallback
    return generate_fallback_storyboard(topic, scenes_count)
