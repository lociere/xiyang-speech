import { requestBlob, errorMessage } from "./api.js";
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

  function refresh() {
    countEl.textContent = String(textEl.value.length);
    submitBtn.disabled = textEl.value.trim().length === 0;
  }

  textEl.addEventListener("input", refresh);

  submitBtn.addEventListener("click", async () => {
    const text = textEl.value.trim();
    if (!text) return;

    setBusy(submitBtn, true, "生成中…");
    try {
      lastBlob = await requestBlob("/api/tts/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      playBlob(lastBlob, "audio/wav", audioEl);
      resultEl.classList.remove("is-hidden");
      audioEl.play().catch(() => {});
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setBusy(submitBtn, false);
      refresh();
    }
  });

  downloadBtn.addEventListener("click", () => {
    if (!lastBlob) return;
    downloadBlob(lastBlob, "xiyang_speech.wav");
  });
}
