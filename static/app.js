const state = {
  capabilities: null,
  files: [],
  activeCategory: "all",
  jobId: null,
  successfulResults: [],
};

const browserSession = document.querySelector('meta[name="localconvert-session"]')?.content;
let browserSessionClosed = false;

function heartbeatBrowserSession() {
  if (!browserSession || browserSessionClosed) return;
  fetch(`/api/browser/${encodeURIComponent(browserSession)}/heartbeat`, {
    method: "POST",
    cache: "no-store",
  }).catch(() => { /* The server may already be stopping. */ });
}

function closeBrowserSession() {
  if (!browserSession || browserSessionClosed) return;
  browserSessionClosed = true;
  const url = `/api/browser/${encodeURIComponent(browserSession)}/closed`;
  if (!navigator.sendBeacon(url, new Blob([], { type: "text/plain" }))) {
    fetch(url, { method: "POST", keepalive: true }).catch(() => {});
  }
}

heartbeatBrowserSession();
window.setInterval(heartbeatBrowserSession, 5000);
window.addEventListener("pagehide", closeBrowserSession);

const els = {
  input: document.querySelector("#file-input"),
  dropZone: document.querySelector("#drop-zone"),
  bulkControls: document.querySelector("#bulk-controls"),
  bulkTarget: document.querySelector("#bulk-target"),
  bulkHint: document.querySelector("#bulk-hint"),
  queue: document.querySelector("#queue"),
  clear: document.querySelector("#clear-button"),
  batchActions: document.querySelector("#batch-actions"),
  convert: document.querySelector("#convert-button"),
  convertLabel: document.querySelector("#convert-label"),
  fileTotal: document.querySelector("#file-total"),
  sizeTotal: document.querySelector("#size-total"),
  progress: document.querySelector("#progress-panel"),
  progressLabel: document.querySelector("#progress-label"),
  progressPercent: document.querySelector("#progress-percent"),
  progressBar: document.querySelector("#progress-bar"),
  results: document.querySelector("#results-panel"),
  resultList: document.querySelector("#result-list"),
  downloadOptions: document.querySelector("#download-options"),
  downloadAll: document.querySelector("#download-all"),
  downloadSeparate: document.querySelector("#download-separate"),
  downloadSeparateLabel: document.querySelector("#download-separate-label"),
  newBatch: document.querySelector("#new-batch-button"),
  tabs: document.querySelector("#category-tabs"),
  formatCloud: document.querySelector("#format-cloud"),
  engineNote: document.querySelector("#engine-note"),
  footerEngine: document.querySelector("#footer-engine"),
  toast: document.querySelector("#toast"),
};

const targetDefaults = {
  pdf: "docx", docx: "pdf", txt: "pdf", md: "pdf", html: "pdf", rtf: "pdf",
  png: "webp", jpg: "png", webp: "png", bmp: "png", tiff: "png", ico: "png",
  gif: "mp4", tgs: "json", json: "tgs",
  mp4: "webm", webm: "mp4", mov: "mp4", mkv: "mp4", avi: "mp4", m4v: "mp4", mpeg: "mp4", "3gp": "mp4",
  mp3: "wav", wav: "mp3", ogg: "mp3", flac: "mp3", m4a: "mp3", aac: "mp3", wma: "mp3", opus: "mp3",
};

function humanBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / (1024 ** index);
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function extensionFor(name) {
  const raw = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
  const aliases = { jpeg: "jpg", jpe: "jpg", tif: "tiff", htm: "html", mpg: "mpeg" };
  return aliases[raw] || raw;
}

function toast(message, type = "") {
  els.toast.textContent = message;
  els.toast.className = `toast show ${type}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { els.toast.className = "toast"; }, 3600);
}

function chooseDefaultTarget(format, targets) {
  const preferred = targetDefaults[format];
  if (targets.includes(preferred)) return preferred;
  return targets.find((target) => target !== format) || targets[0];
}

function addFiles(fileList) {
  if (!state.capabilities) {
    toast("The local converter is still starting. Try again in a moment.", "error");
    return;
  }
  let added = 0;
  let rejected = 0;
  for (const file of fileList) {
    if (state.files.length >= state.capabilities.limits.max_files) {
      toast(`A batch can contain at most ${state.capabilities.limits.max_files} files.`, "error");
      break;
    }
    const format = extensionFor(file.name);
    const info = state.capabilities.formats[format];
    if (!info || !info.targets.length) {
      rejected += 1;
      continue;
    }
    state.files.push({
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
      file,
      format,
      category: info.category,
      target: chooseDefaultTarget(format, info.targets),
    });
    added += 1;
  }
  els.input.value = "";
  renderQueue();
  if (rejected) toast(`${rejected} unsupported ${rejected === 1 ? "file was" : "files were"} skipped.`, "error");
  else if (added > 1) toast(`${added} files added to this batch.`);
}

function renderQueue() {
  els.queue.replaceChildren();
  state.files.forEach((item) => {
    const info = state.capabilities.formats[item.format];
    const row = document.createElement("div");
    row.className = "file-row";

    const kind = document.createElement("span");
    kind.className = `file-kind ${item.category}`;
    kind.textContent = item.format.toUpperCase().slice(0, 5);

    const fileInfo = document.createElement("div");
    fileInfo.className = "file-info";
    const filename = document.createElement("strong");
    filename.textContent = item.file.name;
    filename.title = item.file.name;
    const details = document.createElement("small");
    details.textContent = `${info.label} · ${humanBytes(item.file.size)}`;
    fileInfo.append(filename, details);

    const to = document.createElement("span");
    to.className = "to-label";
    to.textContent = "CONVERT TO";

    const select = document.createElement("select");
    select.className = "target-select";
    select.setAttribute("aria-label", `Output format for ${item.file.name}`);
    for (const target of info.targets) {
      const option = document.createElement("option");
      option.value = target;
      option.textContent = target.toUpperCase();
      option.selected = target === item.target;
      select.append(option);
    }
    select.addEventListener("change", () => {
      item.target = select.value;
      syncBulkSelection();
    });

    const remove = document.createElement("button");
    remove.className = "remove-file";
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${item.file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      state.files = state.files.filter((candidate) => candidate.id !== item.id);
      renderQueue();
    });
    row.append(kind, fileInfo, to, select, remove);
    els.queue.append(row);
  });

  const hasFiles = state.files.length > 0;
  els.clear.hidden = !hasFiles;
  els.batchActions.hidden = !hasFiles;
  els.fileTotal.textContent = `${state.files.length} ${state.files.length === 1 ? "file" : "files"}`;
  els.sizeTotal.textContent = `${humanBytes(state.files.reduce((sum, item) => sum + item.file.size, 0))} total`;
  els.convertLabel.textContent = `Convert ${state.files.length} ${state.files.length === 1 ? "file" : "files"}`;
  renderBulkControl();
}

function renderBulkControl() {
  const hasFiles = state.files.length > 0;
  els.bulkControls.hidden = !hasFiles;
  els.bulkTarget.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Choose a format…";
  els.bulkTarget.append(placeholder);
  if (!hasFiles) return;

  const targets = new Set();
  for (const item of state.files) {
    for (const target of state.capabilities.formats[item.format].targets) targets.add(target);
  }
  for (const target of [...targets].sort()) {
    const option = document.createElement("option");
    option.value = target;
    option.textContent = target.toUpperCase();
    els.bulkTarget.append(option);
  }
  syncBulkSelection();
}

function syncBulkSelection() {
  if (!state.files.length) return;
  const selectedTargets = new Set(state.files.map((item) => item.target));
  els.bulkTarget.value = selectedTargets.size === 1 ? state.files[0].target : "";
  els.bulkHint.textContent = selectedTargets.size === 1
    ? `All ${state.files.length} ${state.files.length === 1 ? "file uses" : "files use"} ${state.files[0].target.toUpperCase()}. You can still customize each one below.`
    : "Files currently have individual outputs. You can still customize each one below.";
}

function applyBulkTarget() {
  const target = els.bulkTarget.value;
  if (!target) return;
  let updated = 0;
  let unchanged = 0;
  for (const item of state.files) {
    const targets = state.capabilities.formats[item.format].targets;
    if (targets.includes(target)) {
      item.target = target;
      updated += 1;
    } else {
      unchanged += 1;
    }
  }
  renderQueue();
  if (unchanged) {
    toast(`${updated} compatible ${updated === 1 ? "file was" : "files were"} changed to ${target.toUpperCase()}; ${unchanged} incompatible ${unchanged === 1 ? "file kept" : "files kept"} its individual choice.`);
  } else {
    toast(`All ${updated} ${updated === 1 ? "file was" : "files were"} changed to ${target.toUpperCase()}.`);
  }
}

function renderFormats() {
  const categories = state.capabilities.categories;
  for (const category of categories) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.category = category.id;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", "false");
    button.textContent = category.label;
    els.tabs.append(button);
  }
  els.tabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-category]");
    if (!button) return;
    state.activeCategory = button.dataset.category;
    for (const tab of els.tabs.querySelectorAll("button")) {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    }
    renderFormatCloud();
  });
  renderFormatCloud();

  const engines = state.capabilities.engines;
  const media = engines.ffmpeg ? "FFmpeg ready" : "FFmpeg unavailable";
  const office = engines.libreoffice ? "LibreOffice ready" : "LibreOffice optional";
  els.footerEngine.textContent = `${media} · ${office}`;
  els.engineNote.textContent = engines.libreoffice
    ? "All listed formats are available. LibreOffice is connected for legacy Word, Excel and PowerPoint files."
    : "Legacy .doc, spreadsheet and presentation input appears automatically when LibreOffice is installed. PDF and .docx conversion works now with the built-in local engine.";
}

function renderFormatCloud() {
  els.formatCloud.replaceChildren();
  const entries = Object.entries(state.capabilities.formats)
    .filter(([, info]) => state.activeCategory === "all" || info.category === state.activeCategory)
    .sort(([left], [right]) => left.localeCompare(right));
  for (const [format, info] of entries) {
    const pill = document.createElement("div");
    pill.className = `format-pill ${info.category}`;
    const dot = document.createElement("i");
    const code = document.createElement("b");
    code.textContent = format.toUpperCase();
    const label = document.createElement("span");
    label.textContent = info.label;
    pill.append(dot, code);
    if (info.label.toUpperCase() !== format.toUpperCase()) pill.append(label);
    els.formatCloud.append(pill);
  }
}

function setProgress(percent, label) {
  els.progress.hidden = false;
  els.progressBar.style.width = `${percent}%`;
  els.progressPercent.textContent = `${Math.round(percent)}%`;
  els.progressLabel.textContent = label;
}

function convertBatch() {
  if (!state.files.length || els.convert.disabled) return;
  const formData = new FormData();
  for (const item of state.files) {
    formData.append("files", item.file, item.file.name);
    formData.append("targets", item.target);
  }

  els.convert.disabled = true;
  els.clear.disabled = true;
  els.results.hidden = true;
  setProgress(3, "Preparing batch…");

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/convert");
  xhr.upload.addEventListener("progress", (event) => {
    if (event.lengthComputable) {
      const value = Math.max(5, Math.min(82, (event.loaded / event.total) * 82));
      setProgress(value, "Sending files to the local converter…");
    }
  });
  xhr.upload.addEventListener("load", () => setProgress(88, "Converting on this computer…"));
  xhr.addEventListener("load", () => {
    els.convert.disabled = false;
    els.clear.disabled = false;
    let payload;
    try { payload = JSON.parse(xhr.responseText); }
    catch { payload = { error: "The local converter returned an unreadable response." }; }
    if (xhr.status < 200 || xhr.status >= 300) {
      els.progress.hidden = true;
      toast(payload.error || "The batch could not be converted.", "error");
      return;
    }
    setProgress(100, "Batch complete");
    state.jobId = payload.job_id;
    setTimeout(() => {
      els.progress.hidden = true;
      renderResults(payload);
    }, 350);
  });
  xhr.addEventListener("error", () => {
    els.convert.disabled = false;
    els.clear.disabled = false;
    els.progress.hidden = true;
    toast("Could not reach the local converter. Restart run.bat and try again.", "error");
  });
  xhr.send(formData);
}

function renderResults(payload) {
  els.resultList.replaceChildren();
  state.successfulResults = payload.results.filter((result) => result.status === "success");
  for (const result of payload.results) {
    const row = document.createElement("div");
    row.className = `result-row ${result.status}`;
    const icon = document.createElement("span");
    icon.className = "result-state";
    icon.textContent = result.status === "success" ? "✓" : "!";
    const info = document.createElement("div");
    info.className = "result-info";
    const title = document.createElement("strong");
    title.textContent = result.status === "success" ? result.output_name : result.input_name;
    const detail = document.createElement("small");
    detail.textContent = result.status === "success"
      ? `${humanBytes(result.size)}${result.note ? ` · ${result.note}` : ""}`
      : result.error;
    info.append(title, detail);
    row.append(icon, info);
    if (result.status === "success") {
      const download = document.createElement("a");
      download.className = "download-file";
      download.href = `/api/jobs/${payload.job_id}/files/${result.file_id}`;
      download.textContent = "Download";
      row.append(download);
    }
    els.resultList.append(row);
  }
  const hasBatchDownloads = state.successfulResults.length > 1;
  els.downloadOptions.hidden = !hasBatchDownloads;
  if (hasBatchDownloads && payload.download_all_url) {
    els.downloadAll.href = payload.download_all_url;
  }
  els.results.hidden = false;
  els.results.scrollIntoView({ behavior: "smooth", block: "start" });
  if (payload.success_count) toast(`${payload.success_count} ${payload.success_count === 1 ? "file is" : "files are"} ready.`);
  else toast("None of the files could be converted. Review the messages below.", "error");
}

async function saveSeparateFiles() {
  if (state.successfulResults.length < 2 || els.downloadSeparate.disabled) return;
  els.downloadSeparate.disabled = true;
  const originalLabel = "Save separate files";
  try {
    if ("showDirectoryPicker" in window) {
      const directory = await window.showDirectoryPicker({ id: "localconvert-output", mode: "readwrite" });
      let completed = 0;
      for (const result of state.successfulResults) {
        els.downloadSeparateLabel.textContent = `Saving ${completed + 1} of ${state.successfulResults.length}…`;
        const response = await fetch(`/api/jobs/${state.jobId}/files/${result.file_id}`);
        if (!response.ok) throw new Error(`Could not download ${result.output_name}`);
        const fileHandle = await directory.getFileHandle(result.output_name, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(await response.blob());
        await writable.close();
        completed += 1;
      }
      toast(`${completed} separate files were saved to the selected folder.`);
      return;
    }

    state.successfulResults.forEach((result, index) => {
      window.setTimeout(() => {
        const link = document.createElement("a");
        link.href = `/api/jobs/${state.jobId}/files/${result.file_id}`;
        link.download = result.output_name;
        link.hidden = true;
        document.body.append(link);
        link.click();
        link.remove();
      }, index * 650);
    });
    toast("Separate downloads started. Your browser may ask where to save each file or to allow multiple downloads.");
  } catch (error) {
    if (error?.name === "AbortError") toast("Folder selection was cancelled.");
    else toast(error?.message || "The separate files could not be saved.", "error");
  } finally {
    els.downloadSeparate.disabled = false;
    els.downloadSeparateLabel.textContent = originalLabel;
  }
}

async function resetBatch() {
  const oldJob = state.jobId;
  state.jobId = null;
  state.successfulResults = [];
  state.files = [];
  renderQueue();
  els.results.hidden = true;
  els.resultList.replaceChildren();
  els.downloadOptions.hidden = true;
  window.scrollTo({ top: els.dropZone.getBoundingClientRect().top + window.scrollY - 120, behavior: "smooth" });
  if (oldJob) {
    try { await fetch(`/api/jobs/${oldJob}`, { method: "DELETE" }); } catch { /* expires automatically */ }
  }
}

els.dropZone.addEventListener("click", () => els.input.click());
els.dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); els.input.click(); }
});
els.input.addEventListener("change", () => addFiles(els.input.files));
for (const eventName of ["dragenter", "dragover"]) {
  els.dropZone.addEventListener(eventName, (event) => { event.preventDefault(); els.dropZone.classList.add("dragging"); });
}
for (const eventName of ["dragleave", "drop"]) {
  els.dropZone.addEventListener(eventName, (event) => { event.preventDefault(); els.dropZone.classList.remove("dragging"); });
}
els.dropZone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
els.clear.addEventListener("click", () => { state.files = []; renderQueue(); });
els.bulkTarget.addEventListener("change", applyBulkTarget);
els.convert.addEventListener("click", convertBatch);
els.downloadSeparate.addEventListener("click", saveSeparateFiles);
els.newBatch.addEventListener("click", resetBatch);

fetch("/api/capabilities")
  .then((response) => {
    if (!response.ok) throw new Error("Capability request failed");
    return response.json();
  })
  .then((capabilities) => {
    state.capabilities = capabilities;
    els.input.accept = capabilities.accept.join(",");
    renderFormats();
  })
  .catch(() => {
    els.footerEngine.textContent = "Local engine unavailable";
    toast("Could not load the local conversion engine. Restart the app.", "error");
  });
