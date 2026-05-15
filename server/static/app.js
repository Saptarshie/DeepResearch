/** @type {string|null} */
let currentJobId = null;
let currentUsername = "";
let eventSource = null;

// DOM refs
const $ = (id) => document.getElementById(id);
const form = $("researchForm");
const advToggle = $("advToggle");
const advPanel = $("advancedPanel");
const submitBtn = $("submitBtn");
const btnText = $("btnText");
const btnSpinner = $("btnSpinner");
const progressBar = $("progressBar");
const progressPercent = $("progressPercent");
const progressLabel = $("progressLabel");
const progressLog = $("progressLog");
const jobBadge = $("jobBadge");
const resultCard = $("resultCard");
const dlMd = $("dlMd");
const dlPdf = $("dlPdf");
const historyList = $("historyList");
const refreshHistory = $("refreshHistory");
const connStatus = $("connStatus");

// Toggle advanced panel
advToggle.addEventListener("click", () => {
  const hidden = advPanel.classList.toggle("hidden");
  advToggle.querySelector("svg").style.transform = hidden ? "rotate(0deg)" : "rotate(180deg)";
});

// Form submit
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (currentJobId) return; // Prevent double-submit

  const username = $("username").value.trim();
  const query = $("query").value.trim();
  if (!username || !query) return;

  currentUsername = username;
  setBusy(true);
  resetProgress();

  const payload = {
    username,
    query,
    provider: $("provider").value,
    api_key: $("apiKey").value || null,
    base_url: $("baseUrl").value || null,
    model: $("model").value || null,
    max_docs: parseInt($("maxDocs").value, 10),
    max_depth: parseInt($("maxDepth").value, 10),
    max_tokens: parseInt($("maxTokens").value, 10),
    enable_browser: $("enableBrowser").checked,
    enable_pdf_extraction: $("enablePdf").checked,
  };

  try {
    const res = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentJobId = data.job_id;
    updateBadge("running", "Running...");
    connectSSE(currentJobId);
    loadHistory(username);
  } catch (err) {
    log("❌ Failed to start: " + err.message, "error");
    setBusy(false);
  }
});

// SSE progress
function connectSSE(jobId) {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`/api/jobs/${currentUsername}/${jobId}/progress`);

  eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleEvent(event);
  };

  eventSource.onerror = () => {
    eventSource.close();
    // If job not done, try reconnecting once
    setTimeout(() => {
      if (currentJobId) connectSSE(currentJobId);
    }, 2000);
  };
}

function handleEvent(event) {
  const { type, data } = event;

  if (type === "__ping__") return;
  if (type === "__done__") {
    finishJob();
    return;
  }

  switch (type) {
    case "status":
      log(`[${data.phase?.toUpperCase()}] ${data.message}`);
      progressLabel.textContent = data.message;
      break;
    case "plan":
      log(`📋 Generated ${data.queries?.length || 0} search queries`);
      setProgress(5);
      break;
    case "search":
      log(`🔍 Search #${data.query_index} returned ${data.results_count} results`);
      break;
    case "document":
      if (data.phase === "fetching") {
        log(`⬇ Fetching ${truncate(data.url, 60)}...`);
      } else if (data.phase === "extracted") {
        log(`✓ ${data.title} (${data.docs_fetched}/${data.max_docs})`);
        setProgress(5 + (data.docs_fetched / (data.max_docs || 1)) * 40);
      }
      break;
    case "gaps":
      log(`🔍 Gaps found — missing: ${data.missing?.length || 0}, follow-ups: ${data.followup_queries?.length || 0}`);
      break;
    case "warning":
      log(`⚠ ${data.message}`, "warn");
      break;
    case "synth_indexer_batch":
      log(`📚 Indexing batch ${data.current_batch}/${data.total_batches}...`);
      setProgress(50);
      break;
    case "synth_indexer_complete":
      log(`📚 Indexing complete — ${data.topics_count} topics.`);
      setProgress(55);
      break;
    case "synth_overview":
      log(`🗺 ${data.message}`);
      setProgress(60);
      break;
    case "synth_report_start":
      log(`📝 Starting report generation (${data.total_topics} topics)...`);
      setProgress(65);
      break;
    case "synth_report_section":
      {
        const pct = 65 + ((data.topics_processed || 0) / (data.total_topics || 1)) * 30;
        setProgress(pct);
        const title = (data.section_title || "").slice(0, 50);
        log(`📝 Section #${data.section_number}: ${title}`);
        progressLabel.textContent = `Writing section ${data.section_number}: ${title}`;
      }
      break;
    case "synth_report_complete":
      log(`📝 Report writing complete — ${data.sections_written} sections.`);
      setProgress(95);
      break;
    case "complete":
      log(`✅ Done! ${data.docs_count} docs, ${data.report_length} chars`);
      setProgress(100);
      break;
    default:
      log(`[${type}] ${JSON.stringify(data).slice(0, 120)}`);
  }
}

function finishJob() {
  setBusy(false);
  updateBadge("completed", "Completed");
  if (eventSource) { eventSource.close(); eventSource = null; }
  if (currentJobId) {
    setupDownloads(currentJobId, currentUsername);
    loadHistory(currentUsername);
  }
  currentJobId = null;
}

function setupDownloads(jobId, username) {
  const user = username || currentUsername || "anonymous";
  dlMd.href = `/api/jobs/${user}/${jobId}/download?fmt=markdown`;
  dlPdf.href = `/api/jobs/${user}/${jobId}/download?fmt=pdf`;
  resultCard.classList.remove("hidden");
}

// History
refreshHistory.addEventListener("click", () => {
  const u = $("username").value.trim();
  if (u) loadHistory(u);
});

async function loadHistory(username) {
  try {
    const res = await fetch(`/api/jobs/${username}`);
    if (!res.ok) return;
    const jobs = await res.json();
    renderHistory(jobs);
  } catch (err) {
    console.error("History load failed", err);
  }
}

function renderHistory(jobs) {
  if (!jobs.length) {
    historyList.innerHTML = '<div class="text-xs text-slate-400 text-center py-4">No jobs yet</div>';
    return;
  }
  historyList.innerHTML = jobs.map(j => {
    const date = new Date(j.created_at * 1000).toLocaleString();
    const statusColor = j.status === "completed" ? "text-emerald-600 bg-emerald-50" :
                        j.status === "failed" ? "text-rose-600 bg-rose-50" :
                        j.status === "running" ? "text-amber-600 bg-amber-50" :
                        "text-slate-600 bg-slate-100";
    return `
      <div class="group p-3 rounded-lg border border-slate-100 hover:border-indigo-200 hover:bg-indigo-50/30 transition cursor-pointer" data-job="${j.job_id}" data-username="${j.username}">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="text-xs font-medium text-slate-700 truncate">${escapeHtml(j.query.slice(0, 60))}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">${date}</div>
          </div>
          <span class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColor}">${j.status}</span>
        </div>
        ${j.report_available ? `
        <div class="flex gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <a href="/api/jobs/${j.username}/${j.job_id}/download?fmt=markdown" class="text-[10px] text-indigo-600 hover:underline">MD</a>
          <a href="/api/jobs/${j.username}/${j.job_id}/download?fmt=pdf" class="text-[10px] text-rose-600 hover:underline">PDF</a>
        </div>` : ""}
      </div>
    `;
  }).join("");

  // Click to view job detail
  historyList.querySelectorAll("[data-job]").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.tagName === "A") return;
      const jobId = el.dataset.job;
      const username = el.dataset.username;
      viewJobDetail(jobId, username);
    });
  });
}

async function viewJobDetail(jobId, username) {
  const user = username || currentUsername || "anonymous";
  try {
    const res = await fetch(`/api/jobs/${user}/${jobId}`);
    if (!res.ok) return;
    const job = await res.json();
    if (job.report_available && job.report_length > 0) {
      // Load preview
      const mdRes = await fetch(`/api/jobs/${user}/${jobId}/download?fmt=markdown`);
      const md = await mdRes.text();
      $("resultPreview").textContent = md.slice(0, 3000) + (md.length > 3000 ? "\n\n..." : "");
      resultCard.classList.remove("hidden");
      setupDownloads(jobId, user);
    }
  } catch (err) {
    console.error(err);
  }
}

// Helpers
function log(message, level = "info") {
  const line = document.createElement("div");
  const time = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  line.className = level === "error" ? "text-rose-400" : level === "warn" ? "text-amber-400" : "";
  line.textContent = `[${time}] ${message}`;
  progressLog.appendChild(line);
  progressLog.scrollTop = progressLog.scrollHeight;
}

function setProgress(pct) {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  progressBar.style.width = clamped + "%";
  progressPercent.textContent = clamped + "%";
}

function resetProgress() {
  progressLog.innerHTML = "";
  setProgress(0);
  progressLabel.textContent = "Initializing...";
  resultCard.classList.add("hidden");
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  btnSpinner.classList.toggle("hidden", !busy);
  btnText.textContent = busy ? "Researching..." : "Start Research";
  if (!busy) {
    updateBadge("ready", "Ready");
  }
}

function updateBadge(status, text) {
  jobBadge.classList.remove("hidden");
  const colors = {
    ready: "bg-slate-100 text-slate-600",
    running: "bg-amber-100 text-amber-700",
    completed: "bg-emerald-100 text-emerald-700",
    failed: "bg-rose-100 text-rose-700",
  };
  jobBadge.className = `px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || colors.ready}`;
  jobBadge.textContent = text;
}

function truncate(str, n) {
  return str && str.length > n ? str.slice(0, n - 1) + "..." : str;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Init
loadHistory($("username").value.trim());
