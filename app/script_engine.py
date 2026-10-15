import json
import re
import urllib.parse
import httpx
from typing import List, Dict, Any, Optional

MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right"]

def clean_sentence(text: str) -> str:
    """Cleans up punctuation and spacing for a clean spoken sentence."""
    text = re.sub(r"\s+", " ", text).strip()
    return text

def split_and_normalize_scenes(raw_scenes: List[Dict[str, Any]], target_count: int, topic: str, art_style: str = "anime") -> List[Dict[str, Any]]:
    """
    CRITICAL: Ensures every single scene contains EXACTLY ONE SENTENCE.
    When a sentence completes speaking, the visual changes immediately.
    """
    expanded_scenes = []
    
    for sc in raw_scenes:
        narration = sc.get("narration", "").strip()
        if not narration:
            continue
            
        # Split narration into individual sentences
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration) if s.strip()]
        if not raw_sentences:
            raw_sentences = [narration]
            
        base_prompt = sc.get("image_prompt", f"Cinematic shot of {topic}")
        base_query = sc.get("broll_query", topic)
        chapter = sc.get("chapter", "Scene")
        
        for idx, sentence in enumerate(raw_sentences):
            cleaned_s = clean_sentence(sentence)
            prompt_subject = cleaned_s.rstrip(".!?")
            if len(prompt_subject) > 80:
                prompt_subject = prompt_subject[:80]
                
            # Extract key nouns / search terms from the sentence
            stop_words = {"what", "that", "this", "with", "from", "have", "been", "were", "they", "some", "more", "most", "when", "where", "into", "their", "there", "about", "could", "would", "should", "century", "centuries", "defied", "began"}
            words = [re.sub(r"[^a-zA-Z]", "", w) for w in cleaned_s.split()]
            meaningful = [w for w in words if len(w) > 3 and w.lower() not in stop_words]
            sentence_query = " ".join(meaningful[:2]) if len(meaningful) >= 1 else topic

            is_anime = (
                art_style == "anime" or 
                any(k in topic.lower() for k in ["anime", "manga", "animation", "cartoon"])
            )
            if is_anime:
                specific_prompt = (
                    f"Simple anime style artwork depicting {prompt_subject}, "
                    f"clean line art, expressive eyes, beautiful cel shading, "
                    f"modern 2D anime aesthetic, vibrant colors, 8k anime screencap"
                )
            elif art_style == "fantasy":
                specific_prompt = (
                    f"Dark fantasy digital concept art depicting {prompt_subject}, "
                    f"intricate textures, epic atmospheric lighting, ArtStation trending, 8k"
                )
            elif art_style == "cyberpunk":
                specific_prompt = (
                    f"Cyberpunk futuristic anime style depicting {prompt_subject}, "
                    f"neon lighting, sharp mechanical and tech details, cinematic screencap, 8k"
                )
            else:
                specific_prompt = (
                    f"Cinematic 8k photograph illustrating {prompt_subject}, "
                    f"dramatic volumetric lighting, photorealistic masterpiece, "
                    f"sharp focus on 35mm lens, highly detailed textures, vibrant atmospheric depth"
                )
            
            expanded_scenes.append({
                "chapter": chapter,
                "narration": cleaned_s,
                "image_prompt": specific_prompt,
                "broll_query": sentence_query,
                "camera_motion": MOTIONS[len(expanded_scenes) % len(MOTIONS)]
            })

    # If we have more than target_count, trim to target_count
    if len(expanded_scenes) > target_count:
        expanded_scenes = expanded_scenes[:target_count]
    # If we have fewer than target_count, we keep them as is (or pipeline handles pad)
    
    # Assign sequential scene IDs
    for i, sc in enumerate(expanded_scenes, 1):
        sc["scene_id"] = i
        
    return expanded_scenes

def build_system_prompt(duration_minutes: int, target_sentences: int, topic: str) -> str:
    word_budget = target_sentences * 13  # ~13 words per sentence
    target_seconds = duration_minutes * 60
    return f"""You are a master documentary director and scriptwriter.
Generate a structured video storyboard for: '{topic}'.

CRITICAL CONSTRAINTS:
1. Target total duration: EXACTLY {duration_minutes} minute(s) ({target_seconds} seconds).
2. Number of scenes: Exactly {target_sentences} scenes.
3. ONE SENTENCE PER SCENE: Each scene must contain EXACTLY ONE single sentence of spoken narration.
   (The video cuts to a new image the instant each sentence completes speaking).
4. Sentence length: 11-15 words per sentence (punchy, dramatic, engaging).
5. Total word budget across all scenes: ~{word_budget} words.
6. Provide for each scene:
   - `scene_id`: integer starting from 1
   - `chapter`: Chapter name (e.g. 'The Hook', 'The Discovery', 'The Conflict', 'The Revelation', 'The Climax', 'The Conclusion')
   - `narration`: Exactly ONE complete spoken sentence.
   - `image_prompt`: A rich, photorealistic, 8k prompt describing the exact visual subject of this sentence.
   - `broll_query`: 2 keywords for search.
   - `camera_motion`: 'zoom_in', 'zoom_out', 'pan_left', or 'pan_right'.

Format response strictly as valid JSON without markdown code ticks or commentary:
{{
  "title": "Title here",
  "scenes": [ ... ]
}}"""

def parse_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError("Could not parse JSON from model output")

async def generate_script_gemini(topic: str, duration_minutes: int, target_sentences: int, api_key: str) -> Dict[str, Any]:
    prompt = build_system_prompt(duration_minutes, target_sentences, topic)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
    }
    candidate_models = ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-pro"]
    last_err = None
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return parse_json_from_text(raw_text)
                else:
                    last_err = f"{model_name} HTTP {res.status_code}: {res.text[:120]}"
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

async def generate_script_pollinations(topic: str, duration_minutes: int, target_sentences: int) -> Dict[str, Any]:
    prompt = (
        f"Generate a video storyboard JSON for topic: '{topic}'.\n"
        f"Length: EXACTLY {duration_minutes} minute ({duration_minutes * 60} seconds).\n"
        f"Provide exactly {target_sentences} scenes.\n"
        "RULE: Each scene's 'narration' MUST be EXACTLY ONE single sentence of 12 to 14 words.\n"
        "Return strictly valid JSON:\n"
        "{\n"
        '  "title": "...",\n'
        '  "scenes": [\n'
        "    {\n"
        '      "scene_id": 1,\n'
        '      "chapter": "Chapter Name",\n'
        '      "narration": "One single punchy sentence of 12-14 words.",\n'
        '      "image_prompt": "Cinematic 8k photorealistic scene description",\n'
        '      "broll_query": "search query",\n'
        '      "camera_motion": "zoom_in"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Output ONLY pure JSON. No markdown ticks."
    )
    encoded = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(url)
        res.raise_for_status()
        return parse_json_from_text(res.text)

def generate_fallback_storyboard(topic: str, target_sentences: int) -> Dict[str, Any]:
    """Guaranteed high-quality 1-sentence-per-scene fallback directly focused on the prompt topic."""
    raw_sentences = [
        ("The Overture", f"Underneath tempestuous skies, {topic} begins with breathtaking speed and anticipation."),
        ("The Stance", f"Every muscle tenses as {topic} commands total control over the surrounding battle arena."),
        ("The Surge", f"A sudden clash of superhuman power ignites the stormy air with blazing kinetic energy."),
        ("The Motion", f"Moving faster than the human eye can perceive, {topic} weaves through the raging tempest."),
        ("The Confrontation", f"Fierce adversaries collide head on, exchanging devastating strikes that fracture the silence."),
        ("The Technique", f"With peerless mastery, {topic} unleashes an ancient secret art against overwhelming odds."),
        ("The Turning Point", f"Momentum violently shifts as an ethereal aura illuminates the shadows in dramatic fashion."),
        ("The Strike", f"Delivering a decisive and breathtaking maneuver, {topic} shatters the enemy offensive."),
        ("The Climax", f"Mid-air raindrops freeze momentarily in time, bearing witness to ultimate warrior discipline."),
        ("The Aftermath", f"As the rain softly tapers off, the unforgettable triumph of {topic} stands absolute.")
    ]
    
    scenes = []
    for i in range(target_sentences):
        idx = i % len(raw_sentences)
        chapter, narration = raw_sentences[idx]
        motion = MOTIONS[i % len(MOTIONS)]
        scenes.append({
            "scene_id": i + 1,
            "chapter": f"{chapter} #{i+1}",
            "narration": narration,
            "image_prompt": (
                f"Dynamic action shot of {topic}, dramatic lighting, intense focus, crisp details, 8k"
            ),
            "broll_query": f"{topic} action",
            "camera_motion": motion
        })
        
    return {
        "title": f"The Tale of {topic.title()}",
        "topic": topic,
        "scenes": scenes
    }

async def generate_script(topic: str, duration_minutes: int = 1, api_key: Optional[str] = None, art_style: str = "anime") -> Dict[str, Any]:
    from app.config import GEMINI_API_KEY
    active_key = api_key if (api_key and api_key.strip()) else GEMINI_API_KEY

    if duration_minutes <= 1:
        target_sentences = 10
    elif duration_minutes <= 3:
        target_sentences = 28
    elif duration_minutes <= 5:
        target_sentences = 48
    else:
        target_sentences = max(50, duration_minutes * 9)

    data = None
    # 1. Try Gemini
    if active_key and active_key.strip():
        try:
            data = await generate_script_gemini(topic, duration_minutes, target_sentences, active_key.strip())
        except Exception as e:
            print(f"[ScriptEngine] Gemini error: {e}. Trying Pollinations...")

    # 2. Try Pollinations
    if not data or "scenes" not in data or len(data["scenes"]) == 0:
        try:
            data = await generate_script_pollinations(topic, duration_minutes, target_sentences)
        except Exception as e:
            print(f"[ScriptEngine] Pollinations error: {e}. Using deterministic fallback...")

    # 3. Fallback
    if not data or "scenes" not in data or len(data["scenes"]) == 0:
        data = generate_fallback_storyboard(topic, target_sentences)

    # Post-process: Guarantee 1 sentence per scene & exact sentence count
    raw_scenes = data.get("scenes", [])
    normalized_scenes = split_and_normalize_scenes(raw_scenes, target_sentences, topic, art_style=art_style)
    
    # If still fewer than target_sentences, pad with tailored sentences
    if len(normalized_scenes) < target_sentences:
        fallback = generate_fallback_storyboard(topic, target_sentences)["scenes"]
        while len(normalized_scenes) < target_sentences:
            next_idx = len(normalized_scenes)
            pad_scene = dict(fallback[next_idx % len(fallback)])
            pad_scene["scene_id"] = next_idx + 1
            normalized_scenes.append(pad_scene)
            
    data["scenes"] = normalized_scenes
    data["target_duration_seconds"] = duration_minutes * 60.0
    return data
