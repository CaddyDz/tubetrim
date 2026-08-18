"use strict";

const $ = (id) => document.getElementById(id);

const urlInput = $("url");
const urlError = $("url-error");
const infoLoading = $("info-loading");
const card = $("card");
const thumb = $("thumb");
const videoTitle = $("video-title");
const videoSub = $("video-sub");
const startInput = $("start");
const endInput = $("end");
const formatSel = $("format");
const convertBtn = $("convert");
const jobError = $("job-error");
const progressBox = $("progress");
const progressFill = $("progress-fill");
const statusLabel = $("status-label");
const statusPct = $("status-pct");
const downloadBox = $("download");
const downloadLink = $("download-link");

const STATUS_LABELS = {
  queued: "Queued…",
  fetching: "Fetching info…",
  downloading: "Downloading…",
  processing: "Converting…",
  done: "Done",
};

let debounceTimer = null;
let infoSeq = 0; // ignore /api/info responses that arrive out of order
let pollTimer = null;

function formatSeconds(total) {
  const s = Math.round(total);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  const h = Math.floor(s / 3600);
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

// "90" | "1:30" | "1:02:30" -> seconds; blank -> null; anything else -> NaN
function parseTime(text) {
  const t = text.trim();
  if (!t) return null;
  if (/^\d+$/.test(t)) return Number(t);
  let m = /^(\d+):([0-5]?\d)$/.exec(t);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  m = /^(\d+):([0-5]?\d):([0-5]?\d)$/.exec(t);
  if (m) return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
  return NaN;
}

async function readDetail(res) {
  try {
    return (await res.json()).detail;
  } catch {
    return null;
  }
}

urlInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  infoSeq++; // invalidate in-flight info requests for the previous value
  urlError.textContent = "";
  const url = urlInput.value.trim();
  if (!url) {
    infoLoading.hidden = true;
    card.hidden = true;
    return;
  }
  debounceTimer = setTimeout(() => fetchInfo(url), 600);
});

async function fetchInfo(url) {
  const seq = ++infoSeq;
  infoLoading.hidden = false;
  try {
    const res = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (seq !== infoSeq) return;
    infoLoading.hidden = true;
    if (!res.ok) {
      urlError.textContent = (await readDetail(res)) || "Could not fetch video info";
      card.hidden = true;
      return;
    }
    const info = await res.json();
    if (seq !== infoSeq) return;
    renderCard(info);
  } catch {
    if (seq !== infoSeq) return;
    infoLoading.hidden = true;
    urlError.textContent = "Network error — could not reach the server";
    card.hidden = true;
  }
}

function renderCard(info) {
  stopPolling();
  if (info.thumbnail) {
    thumb.src = info.thumbnail;
    thumb.hidden = false;
  } else {
    thumb.hidden = true;
  }
  videoTitle.textContent = info.title;
  const duration = formatSeconds(info.duration);
  videoSub.textContent = "";
  if (info.uploader) videoSub.append(info.uploader, " · ");
  const time = document.createElement("span");
  time.className = "time";
  time.textContent = duration;
  videoSub.append(time);

  startInput.value = "";
  endInput.value = "";
  endInput.placeholder = duration;
  jobError.textContent = "";
  progressBox.hidden = true;
  downloadBox.hidden = true;
  convertBtn.disabled = false;
  card.hidden = false;
}

convertBtn.addEventListener("click", startJob);

async function startJob() {
  jobError.textContent = "";
  const start = parseTime(startInput.value);
  const end = parseTime(endInput.value);
  if (Number.isNaN(start) || Number.isNaN(end)) {
    jobError.textContent = "Times must look like 1:30, 1:02:30, or plain seconds";
    return;
  }
  if (start !== null && end !== null && start >= end) {
    jobError.textContent = "Start must be before end";
    return;
  }
  convertBtn.disabled = true;
  downloadBox.hidden = true;
  setProgress(0, STATUS_LABELS.queued);
  progressBox.hidden = false;
  try {
    const res = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: urlInput.value.trim(),
        format: formatSel.value,
        start,
        end,
      }),
    });
    if (!res.ok) {
      failJob((await readDetail(res)) || "Could not start the conversion");
      return;
    }
    const job = await res.json();
    pollTimer = setInterval(() => pollJob(job.id), 1000);
  } catch {
    failJob("Network error — could not reach the server");
  }
}

async function pollJob(id) {
  try {
    const res = await fetch(`/api/jobs/${id}`);
    if (!res.ok) {
      failJob("Job not found — try converting again");
      return;
    }
    const job = await res.json();
    if (job.status === "error") {
      failJob(job.error || "Processing failed");
      return;
    }
    setProgress(job.progress, STATUS_LABELS[job.status] || job.status);
    if (job.status === "done") {
      stopPolling();
      downloadLink.href = `/api/jobs/${id}/file`;
      downloadBox.hidden = false;
      convertBtn.disabled = false;
    }
  } catch {
    // transient network blip: keep polling
  }
}

function failJob(message) {
  stopPolling();
  jobError.textContent = message;
  progressBox.hidden = true;
  convertBtn.disabled = false;
}

function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

function setProgress(pct, label) {
  progressFill.style.width = `${pct}%`;
  statusLabel.textContent = label;
  statusPct.textContent = `${pct}%`;
}
