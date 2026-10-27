let toastEl = null;
let toastTimer = null;

function getToast() {
  if (!toastEl) toastEl = document.getElementById("toast");
  return toastEl;
}

export function toast(message) {
  const el = getToast();
  if (!el) return;
  el.textContent = message;
  el.classList.remove("is-hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("is-hidden"), 2600);
}

export function setBusy(button, busy, busyLabel = "处理中…") {
  if (busy) {
    button.dataset.idleLabel = button.textContent;
    button.textContent = busyLabel;
    button.classList.add("is-busy");
    button.disabled = true;
  } else {
    button.textContent = button.dataset.idleLabel || button.textContent;
    button.classList.remove("is-busy");
    button.disabled = false;
  }
}

export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to legacy approach
    }
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand("copy");
    return true;
  } catch {
    return false;
  } finally {
    ta.remove();
  }
}
