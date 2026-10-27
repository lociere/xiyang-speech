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
  }
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

  setInterval(async () => renderHealth(await getHealth()), 15000);
}

bootstrap();
