import { getHealth } from "./api.js";
import { initAsr } from "./asr.js";
import { initTts } from "./tts.js";
import { initTalk } from "./talk.js";

const statusDots = {
  asr: document.querySelector('[data-status="asr"] .dot'),
  tts: document.querySelector('[data-status="tts"] .dot'),
  talk: document.querySelector('[data-status="talk"] .dot'),
};

function renderHealth(health) {
  for (const key of Object.keys(statusDots)) {
    const online = Boolean(health && health[key]);
    statusDots[key].classList.toggle("is-online", online);
    statusDots[key].classList.toggle("is-offline", !online);
    const label = statusDots[key].parentElement.querySelector(".service-label");
    const name = { asr: "识别", tts: "合成", talk: "说话人" }[key];
    const state = health.models?.[key];
    const labels = { standby: "待命", loading: "准备中", ready: "已加载", busy: "处理中", stopping: "释放中" };
    label.textContent = name + (online ? (labels[state] || "待命") : "不可用");
  }
  document.dispatchEvent(new Event("service-health"));
  const hint = document.getElementById("service-readiness");
  const ready = health && health.asr && health.tts && health.talk;
  hint.textContent = ready ? "模型按需准备，首次使用或切换功能时需要稍候；任务按提交顺序处理。" : "应用暂时不可用，正在尝试重新连接。";
  hint.classList.remove("is-hidden");
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const name = tab.dataset.tab;
      tabs.forEach((t) => t.classList.toggle("is-active", t === tab));
      panels.forEach((p) => p.classList.toggle("is-active", p.dataset.panel === name));
    });
  });
}

async function bootstrap() {
  setupTabs();

  const health = await getHealth();
  renderHealth(health);

  initAsr();
  initTts();
  initTalk({ talkMock: Boolean(health && health.talk_mock) });

  async function pollHealth() {
    renderHealth(await getHealth());
    setTimeout(pollHealth, 5000);
  }
  setTimeout(pollHealth, 5000);
}

bootstrap();
