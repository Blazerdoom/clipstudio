"use strict";

const $ = (sel) => document.querySelector(sel);
const api = {
  async get(url) { const r = await fetch(url); if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json(); },
  async post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  },
};

const state = { selected: null, poll: null };

/* ---------- bootstrap ---------- */
async function boot() {
  await Promise.all([loadEnv(), loadOptions(), loadYt()]);
  await loadProjects();
  $("#create-form").addEventListener("submit", onCreate);
  $("#refresh").addEventListener("click", loadProjects);
  $("#edit-close").addEventListener("click", closeEditor);
  $("#edit-cancel").addEventListener("click", closeEditor);
  $("#edit-apply").addEventListener("click", applyEdit);
  $("#edit-addline").addEventListener("click", addLine);
  $("#edit-modal").addEventListener("click", (e) => { if (e.target.id === "edit-modal") closeEditor(); });
}

async function loadEnv() {
  try {
    const env = await api.get("/api/env");
    const chips = [];
    chips.push(env.ffmpeg
      ? `<span class="chip ok">ffmpeg ready</span>`
      : `<span class="chip warn">ffmpeg missing</span>`);
    chips.push(env.gpu_available
      ? `<span class="chip ok">GPU: ${env.cuda_devices} CUDA</span>`
      : `<span class="chip warn">CPU only</span>`);
    $("#env").innerHTML = chips.join("");
  } catch { $("#env").innerHTML = `<span class="chip warn">engine offline</span>`; }
}

function fillSelect(id, values, current) {
  const el = $(id);
  el.innerHTML = values.map((v) => `<option value="${v}"${v === current ? " selected" : ""}>${v}</option>`).join("");
}

function fillSelectKV(id, items, current) {
  const el = $(id);
  el.innerHTML = items
    .map((it) => `<option value="${it.name}"${it.name === current ? " selected" : ""}>${escapeHtml(it.label)}</option>`)
    .join("");
}

async function loadOptions() {
  const [env, settings, tracks] = await Promise.all([
    api.get("/api/env"), api.get("/api/settings"), api.get("/api/music").catch(() => []),
  ]);
  state.captionPresets = env.caption_presets || [];
  state.dubVoices = (env.dub_voices || []).map((v) => ({ name: v.id, label: v.label }));
  fillSelect("#opt-device", env.devices, settings.device);
  fillSelect("#opt-model", env.models, settings.model);
  fillSelect("#opt-aspect", env.aspects, settings.aspect);
  fillSelect("#opt-reframe", env.reframes, settings.reframe);
  fillSelectKV("#opt-caption", state.captionPresets, settings.caption_preset);
  const musicOpts = [{ name: "", label: "None" }, ...tracks];
  fillSelectKV("#opt-music", musicOpts, settings.music || "");
  $("#opt-max").value = settings.max_clips;
  $("#opt-minutes").value = settings.max_minutes || 30;
  $("#opt-zoom").checked = !!settings.zoom;
  $("#opt-color").checked = !!settings.color;
}

/* ---------- create ---------- */
async function onCreate(e) {
  e.preventDefault();
  const source = $("#source").value.trim();
  if (!source) return;
  const btn = $("#generate-btn");
  btn.disabled = true;
  try {
    const project = await api.post("/api/projects", {
      source,
      device: $("#opt-device").value,
      model: $("#opt-model").value,
      max_clips: Number($("#opt-max").value),
      max_minutes: Number($("#opt-minutes").value),
      aspect: $("#opt-aspect").value,
      reframe: $("#opt-reframe").value,
      caption_preset: $("#opt-caption").value,
      zoom: $("#opt-zoom").checked,
      color: $("#opt-color").checked,
      music: $("#opt-music").value,
    });
    $("#source").value = "";
    await loadProjects();
    selectProject(project.id);
  } catch (err) {
    alert("Could not start: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

/* ---------- projects rail ---------- */
async function loadProjects() {
  const projects = await api.get("/api/projects");
  const list = $("#project-list");
  if (!projects.length) { list.innerHTML = `<li class="pi-meta">No projects yet.</li>`; return; }
  list.innerHTML = projects.map(projectItem).join("");
  list.querySelectorAll("[data-id]").forEach((el) =>
    el.addEventListener("click", () => selectProject(Number(el.dataset.id))));
}

function projectItem(p) {
  const active = p.id === state.selected ? " active" : "";
  return `<li class="project-item${active}" data-id="${p.id}">
    <div class="pi-name">${escapeHtml(p.name)}</div>
    <div class="pi-meta">
      <span><span class="status-dot status-${p.status}"></span>${p.status}</span>
      <span>${Math.round((p.progress || 0) * 100)}%</span>
    </div>
  </li>`;
}

/* ---------- detail ---------- */
function selectProject(id) {
  state.selected = id;
  document.querySelectorAll(".project-item").forEach((el) =>
    el.classList.toggle("active", Number(el.dataset.id) === id));
  refreshDetail();
}

async function refreshDetail() {
  if (state.selected == null) return;
  const p = await api.get(`/api/projects/${state.selected}`);
  renderDetail(p);
  if (state.poll) clearTimeout(state.poll);
  const busyProject = p.running || (p.status !== "done" && p.status !== "error");
  const clipRendering = (p.clips || []).some((c) => c.status === "rendering");
  if (busyProject || clipRendering) {
    state.poll = setTimeout(refreshDetail, 1500);
  } else {
    loadProjects();
  }
}

function renderDetail(p) {
  const pct = Math.round((p.progress || 0) * 100);
  const done = p.status === "done";
  const parts = [`<div class="detail-head">
      <div>
        <h2>${escapeHtml(p.name)}</h2>
        <div class="sub">${escapeHtml(p.source)}${p.duration ? " · " + fmtDur(p.duration) : ""}</div>
      </div>
      <a class="btn-dl-all${p.clips && p.clips.length ? "" : " disabled"}"
         href="/api/projects/${p.id}/download_all">⬇ Download all</a>
    </div>`];

  if (p.status === "error") {
    parts.push(`<div class="error-box">⚠ ${escapeHtml(p.error || "Something went wrong.")}</div>`);
  } else if (!done) {
    parts.push(`<div class="progress-wrap">
      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
      <div class="progress-label">${escapeHtml(p.stage)} — ${pct}%</div>
    </div>`);
  }

  const clips = p.clips || [];
  state.clipsById = {};
  state.projectPreset = (p.settings || {}).caption_preset;
  clips.forEach((c) => { state.clipsById[c.id] = c; });
  if (clips.length) {
    parts.push(`<div class="clips-toolbar"><span class="count">${clips.length} clip${clips.length > 1 ? "s" : ""}, best first</span></div>`);
    parts.push(`<div class="clip-grid">${clips.map(clipCard).join("")}</div>`);
  } else if (done) {
    parts.push(`<div class="empty-state"><p class="empty-title">No clips passed the bar</p>
      <p class="empty-sub">Try a longer or more talkative video.</p></div>`);
  }
  $("#detail").innerHTML = parts.join("");
  wireClipPlay();
  wireEditButtons();
}

function wireEditButtons() {
  document.querySelectorAll("[data-edit]").forEach((el) =>
    el.addEventListener("click", () => openEditor(Number(el.dataset.edit))));
  document.querySelectorAll("[data-yt]").forEach((el) =>
    el.addEventListener("click", () => uploadToYouTube(Number(el.dataset.yt), el)));
}

async function loadYt() {
  try { state.yt = await api.get("/api/youtube/status"); }
  catch { state.yt = { ready: false, authed: false }; }
}

async function uploadToYouTube(clipId, btn) {
  if (!confirm("Upload this clip to YouTube as a PRIVATE video?")) return;
  btn.disabled = true; btn.textContent = "Uploading…";
  try {
    await api.post("/api/youtube/upload", { clip_id: clipId, privacy: "private" });
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 2500));
      const s = await api.get(`/api/youtube/upload_status?clip_id=${clipId}`);
      if (s.state === "done") { btn.textContent = "On YouTube ✓"; window.open(s.url, "_blank"); return; }
      if (s.state === "error") { alert("Upload failed: " + s.error); break; }
    }
  } catch (err) {
    alert("Upload error: " + err.message);
  }
  btn.disabled = false; btn.textContent = "YouTube";
}

function clipCard(c) {
  const cls = c.score >= 70 ? "good" : c.score >= 50 ? "mid" : "low";
  const rendering = c.status === "rendering";
  let media;
  if (rendering) {
    media = `<div class="play-hint rerender">↻ Re-rendering…</div>`;
  } else if (c.url) {
    media = `<img src="${c.thumb_url || ""}" alt="" loading="lazy" data-video="${c.url}" />
             <div class="play-hint" data-video="${c.url}">▶</div>`;
  } else {
    media = `<div class="play-hint">…</div>`;
  }
  const tags = (c.tags || []).map((t) => `<span>#${escapeHtml(t)}</span>`).join("");
  const canEdit = c.url && !rendering;
  const ytOn = state.yt && state.yt.ready && state.yt.authed && c.url && !rendering;
  return `<article class="clip-card">
    <div class="clip-media"><span class="vbadge ${cls}">${Math.round(c.score)}</span>${media}</div>
    <div class="clip-body">
      <div class="clip-title">${escapeHtml(c.title)}</div>
      <div class="clip-reason">${escapeHtml(c.reason)}</div>
      <div class="clip-tags">${tags}</div>
      <div class="clip-foot">
        <span class="clip-time">${fmtDur(c.start)} → ${fmtDur(c.end)}</span>
        <span class="clip-actions">
          ${canEdit ? `<button class="btn-dl" data-edit="${c.id}">Edit</button>` : ""}
          ${ytOn ? `<button class="btn-dl" data-yt="${c.id}">YouTube</button>` : ""}
          ${c.url && !rendering ? `<a class="btn-dl" href="/api/clips/${c.id}/download">Download</a>` : ""}
        </span>
      </div>
    </div>
  </article>`;
}

function wireClipPlay() {
  document.querySelectorAll(".play-hint[data-video], .clip-media img[data-video]").forEach((el) => {
    el.addEventListener("click", () => {
      const url = el.dataset.video;
      const media = el.closest(".clip-media");
      const badge = media.querySelector(".vbadge");
      media.innerHTML = "";
      if (badge) media.appendChild(badge);
      const v = document.createElement("video");
      // cache-bust: the mp4 is overwritten in place when a clip is re-edited
      v.src = url + (url.includes("?") ? "&" : "?") + "v=" + Date.now();
      v.controls = true; v.autoplay = true; v.playsInline = true;
      media.appendChild(v);
    });
  });
}

/* ---------- caption / title editor ---------- */
function openEditor(clipId) {
  const clip = state.clipsById[clipId];
  if (!clip) return;
  state.editing = clipId;
  $("#edit-title").value = clip.title || "";
  $("#edit-hook").value = clip.hook || "";
  fillSelectKV("#edit-style", state.captionPresets || [], clip.caption_preset || state.projectPreset);
  fillSelectKV("#edit-voice", state.dubVoices || [], clip.voice || "");
  const v = $("#edit-video");
  const url = clip.url || "";
  v.src = url + (url.includes("?") ? "&" : "?") + "v=" + Date.now();
  const box = $("#edit-lines");
  box.innerHTML = "";
  const caps = clip.captions && clip.captions.length ? clip.captions : [{ text: "", start: 0, end: 1 }];
  caps.forEach((ln) => box.appendChild(makeLineRow(ln)));
  $("#edit-msg").textContent = "";
  $("#edit-apply").disabled = false;
  $("#edit-modal").hidden = false;
}

function makeLineRow(ln) {
  const row = document.createElement("div");
  row.className = "line-row";
  row.innerHTML = `
    <input class="ln-text" type="text" value="${escapeHtml(ln.text || "")}" placeholder="caption text" />
    <input class="ln-start" type="number" step="0.05" min="0" value="${(+ln.start || 0).toFixed(2)}" />
    <button class="ln-now" data-target="start" type="button" title="set start to current playback time">now</button>
    <input class="ln-end" type="number" step="0.05" min="0" value="${(+ln.end || 0).toFixed(2)}" />
    <button class="ln-now" data-target="end" type="button" title="set end to current playback time">now</button>
    <button class="ln-del" type="button" title="delete line">✕</button>`;
  row.querySelectorAll(".ln-now").forEach((b) =>
    b.addEventListener("click", () => {
      const t = $("#edit-video").currentTime || 0;
      row.querySelector(b.dataset.target === "start" ? ".ln-start" : ".ln-end").value = t.toFixed(2);
    }));
  row.querySelector(".ln-del").addEventListener("click", () => row.remove());
  return row;
}

function addLine() {
  const t = $("#edit-video").currentTime || 0;
  $("#edit-lines").appendChild(makeLineRow({ text: "", start: t, end: t + 1 }));
}

function collectLines() {
  return [...document.querySelectorAll("#edit-lines .line-row")]
    .map((row) => ({
      text: row.querySelector(".ln-text").value,
      start: parseFloat(row.querySelector(".ln-start").value) || 0,
      end: parseFloat(row.querySelector(".ln-end").value) || 0,
    }))
    .filter((l) => l.text.trim());
}

async function applyEdit() {
  const clipId = state.editing;
  if (clipId == null) return;
  const btn = $("#edit-apply");
  btn.disabled = true;
  $("#edit-msg").textContent = "Re-rendering…";
  try {
    await api.post(`/api/clips/${clipId}/reedit`, {
      title: $("#edit-title").value,
      hook: $("#edit-hook").value,
      caption_preset: $("#edit-style").value,
      voice: $("#edit-voice").value,
      captions: collectLines(),
    });
    closeEditor();
    refreshDetail();
  } catch (err) {
    $("#edit-msg").textContent = "Error: " + err.message;
    btn.disabled = false;
  }
}

function closeEditor() {
  const v = $("#edit-video");
  v.pause();
  v.removeAttribute("src");
  v.load();
  $("#edit-modal").hidden = true;
  $("#edit-apply").disabled = false;
  state.editing = null;
}

/* ---------- utils ---------- */
function fmtDur(s) {
  s = Math.max(0, Math.round(s || 0));
  const m = Math.floor(s / 60), sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}
function escapeHtml(str) {
  return String(str == null ? "" : str).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

boot();
