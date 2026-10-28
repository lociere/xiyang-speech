import { request, errorMessage, serviceReady } from "./api.js";
import { toast, setBusy } from "./ui.js";
import { downloadUrl } from "./player.js";

export function initTalk({ talkMock }) {
  const dropzone = document.getElementById("talk-dropzone");
  const fileInput = document.getElementById("talk-file");
  const preview = document.getElementById("talk-preview");
  const textEl = document.getElementById("talk-text");
  const audioInput = document.getElementById("talk-audio");
  const submitBtn = document.getElementById("talk-submit");
  const progressEl = document.getElementById("talk-progress");
  const progressFill = document.getElementById("talk-progress-fill");
  const progressLabel = document.getElementById("talk-progress-label");
  const resultEl = document.getElementById("talk-result");
  const videoEl = document.getElementById("talk-video");
  const downloadBtn = document.getElementById("talk-download");
  const badgeEl = document.getElementById("talk-badge");

  let imageFile = null;
  let pollTimer = null;
  let lastVideoUrl = null;
  let usedText = false;
  let busy = false;
  let previewUrl = null;

  if (talkMock) {
    badgeEl.textContent = "演示模式：暂未接入真实模型，返回示例视频";
    badgeEl.classList.remove("is-hidden");
  }

  function refresh() {
    const hasImage = Boolean(imageFile);
    const hasText = textEl.value.trim().length > 0;
    const hasAudio = Boolean(audioInput.files[0]);
    submitBtn.disabled = busy || !serviceReady("talk") || (hasText && !serviceReady("tts"))
      || !hasImage || (!hasText && !hasAudio);
  }

  function setImage(next) {
    imageFile = next;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const content = dropzone.querySelector(".dropzone__content");
    if (next) {
      previewUrl = URL.createObjectURL(next);
      preview.src = previewUrl;
      preview.classList.remove("is-hidden");
      content.classList.add("is-hidden");
    } else {
      preview.src = "";
      preview.classList.add("is-hidden");
      content.classList.remove("is-hidden");
    }
    refresh();
  }

  document.addEventListener("service-health", refresh);
  refresh();

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
    if (e.dataTransfer.files.length) setImage(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => setImage(fileInput.files[0] || null));
  textEl.addEventListener("input", refresh);
  audioInput.addEventListener("change", refresh);

  submitBtn.addEventListener("click", async () => {
    if (busy || submitBtn.disabled || !imageFile) return;
    if (textEl.value.trim() && audioInput.files[0]) {
      toast("文字与音频请选择一种输入");
      return;
    }
    busy = true;

    usedText = Boolean(textEl.value.trim());

    const form = new FormData();
    form.append("image", imageFile);
    if (usedText) form.append("text", textEl.value.trim());
    if (audioInput.files[0]) form.append("audio", audioInput.files[0]);

    progressEl.classList.remove("is-hidden");
    resultEl.classList.add("is-hidden");
    setBusy(submitBtn, true, "提交中…");

    try {
      const data = await request("/api/talk", { method: "POST", body: form });
      submitBtn.textContent = "生成中…";
      startPolling(data.job_id);
    } catch (err) {
      toast(errorMessage(err));
      busy = false;
      setBusy(submitBtn, false);
      refresh();
      progressEl.classList.add("is-hidden");
    }
  });

  function finish() {
    busy = false;
    setBusy(submitBtn, false);
    refresh();
    progressEl.classList.add("is-hidden");
    sessionStorage.removeItem("talk-job");
  }

  function startPolling(jobId) {
    clearTimeout(pollTimer);
    sessionStorage.setItem("talk-job", JSON.stringify({ jobId, usedText }));
    let failures = 0;
    async function poll() {
      try {
        const job = await request("/api/talk/" + jobId, { signal: AbortSignal.timeout(10000) });
        failures = 0;
        updateProgress(job);
        if (job.status === "done") {
          lastVideoUrl = job.video_url;
          videoEl.src = job.video_url;
          resultEl.classList.remove("is-hidden");
          finish();
          videoEl.play().catch(() => {});
          return;
        }
        if (job.status === "error") {
          finish();
          toast(job.error || "生成失败");
          return;
        }
      } catch (err) {
        failures += 1;
        if (failures >= 5) {
          busy = false;
          setBusy(submitBtn, false);
          refresh();
          progressLabel.textContent = "连接中断，可刷新页面继续查询任务。";
          toast(errorMessage(err));
          return;
        }
        progressLabel.textContent = "连接中断，正在重试…";
      }
      pollTimer = setTimeout(poll, 1500);
    }
    poll();
  }

  try {
    const saved = JSON.parse(sessionStorage.getItem("talk-job"));
    if (saved && saved.jobId) {
      busy = true;
      usedText = saved.usedText;
      setBusy(submitBtn, true, "查询任务中…");
      progressEl.classList.remove("is-hidden");
      startPolling(saved.jobId);
    }
  } catch {
    sessionStorage.removeItem("talk-job");
  }

  function updateProgress(job) {
    const p = Math.max(0, Math.min(100, job.progress || 0));
    progressFill.style.width = `${p}%`;
    progressLabel.textContent = job.message || "等待处理…";
  }

  downloadBtn.addEventListener("click", () => {
    if (lastVideoUrl) downloadUrl(lastVideoUrl, "xiyang_talk.mp4");
  });
}
