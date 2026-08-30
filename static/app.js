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
  btnChar: document.getElementById("btn-char"),
  btnNewChar: document.getElementById("btn-new-char"),
  modal: document.getElementById("char-modal"),
  charClose: document.getElementById("char-close"),
  charForm: document.getElementById("char-form"),
  fName: document.getElementById("f-name"),
  fRace: document.getElementById("f-race"),
  fClass: document.getElementById("f-class"),
  fBackground: document.getElementById("f-background"),
  fBirthplace: document.getElementById("f-birthplace"),
  fRaceNote: document.getElementById("f-race-note"),
  fAbilities: document.getElementById("f-abilities"),
  btnStandard: document.getElementById("btn-standard"),
  btnRandom: document.getElementById("btn-random"),
  fSkills: document.getElementById("f-skills"),
  fSavs: document.getElementById("f-savs"),
  fSpells: document.getElementById("f-spells"),
  fInventory: document.getElementById("f-inventory"),
  btnAddItem: document.getElementById("btn-add-item"),
  fLevel: document.getElementById("f-level"),
  fXp: document.getElementById("f-xp"),
  fHp: document.getElementById("f-hp"),
  fMaxHp: document.getElementById("f-max-hp"),
  fGp: document.getElementById("f-gp"),
  btnSaveChar: document.getElementById("btn-save-char"),
  btnSaveStart: document.getElementById("btn-save-start"),
  savedList: document.getElementById("saved-char-list"),
};
const AB_FIELDS = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"];
const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8];
let charOptions = null;
let currentCharId = null;

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

// ---------------------------------------------------------------- 角色创建(初始身份与属性)
async function loadCharOptions() {
  if (charOptions) return charOptions;
  charOptions = await api("/api/characters/options");
  fillSelect(els.fRace, charOptions.races, "name");
  fillSelect(els.fClass, charOptions.classes, "name");
  fillSelect(els.fBackground, charOptions.backgrounds, "name");
  fillSelect(els.fBirthplace, charOptions.birthplaces, "key");
  els.fAbilities.innerHTML = (charOptions.abilities || [])
    .map(
      (a) =>
        `<label class="abil-item"><span>${a.name}</span><input type="number" min="1" max="30" value="10" data-key="${a.key}" /></label>`
    )
    .join("");
  els.fSkills.innerHTML = chipList(charOptions.skills, "skill");
  els.fSavs.innerHTML = chipList(charOptions.sav_throws, "sav");
  els.fSpells.innerHTML = chipList(
    (charOptions.spells || []).map((s) => ({ ...s, label: s.name + " (" + s.level + "环)" })),
    "spell"
  );
  els.fRace.addEventListener("change", updateRaceNote);
  return charOptions;
}

function fillSelect(sel, items, key) {
  sel.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "— 请选择 —";
  sel.appendChild(blank);
  for (const it of items || []) {
    const o = document.createElement("option");
    o.value = it[key];
    o.textContent = it[key] + (it.note || it.perk ? " · " + (it.note || it.perk) : "");
    sel.appendChild(o);
  }
}

function chipList(items, cls, checked) {
  return (items || [])
    .map((it) => {
      const v = it.name || it.key || it.value;
      const label = it.label || (it.name || it.key) + (it.ability ? "(" + it.ability + ")" : "");
      const on = checked && checked.includes(v) ? " checked" : "";
      return `<label class="chip ${cls}"><input type="checkbox" data-value="${v}"${on}><span>${label}</span></label>`;
    })
    .join("");
}

function checkedValues(container) {
  return Array.from(container.querySelectorAll("input[type=checkbox]:checked")).map((i) => i.dataset.value);
}

function updateRaceNote() {
  const race = charOptions && charOptions.races.find((r) => r.name === els.fRace.value);
  if (!race) {
    els.fRaceNote.textContent = "";
    return;
  }
  const bonus = Object.entries(race.bonus || {})
    .map(([k, v]) => k + " +" + v)
    .join(", ");
  els.fRaceNote.textContent = "种族特性:" + (race.note || "") + (bonus ? " 属性加成:" + bonus : "");
}

function setAbilitiesValues(arr) {
  const inps = els.fAbilities.querySelectorAll("input[type=number]");
  for (let i = 0; i < inps.length && i < (arr || []).length; i++) inps[i].value = arr[i];
}

function setAbilityFromCharacter(ab) {
  els.fAbilities.querySelectorAll("input[type=number]").forEach((i) => {
    i.value = ab ? (ab[i.dataset.key] ?? 10) : 10;
  });
}

function setChecked(container, values) {
  container.querySelectorAll("input[type=checkbox]").forEach((i) => {
    i.checked = (values || []).includes(i.dataset.value);
  });
}

function addInventoryRow(item) {
  const it = item || {};
  const row = document.createElement("div");
  row.className = "inv-row";
  row.innerHTML =
    `<input type="text" name="name" placeholder="物品名" value="${it.name || ""}" />` +
    `<input type="number" name="qty" placeholder="数量" min="1" value="${it.qty || 1}" />` +
    `<input type="text" name="desc" placeholder="描述(可选)" value="${it.desc || ""}" />` +
    `<input type="number" name="value" placeholder="估价gp" min="0" value="${it.value || 2}" />` +
    '<button type="button" class="mini-btn del">✕</button>';
  row.querySelector(".del").addEventListener("click", () => row.remove());
  els.fInventory.appendChild(row);
}

function resetCharForm() {
  currentCharId = null;
  els.fName.value = "";
  els.fRace.value = "";
  els.fClass.value = "";
  els.fBackground.value = "";
  els.fBirthplace.value = "";
  updateRaceNote();
  setAbilityFromCharacter(null);
  setChecked(els.fSkills, []);
  setChecked(els.fSavs, []);
  setChecked(els.fSpells, []);
  els.fInventory.innerHTML = "";
  addInventoryRow();
  els.fLevel.value = 1;
  els.fXp.value = 0;
  els.fHp.value = "";
  els.fMaxHp.value = "";
  els.fGp.value = "";
}

function fillCharForm(c) {
  els.fName.value = c.name || "";
  els.fRace.value = c.race || "";
  els.fClass.value = c.klass || "";
  els.fBackground.value = c.background || "";
  els.fBirthplace.value = c.birthplace || "";
  updateRaceNote();
  setAbilityFromCharacter(c.abilities);
  setChecked(els.fSkills, c.skills || []);
  setChecked(els.fSavs, c.sav_throws || []);
  setChecked(els.fSpells, (c.spells || []).map((s) => s.name));
  els.fInventory.innerHTML = "";
  (c.inventory && c.inventory.length ? c.inventory : [{}]).forEach((i) => addInventoryRow(i));
  els.fLevel.value = c.level || 1;
  els.fXp.value = c.xp || 0;
  els.fHp.value = c.hp || "";
  els.fMaxHp.value = c.max_hp || "";
  els.fGp.value = c.gp != null ? c.gp : "";
}

async function openCharModal(profileId) {
  await loadCharOptions();
  currentCharId = profileId || null;
  if (currentCharId) {
    const data = await api("/api/characters/" + currentCharId);
    fillCharForm(data.character);
  } else {
    resetCharForm();
  }
  els.modal.classList.remove("hidden");
}

function collectCharForm() {
  const abilities = {};
  els.fAbilities.querySelectorAll("input[type=number]").forEach((i) => {
    abilities[i.dataset.key] = parseInt(i.value, 10) || 10;
  });
  const inventory = [];
  for (const row of els.fInventory.querySelectorAll(".inv-row")) {
    const name = (row.querySelector('[name="name"]') || {}).value || "";
    if (!name.trim()) continue;
    inventory.push({
      name: name.trim(),
      qty: parseInt((row.querySelector('[name="qty"]') || {}).value, 10) || 1,
      desc: (row.querySelector('[name="desc"]') || {}).value || "",
      value: parseInt((row.querySelector('[name="value"]') || {}).value, 10) || 2,
    });
  }
  const payload = {
    name: els.fName.value.trim(),
    race: els.fRace.value,
    klass: els.fClass.value,
    background: els.fBackground.value,
    birthplace: els.fBirthplace.value,
    abilities,
    skills: checkedValues(els.fSkills),
    sav_throws: checkedValues(els.fSavs),
    spells: checkedValues(els.fSpells),
    inventory,
    level: parseInt(els.fLevel.value, 10) || 1,
    xp: parseInt(els.fXp.value, 10) || 0,
    hp: parseInt(els.fHp.value, 10) || 0,
    max_hp: parseInt(els.fMaxHp.value, 10) || 0,
  };
  if (els.fGp.value.trim() !== "") payload.gp = parseInt(els.fGp.value, 10) || 0;
  if (currentCharId) payload.id = currentCharId;
  return payload;
}

async function saveCharacter(startNew) {
  const payload = collectCharForm();
  if (!payload.name) return alert("请填写角色名");
  if (!payload.race) return alert("请选择种族");
  if (!payload.klass) return alert("请选择职业");
  const saved = await api("/api/characters", "POST", payload);
  currentCharId = saved.id;
  await renderSavedCharacters();
  if (!startNew) {
    alert("角色已保存:" + saved.character.name);
    return;
  }
  const s = await api("/api/sessions", "POST", {
    player_name: saved.character.name,
    character_id: saved.id,
  });
  sessionId = s.id;
  refreshSidebar(s);
  renderAll([]);
  const full = await api("/api/sessions/" + sessionId);
  renderAll(full.messages || []);
  await loadBranchTree();
  els.modal.classList.add("hidden");
}

async function applySavedToSession(cid) {
  if (!sessionId) return alert("请先创建或载入一个会话");
  await api("/api/sessions/" + sessionId + "/character", "POST", { character_id: cid });
  const full = await api("/api/sessions/" + sessionId);
  refreshSidebar(full.session);
  renderAll(full.messages || []);
  await loadBranchTree();
}

async function deleteSavedCharacter(cid) {
  if (!confirm("确定删除该角色存档?")) return;
  await api("/api/characters/" + cid, "DELETE");
  renderSavedCharacters();
}

async function renderSavedCharacters() {
  const list = await api("/api/characters");
  els.savedList.innerHTML = "";
  if (!list || !list.length) {
    els.savedList.innerHTML = '<p class="dim">暂无已保存角色</p>';
    return;
  }
  for (const c of list) {
    const row = document.createElement("div");
    row.className = "saved-char";
    const head = document.createElement("div");
    head.className = "saved-char-head";
    const name = document.createElement("span");
    name.className = "saved-name";
    name.textContent = c.name + " · L" + c.level;
    const sub = document.createElement("div");
    sub.className = "saved-sub";
    sub.textContent = (c.race || "—") + " / " + (c.klass || "—") + (c.birthplace ? " · " + c.birthplace : "");
    head.append(name, sub);
    const acts = document.createElement("div");
    acts.className = "saved-acts";
    acts.innerHTML =
      '<button type="button" class="mini-btn act-apply">应用到本会话</button>' +
      '<button type="button" class="mini-btn act-edit">编辑</button>' +
      '<button type="button" class="mini-btn act-del">删除</button>';
    row.append(head, acts);
    row.dataset.id = c.id;
    els.savedList.appendChild(row);
  }
  els.savedList.querySelectorAll(".act-apply").forEach((b) => {
    b.addEventListener("click", () => applySavedToSession(b.closest(".saved-char").dataset.id));
  });
  els.savedList.querySelectorAll(".act-edit").forEach((b) => {
    b.addEventListener("click", () => openCharModal(b.closest(".saved-char").dataset.id));
  });
  els.savedList.querySelectorAll(".act-del").forEach((b) => {
    b.addEventListener("click", () => deleteSavedCharacter(b.closest(".saved-char").dataset.id));
  });
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

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendInput();
});
els.btnNew.addEventListener("click", newGame);
els.btnBranches.addEventListener("click", loadBranchTree);

els.btnChar.addEventListener("click", () => openCharModal(null));
els.btnNewChar.addEventListener("click", () => openCharModal(null));
els.charClose.addEventListener("click", () => els.modal.classList.add("hidden"));
els.modal.addEventListener("click", (e) => {
  if (e.target === els.modal) els.modal.classList.add("hidden");
});
els.charForm.addEventListener("submit", (e) => e.preventDefault());
els.btnStandard.addEventListener("click", () => {
  setAbilitiesValues([...STANDARD_ARRAY].sort(() => Math.random() - 0.5));
});
els.btnRandom.addEventListener("click", () => {
  setAbilitiesValues(Array.from({ length: 6 }, () => 3 + Math.floor(Math.random() * 16)));
});
els.btnAddItem.addEventListener("click", () => addInventoryRow());
els.btnSaveChar.addEventListener("click", () => saveCharacter(false));
els.btnSaveStart.addEventListener("click", () => saveCharacter(true));

async function init() {
  try {
    const h = await api("/api/health");
    els.llm.textContent = h.llm_provider + " DM";
    els.img.textContent = h.image_provider + " 生图";
  } catch (e) {
    els.llm.textContent = "引擎离线";
    els.img.textContent = "";
  }
  renderSavedCharacters();
  loadCharOptions().catch(() => {});
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

init();