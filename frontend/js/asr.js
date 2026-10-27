import { request, errorMessage } from "./api.js";
import { toast, setBusy, copyText } from "./ui.js";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function initAsr() {
  const dropzone = document.getElementById("asr-dropzone");
  const fileInput = document.getElementById("asr-file");
  const chip = document.getElementById("asr-file-chip");
  const submitBtn = document.getElementById("asr-submit");
  const resultEl = document.getElementById("asr-result");
  const textEl = document.getElementById("asr-text");
  const copyBtn = document.getElementById("asr-copy");

  let file = null;

  function setFile(next) {
    file = next;
    if (next) {
      chip.textContent = `${next.name}（${formatSize(next.size)}）`;
      chip.classList.remove("is-hidden");
    } else {
      chip.classList.add("is-hidden");
    }
    refreshSubmit();
  }

  function refreshSubmit() {
    submitBtn.disabled = !file;
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
    if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => setFile(fileInput.files[0] || null));

  submitBtn.addEventListener("click", async () => {
    if (!file) return;
    const form = new FormData();
    form.append("audio", file);

    setBusy(submitBtn, true, "识别中…");
    try {
      const data = await request("/api/asr/recognize", { method: "POST", body: form });
      textEl.textContent = data.text || "";
      resultEl.classList.remove("is-hidden");
    } catch (err) {
      toast(errorMessage(err));
    } finally {
      setBusy(submitBtn, false);
      refreshSubmit();
    }
  });

  copyBtn.addEventListener("click", async () => {
    const text = textEl.textContent;
    if (!text) return;
    const ok = await copyText(text);
    toast(ok ? "已复制" : "复制失败，请手动选择复制");
  });
}
