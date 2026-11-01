/* 감 테스트 — 주제 고르기 · 진행 · 채점 · 결과 · 공유
 *
 * 계산은 전부 여기서 끝난다. 서버는 촌평 한 줄을 받을 때만 부른다.
 * 원본 데이터는 이 앱에 들어오지 않는다 — topics/*.json 에 정답과 근거만 있다.
 */

const $ = (id) => document.getElementById(id);
const views = { home: $("view-home"), quiz: $("view-quiz"), result: $("view-result") };

let INDEX = null;     // topics.json
let PACK = null;      // 지금 푸는 주제
let idx = 0;
let answers = [];

const DONE_KEY = "gam-test-done";

/* 푼 주제를 기억한다. 이 브라우저 안에만 남고 서버로 가지 않는다.
   시크릿 창이나 저장소 차단 환경에서는 읽기·쓰기가 막히므로 감싼다. */
function doneMap() {
  try { return JSON.parse(localStorage.getItem(DONE_KEY) || "{}"); }
  catch { return {}; }
}
function markDone(id, score) {
  try {
    const m = doneMap();
    m[id] = Math.max(score, m[id] ?? 0);
    localStorage.setItem(DONE_KEY, JSON.stringify(m));
  } catch { /* 저장이 막혀 있어도 앱은 그대로 돈다 */ }
}

/* ── 채점 ────────────────────────────────────────────
 * 택1     맞으면 100, 틀리면 0
 * 슬라이더 오차율 × 200 만큼 깎는다 (10% 빗나가면 80점)
 */
function scoreOne(q, mine) {
  if (q.type === "choice") return mine === q.answer ? 100 : 0;
  const err = Math.abs(mine - q.answer) / Math.abs(q.answer);
  return Math.max(0, Math.round(100 - err * 200));
}
function errPct(q, mine) {
  if (q.type === "choice") return mine === q.answer ? 0 : 100;
  return Math.abs(mine - q.answer) / Math.abs(q.answer) * 100;
}
function gradeOf(s) {
  return INDEX.grades.find((g) => s >= g.min) || INDEX.grades.at(-1);
}
function reactionOf(q, mine, pct) {
  if (q.type === "choice") {
    return mine === q.answer ? INDEX.reactions_choice.hit
                             : INDEX.reactions_choice.miss;
  }
  return (INDEX.reactions.find((r) => pct <= r.max) || { text: "" }).text;
}
/* 받침이 있으면 을, 없으면 를 */
function josa(w) {
  const c = String(w).trim().slice(-1).charCodeAt(0);
  if (c < 0xac00 || c > 0xd7a3) return "을";
  return (c - 0xac00) % 28 ? "을" : "를";
}
/* 공유 링크로 들어온 글자는 HTML 로 해석되지 않게 바꾼다 */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
/* Gemini 에게는 숫자가 아니라 방향만 보낸다 */
function directionOf(q, mine) {
  if (q.type === "choice") return mine === q.answer ? "맞힘" : "틀림";
  const d = (mine - q.answer) / Math.abs(q.answer);
  if (Math.abs(d) <= 0.08) return "비슷";
  return d > 0 ? "높게" : "낮게";
}

function show(name) {
  Object.entries(views).forEach(([k, el]) => (el.hidden = k !== name));
  window.scrollTo({ top: 0 });
}

/* ── 시작 ────────────────────────────────────────── */
async function boot() {
  INDEX = await (await fetch("topics.json", { cache: "no-store" })).json();
  // 제목은 첫 단어는 빨강, 나머지는 파랑 두 줄로 나눈다 (태극 두 색)
  const [head, ...rest] = INDEX.title.split(" ");
  $("title").innerHTML = "";
  const red = document.createElement("span");
  red.className = "t-red"; red.textContent = head;
  $("title").appendChild(red);
  if (rest.length) {
    const blue = document.createElement("span");
    blue.className = "t-blue"; blue.textContent = rest.join(" ");
    $("title").append(document.createElement("br"), blue);
  }
  $("subtitle").textContent = INDEX.subtitle;

  const p = new URLSearchParams(location.search);
  if (p.has("s")) {
    const g = p.get("g") || "";
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    $("shared-banner").innerHTML =
      `친구가 ${t ? `<b>${t.emoji} ${t.title}</b> 에서 ` : ""}` +
      `<b>${Number(p.get("s"))}점 · ${esc(g)}</b>${josa(g || "점")} 받았습니다. 당신은요?`;
    $("shared-banner").hidden = false;
  }

  renderGrid();
  $("btn-next").onclick = next;
  $("btn-back").onclick = () => show("home");
  $("btn-more").onclick = () => { renderGrid(); show("home"); };
  $("btn-share").onclick = share;
  if (p.has("t")) {
    const t = INDEX.topics.find((x) => x.id === p.get("t"));
    if (t && !p.has("s")) start(t.id);
  }
}

function renderGrid() {
  const done = doneMap();
  const n = INDEX.topics.filter((t) => t.id in done).length;
  $("progress-note").textContent =
    n ? `${INDEX.topics.length}개 중 ${n}개 풀었습니다` : "";
  $("topic-grid").innerHTML = "";
  INDEX.topics.forEach((t) => {
    const b = document.createElement("button");
    b.className = "tcard" + (t.id in done ? " done" : "");
    b.innerHTML =
      (t.art
        ? `<span class="tart" aria-hidden="true">${t.art.map((src) => `<img src="${src}" alt="">`).join("")}</span>`
        : `<span class="temoji${t.fx ? ` fx-${t.fx}` : ""}">${t.emoji}</span>`) +
      `<span class="ttitle">${t.title}</span>` +
      `<span class="tblurb">${t.blurb}</span>` +
      (t.id in done ? `<span class="tscore">${done[t.id]}점</span>` : "");
    b.onclick = () => start(t.id);
    $("topic-grid").appendChild(b);
  });
}

async function start(id) {
  // 주제를 누른 뒤에 받는 파일은 강력 새로고침으로도 새로 받지 않는다. 문항을 다시
  // 계산해도 옛 파일이 나오지 않게, 기억해 둔 사본을 쓰지 말고 늘 서버에서 받는다
  PACK = await (await fetch(`topics/${id}.json`, { cache: "no-store" })).json();
  idx = 0; answers = [];
  $("topic-name").textContent = `${PACK.emoji} ${PACK.title}`;
  renderQ();
  show("quiz");
}

/* ── 문항 ────────────────────────────────────────── */
function renderQ() {
  const q = PACK.questions[idx];
  $("progress-bar").style.width = `${(idx / PACK.questions.length) * 100}%`;
  $("q-count").textContent = `${idx + 1} / ${PACK.questions.length}`;
  $("q-text").textContent = q.text;
  $("btn-next").textContent =
    idx === PACK.questions.length - 1 ? "결과 보기" : "다음";

  const isChoice = q.type === "choice";
  $("q-choice").hidden = !isChoice;
  $("q-slider").hidden = isChoice;

  if (isChoice) {
    answers[idx] = null;
    $("btn-next").disabled = true;
    $("q-choice").innerHTML = "";
    q.options.forEach((opt) => {
      const b = document.createElement("button");
      b.className = "choice";
      b.type = "button";
      b.textContent = opt;
      b.setAttribute("aria-pressed", "false");
      b.onclick = () => {
        answers[idx] = opt;
        [...$("q-choice").children].forEach((c) =>
          c.setAttribute("aria-pressed", String(c === b)));
        $("btn-next").disabled = false;
      };
      $("q-choice").appendChild(b);
    });
  } else {
    const s = $("slider");
    s.min = q.min; s.max = q.max; s.step = q.step;
    // 기본값을 한가운데에서 한 칸 비켜 둔다 — 가운데면 생각 없이 맞는다
    s.value = Math.round(((q.min + q.max) / 2 + q.step) / q.step) * q.step;
    $("slider-min").textContent = `${q.min}${q.unit}`;
    $("slider-max").textContent = `${q.max}${q.unit}`;
    const paint = () => {
      answers[idx] = Number(s.value);
      $("slider-out").textContent = `${s.value}${q.unit}`;
    };
    s.oninput = paint;
    paint();
    $("btn-next").disabled = false;
  }
}

function next() {
  if (idx < PACK.questions.length - 1) { idx++; renderQ(); return; }
  renderResult();
  show("result");
}

/* ── 결과 ────────────────────────────────────────── */
function pos(q, v) {
  return Math.max(0, Math.min(100, ((v - q.min) / (q.max - q.min)) * 100));
}

function renderResult() {
  const total = Math.round(
    PACK.questions.map((q, i) => scoreOne(q, answers[i]))
      .reduce((a, b) => a + b, 0) / PACK.questions.length);
  const g = gradeOf(total);
  markDone(PACK.id, total);

  $("result-topic").textContent = `${PACK.emoji} ${PACK.title}`;
  $("score").innerHTML = `${total}<span>점</span>`;
  $("grade").textContent = g.name;
  $("grade-emoji").textContent = g.emoji || "";

  const box = $("cards");
  box.innerHTML = "";
  PACK.questions.forEach((q, i) => {
    const mine = answers[i];
    const pct = errPct(q, mine);
    const hit = q.type === "choice" ? mine === q.answer : pct <= 5;
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <h3>${q.text}</h3>
      <p class="react ${hit ? "hit" : pct > 40 ? "miss" : ""}">${reactionOf(q, mine, pct)}</p>
      ${q.type === "choice" ? choiceBody(q, mine) : sliderBody(q, mine)}
      <p class="why">💡 ${q.why}</p>
      <details><summary>근거 보기</summary><p class="basis">${q.basis}</p></details>`;
    box.appendChild(el);
  });

  $("caveat").hidden = !PACK.caveat;
  if (PACK.caveat) $("caveat").innerHTML = `<b>이 데이터의 한계</b><br>${PACK.caveat}`;
  $("source").innerHTML =
    `출처 <a href="${PACK.source_url}" target="_blank" rel="noopener">${PACK.source}</a>`;

  requestAnimationFrame(() => setTimeout(animate, 60));
  askComment(total, g.name);
}

function choiceBody(q, mine) {
  const label = (o) => {
    const cls = o === q.answer && o === mine ? "both"
      : o === q.answer ? "real" : o === mine ? "mine" : "";
    const tag = o === q.answer && o === mine ? " 실제 · 내 답"
      : o === q.answer ? " 실제" : o === mine ? " 내 답" : "";
    return `<span class="pill ${cls}">${o}${tag}</span>`;
  };
  return `<div class="pills">${q.options.map(label).join("")}</div>`;
}

function sliderBody(q, mine) {
  const rows = [["내 답", mine, "mine"]];
  rows.push(["실제", q.answer, "real"]);
  const max = Math.max(...rows.map((r) => Math.abs(Number(r[1])))) || 1;
  const bars = rows.map(([k, v, cls]) => `
      <div class="row">
        <span class="k">${k}</span>
        <span class="bar ${cls}"><i data-w="${Math.abs(Number(v)) / max * 100}"></i></span>
        <span class="v">${v}${q.unit}</span>
      </div>`).join("");
  return `
    <div class="track">
      <span class="line"></span>
      <span class="ghost" style="left:${pos(q, mine)}%"></span>
      <span class="live" data-left="${pos(q, q.answer)}" style="left:${pos(q, mine)}%"></span>
    </div>
    <div class="rows">${bars}</div>`;
}

function animate() {
  document.querySelectorAll(".bar > i").forEach((b) => (b.style.width = b.dataset.w + "%"));
  document.querySelectorAll(".track .live").forEach((m) => (m.style.left = m.dataset.left + "%"));
}

/* ── 촌평 — 없어도 앱은 그대로 돈다 ──────────────── */
async function askComment(total, grade) {
  const el = $("ai-comment");
  el.hidden = false;
  el.innerHTML = `<span class="tag">촌평을 받아오는 중…</span>`;
  const directions = PACK.questions.map((q, i) => directionOf(q, answers[i]));
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 3000);
    const r = await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score: total, grade, directions, topic: PACK.title }),
      signal: ctl.signal,
    });
    clearTimeout(timer);
    const j = await r.json();
    if (!j || !j.comment) { el.hidden = true; return; }
    el.innerHTML = `<span class="tag">한 줄 촌평</span><br>${j.comment}` +
      (j.nickname ? `<br><span class="nick">${j.nickname}</span>` : "");
  } catch {
    el.hidden = true;
  }
}

/* ── 공유 ────────────────────────────────────────── */
async function share() {
  const total = $("score").textContent.replace(/[^0-9]/g, "");
  const grade = $("grade").textContent;
  const url = `${location.origin}${location.pathname}` +
    `?t=${encodeURIComponent(PACK.id)}&s=${total}&g=${encodeURIComponent(grade)}`;
  const text = `${INDEX.title} · ${PACK.title} ${total}점 · ${grade}`;
  try {
    if (navigator.share) { await navigator.share({ title: INDEX.title, text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`);
    $("btn-share").textContent = "링크를 복사했습니다";
    setTimeout(() => ($("btn-share").textContent = "친구에게 보내기"), 1800);
  } catch { /* 사용자가 취소한 경우 */ }
}

boot();
