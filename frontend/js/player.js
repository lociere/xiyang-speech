export function playBlob(blob, mime, element) {
  const url = URL.createObjectURL(blob);
  const previous = element.dataset.objectUrl;
  if (previous) URL.revokeObjectURL(previous);
  element.dataset.objectUrl = url;
  element.src = url;
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  downloadUrl(url, filename);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadUrl(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
