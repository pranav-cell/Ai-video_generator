# AuraVideo — AI Faceless Video Generator (100% Free & Local)

A complete, production-ready AI faceless video generation studio that creates 5–10 minute documentary, explainer, or viral short-form videos from a single prompt **without any paid tools, subscriptions, or credit cards**.

---

## 🌟 How the 100% Free Pipeline Works

| Stage | Free Tool / Engine | Cost | Description |
| :--- | :--- | :--- | :--- |
| **1. Scriptwriting & Storyboard** | **Pollinations AI / Gemini Free API** | **$0** | Automatically crafts a viral multi-chapter script with visual descriptions, b-roll search queries, and narration. |
| **2. Neural Voiceover** | **Microsoft Edge-TTS** (`edge-tts`) | **$0** | Ultra-realistic, high-fidelity human narration with automatic word & sentence boundary timestamps. |
| **3. Photorealistic Visuals** | **FLUX.1 via Pollinations.ai** | **$0** | High-definition AI-generated scene imagery (1920x1080 or 1080x1920) matching each scene. |
| **4. Stock B-Roll (Optional)** | **Pexels Video API** | **$0** | Free commercial stock video clips for realistic hybrid footage. |
| **5. Dynamic Camera Motion** | **FFmpeg Ken Burns Engine** | **$0** | Applies cinematic camera pans (`zoom_in`, `zoom_out`, `pan_left`, `pan_right`) so images never look static. |
| **6. Soundscape & Audio Ducking** | **Procedural FFmpeg Audio Synth** | **$0** | Generates ambient/cinematic background music ducked at -18dB under narration. |
| **7. Fast Hardware Encoding** | **Apple Silicon FFmpeg** | **$0** | Hardware-accelerated local rendering into web-optimized H.264 MP4. |

---

## 🚀 Quick Start

### 1. Launch the Studio
In your terminal, navigate to the project directory and run:
```bash
./run.sh
```
Or start manually:
```bash
source venv/bin/activate
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open the Dashboard
Open your browser and navigate to:
```
http://localhost:8000
```

---

## ⚙️ Features & Controls

1. **Duration Options**:
   - `1 Minute`: Fast test preview (~7–8 scenes)
   - `3 Minutes`: Standard explainer (~20 scenes)
   - `5 Minutes`: Deep dive (~35 scenes)
   - `10 Minutes`: Full documentary (~70 scenes)
2. **Aspect Ratios**:
   - `16:9 Landscape`: Standard YouTube videos.
   - `9:16 Vertical`: YouTube Shorts, Instagram Reels, and TikTok.
3. **Voice Narrators**:
   - Christopher (Deep Documentary - Male)
   - Guy (Casual & Tech - Male)
   - Jenny (Warm & Natural - Female)
   - Aria (Dynamic & Engaging - Female)
   - Ryan (British Sophisticated - Male)
   - Prabhat (Indian English Clear - Male)
4. **Subtitles & Captions**:
   - Automatically generated `.srt` and `.vtt` tracks embedded directly into the video player and downloadable file.
5. **Video Library**:
   - All rendered videos are saved locally to `outputs/` with JSON metadata, scene audio files, and subtitles.

---

## 🔑 Optional API Keys (100% Free)

The generator works completely out-of-the-box with **zero keys**. However, you can enhance quality by clicking the **Settings (gear)** icon in the top right of the dashboard:
- **Google Gemini API Key**: [Get Free Key from Google AI Studio](https://aistudio.google.com/app/apikey).
- **Pexels API Key**: [Get Free Key from Pexels](https://www.pexels.com/api/) to fetch real stock B-roll video clips.
