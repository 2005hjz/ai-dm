// AI-DM 前端逻辑:会话管理 + 消息渲染 + SSE 流式剧情 + 斜杠指令
"use strict";

const els = {
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  form: document.getElementById("send-form"),
  msgs: document.getElementById("messages"),
  llm: document.getElementById("llm-badge"),
  img: document.getElementById("img-badge"),
  sceneImg: document.getElementById("scene-img"),
  sceneName: document.getElementById("scene-name"),
  playerName: document.getElementById("player-name"),
  playerNameDisplay: document.getElementById("player-name-display"),
  hpBar: document.getElementById("hp-bar"),
  btnNew: document.getElementById("btn-new"),
  statRolls: document.getElementById("stat-rolls"),
  statChecks: document.getElementById("stat-checks"),
  statPass: document.getElementById("stat-pass"),
  statFail: document.getElementById("stat-fail"),
  npcList: document.getElementById("npc-list"),
  eventLog: document.getElementById("event-log"),
  meta: document.getElementById("session-meta"),
  charLine: document.getElementById("char-line"),
  xpLine: document.getElementById("xp-line"),
  gpLine: document.getElementById("gp-line"),
  abilList: document.getElementById("abil-list"),
  invList: document.getElementById("inv-list"),
  spellLine: document.getElementById("spell-line"),
  branchTree: document.getElementById("branch-tree"),
  btnBranches: document.getElementById("btn-branches"),
};

const AB_CN = { strength: "力量", dexterity: "敏捷", constitution: "体质", intelligence: "智力", wisdom: "感知", charisma: "魅力" };

let sessionId = null;
let streaming = false;
let branchData = null;
let currentScene = null;

// ---------------------------------------------------------------- 基础设施
async function api(path, method = "GET", body = null) {
  const opt = { method, headers: {} };
  if (body) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const res = await fetch(path, opt);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || res.statusText);
  }
  return res.json();
}

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

// ---------------------------------------------------------------- 渲染
function refreshSidebar(s) {
  const st = s.state;
  currentScene = s.scene && s.scene.id ? s.scene.id : (st && st.scene_id) || null;
  els.sceneImg.src = s.scene.image || "";
  els.sceneName.textContent = "· " + (s.scene.name || "");
  els.playerNameDisplay.textContent = st.player + " · 回合 " + st.turn;
  els.meta.textContent =
    "场景 " + s.scene.id + " · 会话 " + s.id + " · " + (new Date().toLocaleTimeString());
  els.statRolls.textContent = s.stats.rolls;
  els.statChecks.textContent = s.stats.checks;
  els.statPass.textContent = s.stats.checks_passed;
  els.statFail.textContent = s.stats.checks_failed;
  // HP 条
  els.hpBar.innerHTML = "";
  for (let i = 0; i < (st.max_hp || 0); i++) {
    const c = document.createElement("i");
    if (i < (st.hp || 0)) c.className = "on";
    els.hpBar.appendChild(c);
  }
  // D&D 角色卡
  els.charLine.textContent = (st.race || "未建卡") + " · " + (st.klass || "—") + " · " + (st.background || "—") + " · " + (st.birthplace || "—");
  els.xpLine.textContent = "经验 " + (st.xp || 0) + " XP · 等级 L" + (st.level || 1) + " · 熟练加值 +" + (st.prof_bonus || 2);
  els.gpLine.textContent = "金币 " + (st.gp || 0) + " gp";
  els.abilList.innerHTML = st.abilities
    ? Object.entries(st.abilities)
        .map(([k, v]) => `<span class="abil">${AB_CN[k] || k} ${v}</span>`)
        .join(" ")
    : "";
  els.invList.innerHTML = st.inventory && st.inventory.length
    ? st.inventory
        .map((i) => `<div class="inv-item">${i.name}×${i.qty || 1}${i.effect ? " [" + i.effect + "]" : ""}</div>`)
        .join("")
    : '<div class="dim">背包空空（用 /sell 编号 出售物品）</div>';
  const slots = Object.entries(st.spell_slots || {})
    .map(([k, v]) => k + "环×" + v)
    .join(" ");
  const prepared = (st.spells || []).filter((s) => s.prepared).map((s) => s.name).join("、") || "无";
  els.spellLine.textContent = "法术位 " + (slots || "无") + " · 已准备 " + prepared;
  // NPC
  els.npcList.innerHTML = "";
  for (const n of st.npcs || []) {
    const row = document.createElement("div");
    row.className = "npc";
    const img = document.createElement("img");
    img.src = n.portrait || "";
    const box = document.createElement("div");
    const nm = document.createElement("div");
    nm.className = "n-name";
    nm.textContent = n.name;
    const t = document.createElement("div");
    t.className = "n-title";
    t.textContent = n.title || "";
    box.append(nm, t);
    row.append(img, box);
    els.npcList.appendChild(row);
  }
  // 事件日志
  els.eventLog.innerHTML = "";
  for (const ev of st.events || []) {
    const li = document.createElement("li");
    li.textContent = ev;
    els.eventLog.appendChild(li);
  }
}

function bubble(kind, content) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + kind;
  const b = document.createElement("div");
  b.className = "bubble";
  if (kind === "roll") {
    b.innerHTML =
      '<span class="roll-ico">⚂</span> ' +
      escapeHtml(content) +
      addDegree(content);
  } else {
    b.textContent = content;
  }
  wrap.appendChild(b);
  return wrap;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function addDegree(content) {
  // 从 /roll 返回的 meta 里更好;这里兜底不显示
  return "";
}

function addCheck(m) {
  const wrap = document.createElement("div");
  wrap.className = "msg check";
  const banner = document.createElement("div");
  banner.className = "check-banner";
  const meta = m.meta || {};
  const sev =
    meta.degree === "大成功"
      ? "severity-good"
      : meta.degree === "大失败"
        ? "severity-bad"
        : meta.success
          ? "severity-mid"
          : "severity-bad";
  const row = document.createElement("div");
  row.className = "check-row";
  const title = document.createElement("span");
  title.className = "check-title";
  title.textContent = m.content || "";
  const dg = document.createElement("span");
  dg.className = "degree " + sev;
  dg.textContent = meta.degree || "—";
  row.append(title, dg);
  banner.appendChild(row);
  if (meta.dc != null) {
    const metaRow = document.createElement("div");
    metaRow.className = "check-meta";
    metaRow.innerHTML =
      "<span>DC " + meta.dc + "</span><span>掷出 " + meta.total + "</span><span>" + (meta.success ? "成功" : "失败") + "</span>";
    banner.appendChild(metaRow);
  }
  wrap.appendChild(banner);
  return wrap;
}

function addCard(m) {
  const wrap = document.createElement("div");
  wrap.className = "msg system";
  const b = document.createElement("div");
  b.className = "bubble";
  b.textContent = m.content || "";
  wrap.appendChild(b);
  return wrap;
}

function renderMessage(m) {
  if (!m || !m.content) return null;
  if (m.kind === "player") {
    const el = bubble("player", m.content);
    el.querySelector(".bubble").textContent = m.content;
    return el;
  }
  if (m.kind === "check") return addCheck(m);
  if (m.kind === "card") return addCard(m);
  if (m.kind === "roll") {
    const el = bubble("roll", m.content);
    const deg = m.meta && m.meta.degree;
    if (deg) {
      const sp = document.createElement("span");
      sp.className = "degree " + (deg === "大成功" ? "severity-good" : deg === "大失败" || !m.meta.success ? "severity-bad" : deg === "普通" ? "severity-mid" : "severity-mid");
      sp.textContent = deg;
      el.querySelector(".bubble").appendChild(sp);
    }
    return el;
  }
  // story / system
  const el = bubble(m.kind === "system" ? "system" : "story", m.content);
  if (m.role === "dm") {
    const tag = document.createElement("div");
    tag.className = "dm-tag";
    tag.textContent = "DM";
    el.prepend(tag);
  }
  return el;
}

function renderAll(messages) {
  els.msgs.innerHTML = "";
  for (const m of messages) {
    const el = renderMessage(m);
    if (el) els.msgs.appendChild(el);
  }
  scrollToBottom();
}

function renderNew(messages) {
  for (const m of messages) {
    const el = renderMessage(m);
    if (el) els.msgs.appendChild(el);
  }
  scrollToBottom();
}

function scrollToBottom() {
  els.msgs.scrollTop = els.msgs.scrollHeight;
}

// ---------------------------------------------------------------- 剧情分支树
function renderBranchTree(data, currentId) {
  if (!data || !data.nodes) return;
  const box = els.branchTree;
  box.innerHTML = "";
  const byId = {};
  for (const n of data.nodes) byId[n.id] = n;

  const container = document.createElement("div");
  container.style.display = "flex";
  container.style.flexDirection = "column";
  container.style.gap = "4px";

  const start = data.nodes.find((n) => n.id === data.order[0]) || data.nodes[0];
  container.appendChild(branchNodeEl(start, currentId));

  // 大剧情分支边走:每个节点 → 声明过的下一分支
  const children = {};
  for (const e of data.edges) {
    if (e.kind !== "branch") continue;
    (children[e.from] = children[e.from] || []).push(e);
  }
  for (const n of data.nodes) {
    for (const e of children[n.id] || []) {
      const edge = document.createElement("div");
      edge.className = "branch-edge";
      edge.textContent = "── " + (e.label || "推进") + " → " + (byId[e.to] ? byId[e.to].name : e.to);
      container.appendChild(edge);
      if (byId[e.to]) container.appendChild(branchNodeEl(byId[e.to], currentId));
    }
  }
  box.appendChild(container);
}

function branchNodeEl(n, currentId) {
  const el = document.createElement("div");
  el.className = "branch-node";
  if (n.id === currentId) el.classList.add("current");
  if (n.terminal) el.classList.add("terminal");
  const name = document.createElement("span");
  const sk = document.createElement("span");
  name.textContent = n.name;
  sk.className = "b-skill";
  sk.textContent = (n.start ? "起始" : "") + (n.terminal ? " · 终局" : "");
  el.append(name, sk);
  return el;
}

async function loadBranchTree() {
  try {
    const data = await api("/api/scenario/branches");
    branchData = data;
    renderBranchTree(data, currentScene);
  } catch (e) {
    els.branchTree.innerHTML = '<p class="dim">分支树不可用</p>';
  }
}

function makeStreamingBubble() {
  const wrap = document.createElement("div");
  wrap.className = "msg story";
  const tag = document.createElement("div");
  tag.className = "dm-tag";
  tag.textContent = "DM";
  const b = document.createElement("div");
  b.className = "bubble";
  const cur = document.createElement("span");
  cur.className = "cursor";
  b.appendChild(cur);
  wrap.append(tag, b);
  els.msgs.appendChild(wrap);
  scrollToBottom();
  return { wrap, b, cur };
}

// ---------------------------------------------------------------- SSE 解析
async function sendFreeAction(text) {
  const sb = makeStreamingBubble();
  const res = await fetch("/api/sessions/" + sessionId + "/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok || !res.body) {
    sb.b.textContent = "连接失败: " + res.status + " " + (await res.text());
    if (sb.cur) sb.cur.remove();
    return;
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      handleBlock(block, sb);
    }
  }
  sb.cur.remove();
}

function handleBlock(block, sb) {
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim() + "\n";
  }
  if (!data.trim()) return;
  let payload;
  try {
    payload = JSON.parse(data);
  } catch (e) {
    return;
  }
  if (event === "token") {
    const t = document.createTextNode(payload.token || "");
    sb.b.insertBefore(t, sb.cur);
    scrollToBottom();
  } else if (event === "done") {
    renderNew(payload.new_messages || []);
    refreshSidebar(payload.session);
    if (branchData) renderBranchTree(branchData, currentScene);
  }
}

// ---------------------------------------------------------------- 交互
async function sendInput() {
  const text = els.input.value.trim();
  if (!text || streaming || !sessionId) return;
  streaming = true;
  els.send.disabled = true;
  els.input.disabled = true;

  const playerEl = renderMessage({ kind: "player", role: "player", content: text });
  if (playerEl) {
    els.msgs.appendChild(playerEl);
    els.input.value = "";
    scrollToBottom();
  }

  try {
    if (text.startsWith("/")) {
      const r = await api("/api/sessions/" + sessionId + "/command", "POST", { text });
      renderNew(r.new_messages || []);
      refreshSidebar(r.session);
    } else {
      await sendFreeAction(text);
    }
  } catch (err) {
    renderNew([
      { kind: "system", role: "system", content: "引擎出错: " + err.message },
    ]);
  } finally {
    streaming = false;
    els.send.disabled = false;
    els.input.disabled = false;
    els.input.focus();
  }
}

async function newGame() {
  const name = els.playerName.value.trim() || "无名调查员";
  const s = await api("/api/sessions", "POST", { player_name: name });
  sessionId = s.id;
  refreshSidebar(s);
  renderAll([]);
  // 拉完整开场
  const full = await api("/api/sessions/" + sessionId);
  renderAll(full.messages || []);
  await loadBranchTree();
}

async function init() {
  try {
    const h = await api("/api/health");
    els.llm.textContent = h.llm_provider + " DM";
    els.img.textContent = h.image_provider + " 生图";
  } catch (e) {
    els.llm.textContent = "引擎离线";
    els.img.textContent = "";
  }
  const sessions = await api("/api/sessions");
  if (sessions && sessions.length) {
    const s = sessions[0];
    sessionId = s.id;
    const full = await api("/api/sessions/" + sessionId);
    refreshSidebar(full.session);
    renderAll(full.messages || []);
  } else {
    await newGame();
  }
  await loadBranchTree();
}

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendInput();
});
els.btnNew.addEventListener("click", newGame);
els.btnBranches.addEventListener("click", loadBranchTree);

init();