async function errorFrom(response) {
  let detail = null;
  try {
    const data = await response.json();
    detail = data && data.detail;
  } catch {
    // response body is not JSON
  }
  if (typeof detail === "string" && detail) return detail;
  return `请求失败（${response.status}）`;
}

export async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await errorFrom(response));
  return response.json();
}

export async function requestBlob(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await errorFrom(response));
  return response.blob();
}

export function errorMessage(err) {
  return err && err.message ? err.message : "发生未知错误";
}

export async function getHealth() {
  try {
    return await request("/api/health");
  } catch {
    return { asr: false, tts: false, talk: false, talk_mock: false };
  }
}
