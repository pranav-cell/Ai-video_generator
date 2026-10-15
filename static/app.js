document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const form = document.getElementById("generatorForm");
  const topicInput = document.getElementById("topicInput");
  const durationSelect = document.getElementById("durationSelect");
  const aspectRatioSelect = document.getElementById("aspectRatioSelect");
  const voiceSelect = document.getElementById("voiceSelect");
  const bgmMoodSelect = document.getElementById("bgmMoodSelect");
  const visualModeSelect = document.getElementById("visualModeSelect");
  const generateBtn = document.getElementById("generateBtn");

  const progressContainer = document.getElementById("progressContainer");
  const progressTitle = document.getElementById("progressTitle");
  const progressMessage = document.getElementById("progressMessage");
  const progressPercent = document.getElementById("progressPercent");
  const progressBar = document.getElementById("progressBar");

  const stepScript = document.getElementById("step-script");
  const stepVoice = document.getElementById("step-voice");
  const stepVisual = document.getElementById("step-visual");
  const stepRender = document.getElementById("step-render");

  const playerContainer = document.getElementById("playerContainer");
  const playerPlaceholder = document.getElementById("playerPlaceholder");
  const videoPlayer = document.getElementById("videoPlayer");
  const videoSource = document.getElementById("videoSource");
  const videoTrack = document.getElementById("videoTrack");
  const playerActions = document.getElementById("playerActions");
  const downloadBtn = document.getElementById("downloadBtn");
  const openSubtitlesBtn = document.getElementById("openSubtitlesBtn");
  const videoDurationBadge = document.getElementById("videoDurationBadge");
  const historyList = document.getElementById("historyList");

  // Settings Modal Elements
  const settingsBtn = document.getElementById("settingsBtn");
  const settingsModal = document.getElementById("settingsModal");
  const closeSettingsBtn = document.getElementById("closeSettingsBtn");
  const saveSettingsBtn = document.getElementById("saveSettingsBtn");
  const geminiKeyInput = document.getElementById("geminiKeyInput");
  const pexelsKeyInput = document.getElementById("pexelsKeyInput");

  // Load saved settings
  geminiKeyInput.value = localStorage.getItem("auravideo_gemini_key") || "";
  pexelsKeyInput.value = localStorage.getItem("auravideo_pexels_key") || "";

  // Preset chips click
  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      topicInput.value = chip.getAttribute("data-prompt");
      topicInput.focus();
    });
  });

  // Settings modal handlers
  settingsBtn.addEventListener("click", () => settingsModal.classList.remove("hidden"));
  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.add("hidden"));
  saveSettingsBtn.addEventListener("click", () => {
    localStorage.setItem("auravideo_gemini_key", geminiKeyInput.value.trim());
    localStorage.setItem("auravideo_pexels_key", pexelsKeyInput.value.trim());
    settingsModal.classList.add("hidden");
  });

  let pollInterval = null;
  let currentJobId = null;

  // Form Submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const topic = topicInput.value.trim();
    if (!topic) return;

    // Reset progress UI
    generateBtn.disabled = true;
    generateBtn.innerHTML = `<span>Generating...</span>`;
    progressContainer.classList.remove("hidden");
    progressBar.style.width = "5%";
    progressPercent.textContent = "5%";
    progressTitle.textContent = "Preparing Video Pipeline...";
    progressMessage.textContent = "Connecting to generation engine...";
    resetStepNodes();

    const payload = {
      topic: topic,
      duration_minutes: parseInt(durationSelect.value, 10),
      aspect_ratio: aspectRatioSelect.value,
      voice: voiceSelect.value,
      visual_mode: visualModeSelect.value,
      bgm_mood: bgmMoodSelect.value,
      gemini_api_key: localStorage.getItem("auravideo_gemini_key") || null,
      pexels_api_key: localStorage.getItem("auravideo_pexels_key") || null
    };

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start generation");
      }

      const data = await res.json();
      currentJobId = data.job_id;
      startPolling(currentJobId);

    } catch (err) {
      alert("Error: " + err.message);
      generateBtn.disabled = false;
      generateBtn.innerHTML = `<span>⚡</span><span>Generate Full Video Now</span>`;
      progressContainer.classList.add("hidden");
    }
  });

  function resetStepNodes() {
    [stepScript, stepVoice, stepVisual, stepRender].forEach(node => {
      node.classList.remove("active", "completed");
    });
    stepScript.classList.add("active");
  }

  function updateStepsByStatus(status) {
    if (status === "scripting") {
      stepScript.classList.add("active");
    } else if (status === "voicing") {
      stepScript.classList.add("completed");
      stepScript.classList.remove("active");
      stepVoice.classList.add("active");
    } else if (status === "visualizing") {
      stepScript.classList.add("completed");
      stepVoice.classList.add("completed");
      stepVoice.classList.remove("active");
      stepVisual.classList.add("active");
    } else if (status === "rendering_clips" || status === "assembling") {
      stepScript.classList.add("completed");
      stepVoice.classList.add("completed");
      stepVisual.classList.add("completed");
      stepVisual.classList.remove("active");
      stepRender.classList.add("active");
    } else if (status === "completed") {
      [stepScript, stepVoice, stepVisual, stepRender].forEach(node => {
        node.classList.remove("active");
        node.classList.add("completed");
      });
    }
  }

  function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`);
        if (!res.ok) return;

        const data = await res.json();
        const progress = data.progress || 0;
        
        progressBar.style.width = `${progress}%`;
        progressPercent.textContent = `${progress}%`;
        progressMessage.textContent = data.step_message || "Working...";

        updateStepsByStatus(data.status);

        if (data.status === "completed") {
          clearInterval(pollInterval);
          onGenerationComplete(data);
        } else if (data.status === "failed") {
          clearInterval(pollInterval);
          onGenerationFailed(data.error);
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    }, 1200);
  }

  function onGenerationComplete(data) {
    generateBtn.disabled = false;
    generateBtn.innerHTML = `<span>⚡</span><span>Generate Another Video</span>`;
    progressTitle.textContent = "Video Generation Complete! 🎉";
    progressMessage.textContent = "Your video has been rendered and encoded successfully.";

    // Configure and reveal player
    playerPlaceholder.classList.add("hidden");
    videoPlayer.classList.remove("hidden");
    
    // Set aspect ratio class
    if (aspectRatioSelect.value === "9:16") {
      playerContainer.style.aspectRatio = "9/16";
      playerContainer.style.maxWidth = "360px";
      playerContainer.style.margin = "0 auto";
    } else {
      playerContainer.style.aspectRatio = "16/9";
      playerContainer.style.maxWidth = "100%";
      playerContainer.style.margin = "0";
    }

    // Set video sources
    videoSource.src = data.video_url;
    if (data.vtt_url) {
      videoTrack.src = data.vtt_url;
    }
    videoPlayer.load();
    videoPlayer.play().catch(() => {});

    // Actions
    playerActions.classList.remove("hidden");
    downloadBtn.href = `/api/video/${data.job_id}/download`;

    // Duration badge
    if (data.total_duration) {
      const mins = Math.floor(data.total_duration / 60);
      const secs = Math.floor(data.total_duration % 60);
      videoDurationBadge.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
      videoDurationBadge.classList.remove("hidden");
    }

    loadHistory();
  }

  function onGenerationFailed(err) {
    generateBtn.disabled = false;
    generateBtn.innerHTML = `<span>⚡</span><span>Retry Generation</span>`;
    progressTitle.textContent = "Generation Failed";
    progressMessage.textContent = err || "An unexpected error occurred during rendering.";
    progressBar.style.background = "#ef4444";
  }

  // Open subtitles in new tab
  openSubtitlesBtn.addEventListener("click", () => {
    if (currentJobId) {
      window.open(`/api/video/${currentJobId}/subtitles.vtt`, "_blank");
    }
  });

  // Load Past Videos
  async function loadHistory() {
    try {
      const res = await fetch("/api/history");
      if (!res.ok) return;
      const list = await res.json();
      
      if (!list || list.length === 0) {
        historyList.innerHTML = `<p class="empty-history">No previous generations found.</p>`;
        return;
      }

      historyList.innerHTML = list.map(item => `
        <div class="history-card" data-jobid="${item.job_id}" data-ratio="${item.aspect_ratio || '16:9'}">
          <h5>${item.title || item.topic}</h5>
          <p>${item.duration_seconds ? Math.round(item.duration_seconds) + 's' : ''} • ${item.scenes_count || 0} scenes • ${item.aspect_ratio || '16:9'}</p>
        </div>
      `).join("");

      // Bind click
      document.querySelectorAll(".history-card").forEach(card => {
        card.addEventListener("click", () => {
          const jid = card.getAttribute("data-jobid");
          const ratio = card.getAttribute("data-ratio");
          loadPastVideo(jid, ratio);
        });
      });
    } catch (e) {
      console.error("Failed to load history:", e);
    }
  }

  function loadPastVideo(jobId, ratio) {
    currentJobId = jobId;
    playerPlaceholder.classList.add("hidden");
    videoPlayer.classList.remove("hidden");

    if (ratio === "9:16") {
      playerContainer.style.aspectRatio = "9/16";
      playerContainer.style.maxWidth = "360px";
      playerContainer.style.margin = "0 auto";
    } else {
      playerContainer.style.aspectRatio = "16/9";
      playerContainer.style.maxWidth = "100%";
      playerContainer.style.margin = "0";
    }

    videoSource.src = `/api/video/${jobId}/stream`;
    videoTrack.src = `/api/video/${jobId}/subtitles.vtt`;
    videoPlayer.load();
    videoPlayer.play().catch(() => {});

    playerActions.classList.remove("hidden");
    downloadBtn.href = `/api/video/${jobId}/download`;
  }

  // Initial load
  loadHistory();
});
