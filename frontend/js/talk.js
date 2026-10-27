import { request, errorMessage } from "./api.js";
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

  if (talkMock) {
    badgeEl.textContent = "演示模式：暂未接入真实模型，返回示例视频";
    badgeEl.classList.remove("is-hidden");
  }

  function refresh() {
    const hasImage = Boolean(imageFile);
    const hasText = textEl.value.trim().length > 0;
    const hasAudio = Boolean(audioInput.files[0]);
    submitBtn.disabled = !hasImage || (!hasText && !hasAudio);
  }

  function setImage(next) {
    imageFile = next;
    const content = dropzone.querySelector(".dropzone__content");
    if (next) {
      preview.src = URL.createObjectURL(next);
      preview.classList.remove("is-hidden");
      content.classList.add("is-hidden");
    } else {
      preview.src = "";
      preview.classList.add("is-hidden");
      content.classList.remove("is-hidden");
    }
    refresh();
  }

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
    if (!imageFile) return;

    const form = new FormData();
    form.append("image", imageFile);
    if (textEl.value.trim()) form.append("text", textEl.value.trim());
    if (audioInput.files[0]) form.append("audio", audioInput.files[0]);

    progressEl.classList.remove("is-hidden");
    resultEl.classList.add("is-hidden");
    setBusy(submitBtn, true, "提交中…");

    try {
      const data = await request("/api/talk", { method: "POST", body: form });
      setBusy(submitBtn, false);
      refresh();
      startPolling(data.job_id);
    } catch (err) {
      toast(errorMessage(err));
      setBusy(submitBtn, false);
      refresh();
      progressEl.classList.add("is-hidden");
    }
  });

  function startPolling(jobId) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const job = await request(`/api/talk/${jobId}`);
        updateProgress(job);

        if (job.status === "done") {
          clearInterval(pollTimer);
          lastVideoUrl = job.video_url;
          videoEl.src = job.video_url;
          resultEl.classList.remove("is-hidden");
          progressEl.classList.add("is-hidden");
          videoEl.play().catch(() => {});
        } else if (job.status === "error") {
          clearInterval(pollTimer);
          progressEl.classList.add("is-hidden");
          toast(job.error || "生成失败");
        }
      } catch (err) {
        clearInterval(pollTimer);
        progressEl.classList.add("is-hidden");
        toast(errorMessage(err));
      }
    }, 1000);
  }

  function updateProgress(job) {
    const p = Math.max(0, Math.min(100, job.progress || 0));
    progressFill.style.width = `${p}%`;
    progressLabel.textContent = job.status === "running" ? `生成中… ${p}%` : `排队中… ${p}%`;
  }

  downloadBtn.addEventListener("click", () => {
    if (lastVideoUrl) downloadUrl(lastVideoUrl, "xiyang_talk.mp4");
  });
}
