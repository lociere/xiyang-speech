import { request, requestBlob, waitJob, errorMessage, serviceReady } from "./api.js";
import { toast, setBusy } from "./ui.js";
import { playBlob, downloadBlob } from "./player.js";

export function initTts() {
  const textEl = document.getElementById("tts-text");
  const countEl = document.getElementById("tts-count");
  const submitBtn = document.getElementById("tts-submit");
  const resultEl = document.getElementById("tts-result");
  const audioEl = document.getElementById("tts-audio");
  const downloadBtn = document.getElementById("tts-download");

  let lastBlob = null;
  let busy = false;

  function refresh() {
    countEl.textContent = String(textEl.value.length);
    submitBtn.disabled = busy || !serviceReady("tts") || textEl.value.trim().length === 0;
  }

  textEl.addEventListener("input", refresh);
  document.addEventListener("service-health", refresh);
  refresh();

  submitBtn.addEventListener("click", async () => {
    const text = textEl.value.trim();
    if (busy || !serviceReady("tts") || !text) return;

    busy = true;
    setBusy(submitBtn, true, "生成中…");
    try {
      const submitted = await request("/api/tts/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const job = await waitJob(submitted.job_id, state => {
        submitBtn.textContent = state.message || "等待中…";
      });
      lastBlob = await requestBlob(job.result_url);
      playBlob(lastBlob, "audio/wav", audioEl);
      resultEl.classList.remove("is-hidden");
      audioEl.play().catch(() => {});
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      busy = false;
      setBusy(submitBtn, false);
      refresh();
    }
  });

  downloadBtn.addEventListener("click", () => {
    if (!lastBlob) return;
    downloadBlob(lastBlob, "xiyang_speech.wav");
  });
}
