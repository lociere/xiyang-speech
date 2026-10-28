let health = { asr: false, tts: false, talk: false };
export function serviceReady(name) {
  return Boolean(health[name]);
}

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
    health = await request("/api/health", { signal: AbortSignal.timeout(5000) });
    return health;
  } catch {
    health = { asr: false, tts: false, talk: false, talk_mock: false };
    return health;
  }
}

// Poll separately so model cold starts do not hold the upload request open.
export async function waitJob(jobId, onProgress = () => {}) {
  let failures = 0;
  for (;;) {
    let job;
    try {
      job = await request("/api/jobs/" + jobId, { signal: AbortSignal.timeout(10000) });
      failures = 0;
    } catch (err) {
      if (++failures >= 5) throw new Error("任务连接中断。任务编号：" + jobId + "。请恢复连接后查询，避免重复提交。");
      onProgress({ message: "连接中断，正在重试…" });
      await new Promise(resolve => setTimeout(resolve, 2000));
      continue;
    }
    onProgress(job);
    if (job.status === "error") throw new Error(job.error || "任务失败");
    if (job.status === "done") return job;
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
}
