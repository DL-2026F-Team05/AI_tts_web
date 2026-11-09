"use strict";
// 패키지 읽어주기 웹 데모. 담당: 박세준
// 흐름: 사진 → /api/analyze → 요약 음성 재생 (서버 음성이 없으면 브라우저 음성)

const DEFAULT_SETTINGS = { allergens: [], speed: 1.0, srMode: false, waitSound: true };
const SETTINGS_KEY = "packreader.settings.v1";
const SILENT_WAV =
  "data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const RISK_TEXT = { danger: "위험", caution: "주의", ok: "특이사항 없음", unknown: "확인 필요" };
const KIND_TEXT = { use_by: "소비기한", sell_by: "유통기한", best_before: "품질유지기한", unknown: "종류 모름" };
const STATUS_TEXT = { ok: "남음", soon: "곧 지남", expired: "지남", elsewhere: "다른 면에 표기", unknown: "판단 보류" };
const REGION_STYLE = {
  product_name: ["제품명", "#7a5af8"],
  expiry: ["소비기한", "#d92d20"],
  allergen: ["알레르기", "#f79009"],
  ingredients: ["원재료", "#0e9384"],
  nutrition: ["영양정보", "#2e90fa"],
  caution: ["주의사항", "#667085"],
  other: ["기타", "#98a2b3"],
  none: ["영역 없음", "#98a2b3"],
};

const $ = (sel) => document.querySelector(sel);
const player = $("#player");

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return Object.assign({}, DEFAULT_SETTINGS, JSON.parse(raw));
  } catch (e) { /* 저장소를 못 쓰는 환경 */ }
  return Object.assign({}, DEFAULT_SETTINGS);
}
function saveSettings() {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings)); } catch (e) { /* 무시 */ }
}

const state = {
  settings: loadSettings(),
  result: null,
  audioUrl: null,
  detailAudioUrl: null,
  imageUrl: null,
  t0: 0,
  busy: false,
  label: "",
};

// ---------------------------------------------------------------- 소리 준비
// 모바일 브라우저는 사용자가 누른 순간에만 소리를 낼 수 있어서, 첫 터치 때 무음을 한 번 재생해 둔다.
let audioCtx = null;
let unlocked = false;
function unlockAudio() {
  if (unlocked) return;
  unlocked = true;
  try { player.src = SILENT_WAV; const p = player.play(); if (p) p.catch(() => {}); } catch (e) {}
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) { audioCtx = new AC(); if (audioCtx.resume) audioCtx.resume(); }
  } catch (e) {}
  try {
    if ("speechSynthesis" in window) {
      const u = new SpeechSynthesisUtterance(" ");
      u.volume = 0;
      speechSynthesis.speak(u);
    }
  } catch (e) {}
}
document.addEventListener("pointerdown", unlockAudio, { passive: true });
document.addEventListener("keydown", unlockAudio);

let tickTimer = null;
function startWaiting() {
  stopWaiting();
  if (!state.settings.waitSound || !audioCtx) return;
  const tick = () => {
    try {
      const t = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.frequency.value = 660;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.12, t + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.13);
    } catch (e) {}
  };
  tick();
  tickTimer = setInterval(tick, 1000);
}
function stopWaiting() {
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
}

// ---------------------------------------------------------------- 말하기
let koVoice = null;
function pickVoice() {
  if (!("speechSynthesis" in window)) return;
  const voices = speechSynthesis.getVoices();
  koVoice = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("ko")) || null;
}
if ("speechSynthesis" in window) {
  pickVoice();
  speechSynthesis.addEventListener("voiceschanged", pickVoice);
}

function announce(text) {
  const el = $("#srAnnounce");
  el.textContent = "";
  setTimeout(() => { el.textContent = text; }, 60);
}

function stopSpeaking() {
  try { player.pause(); } catch (e) {}
  try { if ("speechSynthesis" in window) speechSynthesis.cancel(); } catch (e) {}
}

function speakBrowser(text, kind) {
  if (!("speechSynthesis" in window)) { announce(text); return; }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ko-KR";
  u.rate = state.settings.speed;
  if (koVoice) u.voice = koVoice;
  u.onstart = () => markFirstAudio(kind, "browser");
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

function say(url, text, kind) {
  stopSpeaking();
  if (state.settings.srMode) { announce(text); return; }
  if (url) {
    player.src = url;
    player.onplaying = () => markFirstAudio(kind, state.result && state.result.audio ? state.result.audio.engine : "server");
    const p = player.play();
    if (p) p.catch(() => speakBrowser(text, kind));
  } else {
    speakBrowser(text, kind);
  }
}

function markFirstAudio(kind, engine) {
  if (kind !== "summary" || !state.t0) return;
  const ms = Math.round(performance.now() - state.t0);
  state.t0 = 0;
  setTiming("첫 음성까지", `${(ms / 1000).toFixed(2)}초 (${engine})`);
  postEvent("first_audio", { ms, engine, label: state.label });
}

function postEvent(type, data) {
  try {
    fetch("/api/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, data }) }).catch(() => {});
  } catch (e) {}
}

// ---------------------------------------------------------------- 분석 요청
function setStatus(text, busy) {
  const el = $("#status");
  el.textContent = text;
  el.classList.toggle("busy", !!busy);
  $("#captureBtn").disabled = !!busy;
}

async function downscale(file, maxSide) {
  // 큰 폰 사진은 올리기 전에 줄인다 (터널·모바일 망에서 업로드가 오래 걸려서)
  if (!file || file.size < 1.5 * 1024 * 1024 || !window.createImageBitmap) return file;
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    if (scale >= 1) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    return blob || file;
  } catch (e) {
    return file;
  }
}

async function analyze({ file, sampleId, sampleUrl, label }) {
  if (state.busy) return;
  state.busy = true;
  stopSpeaking();
  setStatus("사진을 읽고 있어요. 잠시만 기다려 주세요.", true);
  startWaiting();
  state.label = label || "";
  state.t0 = performance.now();

  const fd = new FormData();
  if (file) {
    const small = await downscale(file, 2000);
    fd.append("image", small, file.name || "photo.jpg");
    if (state.imageUrl && state.imageUrl.startsWith("blob:")) URL.revokeObjectURL(state.imageUrl);
    state.imageUrl = URL.createObjectURL(small);
  } else {
    fd.append("sample_id", sampleId);
    state.imageUrl = sampleUrl;
  }
  fd.append("allergens", JSON.stringify(state.settings.allergens));
  fd.append("speed", String(state.settings.speed));
  fd.append("audio", state.settings.srMode ? "false" : "true");
  const today = $("#todayInput").value;
  if (today) fd.append("today", today);

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: fd });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error((data && data.detail) || `HTTP ${res.status}`);
    showResult(data);
  } catch (err) {
    showError(err);
  } finally {
    stopWaiting();
    state.busy = false;
  }
}

async function analyzeText() {
  const text = $("#textInput").value.trim();
  if (!text || state.busy) return;
  state.busy = true;
  stopSpeaking();
  setStatus("글자를 분석하고 있어요.", true);
  state.t0 = performance.now();
  state.label = "text";
  state.imageUrl = null;
  try {
    const res = await fetch("/api/analyze-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        allergens: state.settings.allergens,
        today: $("#todayInput").value || null,
        audio: !state.settings.srMode,
        speed: state.settings.speed,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error((data && data.detail) || `HTTP ${res.status}`);
    showResult(data);
  } catch (err) {
    showError(err);
  } finally {
    state.busy = false;
  }
}

function showResult(data) {
  state.result = data;
  state.audioUrl = data.audio ? data.audio.url : null;
  state.detailAudioUrl = null;

  const level = (data.risk && data.risk.level) || "unknown";
  const box = $("#result");
  box.hidden = false;
  box.classList.toggle("danger", level === "danger");
  const badge = $("#riskBadge");
  badge.textContent = RISK_TEXT[level] || level;
  badge.className = `badge ${level}`;
  $("#summary").textContent = data.speech ? data.speech.summary : "";
  const detail = $("#detail");
  detail.hidden = true;
  detail.textContent = "";
  setStatus("", false);

  renderDev(data);
  if (state.settings.srMode) $("#resultTitle").focus();
  say(state.audioUrl, data.speech ? data.speech.summary : "결과가 없어요.", "summary");
}

function showError(err) {
  const msg = "분석하지 못했어요. 다시 시도해 주세요.";
  setStatus(`${msg} (${err && err.message ? err.message : err})`, false);
  state.t0 = 0;
  say(null, msg, "error");
}

async function playDetail() {
  const r = state.result;
  if (!r || !r.speech) return;
  const text = r.speech.detail || "더 알려 드릴 내용이 없어요.";
  const el = $("#detail");
  el.textContent = text;
  el.hidden = false;
  postEvent("more", { label: state.label });
  if (state.settings.srMode) { announce(text); return; }
  if (!state.detailAudioUrl) {
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speed: state.settings.speed }),
      });
      const data = await res.json();
      state.detailAudioUrl = data && data.audio ? data.audio.url : null;
    } catch (e) {
      state.detailAudioUrl = null;
    }
  }
  say(state.detailAudioUrl, text, "detail");
}

function replay() {
  const r = state.result;
  if (!r || !r.speech) return;
  postEvent("replay", { label: state.label });
  say(state.audioUrl, r.speech.summary, "replay");
}

// ---------------------------------------------------------------- 개발자 보기
function setTiming(key, value) {
  const tbody = $("#timingTable tbody");
  let row = Array.from(tbody.rows).find((tr) => tr.dataset.key === key);
  if (!row) {
    row = tbody.insertRow();
    row.dataset.key = key;
    row.insertCell().outerHTML = "<th></th>";
    row.insertCell();
  }
  row.cells[0].textContent = key;
  row.cells[1].textContent = value;
}

function fillTable(tbody, rows) {
  tbody.innerHTML = "";
  for (const [k, v] of rows) {
    const tr = tbody.insertRow();
    const th = document.createElement("th");
    th.textContent = k;
    tr.appendChild(th);
    tr.insertCell().textContent = v;
  }
}

function renderDev(data) {
  const f = data.fields || {};
  const e = f.expiry || {};
  const a = f.allergens || {};
  const pct = (x) => (typeof x === "number" ? `${Math.round(x * 100)}%` : "-");
  fillTable($("#fieldsTable tbody"), [
    ["제품명", f.product_name && f.product_name.value ? `${f.product_name.value} (${pct(f.product_name.conf)})` : "-"],
    ["날짜", e.date ? `${KIND_TEXT[e.kind] || e.kind} ${e.date} · ${STATUS_TEXT[e.status] || e.status}${e.days_left != null ? ` · ${e.days_left}일` : ""} (${pct(e.conf)})` : (STATUS_TEXT[e.status] || "-")],
    ["알레르기 함유", (a.contains || []).join(", ") || "-"],
    ["같은 시설", (a.may_contain || []).join(", ") || "-"],
    ["내 성분과 겹침", [...(a.user_hits || []), ...(a.user_may_hits || []).map((x) => `${x}(혼입)`)].join(", ") || "-"],
    ["위험도", `${RISK_TEXT[data.risk.level] || data.risk.level} ${data.risk.reasons.length ? "· " + data.risk.reasons.join(", ") : ""}`],
    ["사진 품질", data.quality && data.quality.issues.length ? data.quality.issues.join(", ") : "문제 없음"],
    ["오류", (data.errors || []).map((x) => `${x.stage}: ${x.message}`).join(" / ") || "-"],
  ]);
  const t = data.timing_ms || {};
  const rows = Object.keys(t).map((k) => [k, `${t[k]} ms`]);
  rows.push(["엔진", Object.entries(data.engines || {}).map(([k, v]) => `${k}=${v}`).join(", ")]);
  fillTable($("#timingTable tbody"), rows);
  $("#rawJson").textContent = JSON.stringify(data, null, 2);
  drawOverlay(data);
}

function drawOverlay(data) {
  const canvas = $("#overlay");
  const ctx = canvas.getContext("2d");
  const used = new Set();
  const finish = () => {
    $("#legend").innerHTML = Array.from(used)
      .map((r) => `<li><i style="background:${REGION_STYLE[r][1]}"></i>${REGION_STYLE[r][0]}</li>`)
      .join("");
  };
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!state.imageUrl || !data.image) { finish(); return; }
  const img = new Image();
  img.onload = () => {
    const w = data.image.width;
    const h = data.image.height;
    canvas.width = 560;
    canvas.height = Math.round((560 * h) / w);
    const s = canvas.width / w;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2;
    for (const b of data.boxes || []) {
      if (!b.poly) continue;
      const key = b.region || "none";
      used.add(key);
      ctx.strokeStyle = REGION_STYLE[key][1];
      ctx.beginPath();
      b.poly.forEach(([x, y], i) => (i ? ctx.lineTo(x * s, y * s) : ctx.moveTo(x * s, y * s)));
      ctx.closePath();
      ctx.stroke();
    }
    finish();
  };
  img.src = state.imageUrl;
}

// ---------------------------------------------------------------- 설정과 샘플
function renderAllergens(list) {
  const wrap = $("#allergenList");
  wrap.innerHTML = "";
  for (const name of list) {
    const label = document.createElement("label");
    label.className = "chip";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = name;
    input.checked = state.settings.allergens.includes(name);
    input.addEventListener("change", () => {
      const set = new Set(state.settings.allergens);
      if (input.checked) set.add(name); else set.delete(name);
      state.settings.allergens = list.filter((x) => set.has(x));
      saveSettings();
    });
    const span = document.createElement("span");
    span.textContent = name;
    label.append(input, span);
    wrap.appendChild(label);
  }
}

function renderSamples(samples) {
  const wrap = $("#sampleList");
  wrap.innerHTML = "";
  for (const s of samples) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sample";
    btn.setAttribute("aria-label", `샘플: ${s.title}`);
    const img = document.createElement("img");
    img.src = s.url;
    img.alt = "";
    img.loading = "lazy";
    const span = document.createElement("span");
    span.textContent = s.title;
    btn.append(img, span);
    btn.addEventListener("click", () => analyze({ sampleId: s.id, sampleUrl: s.url, label: s.id }));
    wrap.appendChild(btn);
  }
}

function bindSettings() {
  const speed = $("#speedInput");
  speed.value = String(state.settings.speed);
  $("#speedOut").textContent = Number(state.settings.speed).toFixed(1);
  speed.addEventListener("input", () => {
    state.settings.speed = Number(speed.value);
    $("#speedOut").textContent = state.settings.speed.toFixed(1);
    saveSettings();
  });
  const sr = $("#srMode");
  sr.checked = !!state.settings.srMode;
  sr.addEventListener("change", () => { state.settings.srMode = sr.checked; saveSettings(); });
  const wait = $("#waitSound");
  wait.checked = !!state.settings.waitSound;
  wait.addEventListener("change", () => { state.settings.waitSound = wait.checked; saveSettings(); });
}

async function init() {
  bindSettings();
  $("#captureBtn").addEventListener("click", () => { unlockAudio(); $("#fileInput").click(); });
  $("#fileInput").addEventListener("change", (ev) => {
    const file = ev.target.files && ev.target.files[0];
    ev.target.value = "";
    if (file) analyze({ file, label: "photo" });
  });
  $("#replayBtn").addEventListener("click", replay);
  $("#moreBtn").addEventListener("click", playDetail);
  $("#stopBtn").addEventListener("click", stopSpeaking);
  $("#textBtn").addEventListener("click", analyzeText);

  try {
    const health = await (await fetch("/api/health")).json();
    renderAllergens(health.allergens || []);
    setTiming("서버 엔진", `ocr=${health.ocr}, tts=${(health.tts.available || []).join("/") || "브라우저"}`);
  } catch (e) {
    setStatus("서버에 연결하지 못했어요.", false);
  }
  try {
    renderSamples(await (await fetch("/api/samples")).json());
  } catch (e) { /* 샘플 없이도 동작 */ }
}

init();
