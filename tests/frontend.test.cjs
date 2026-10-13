const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const { randomUUID } = require("node:crypto");

function element() {
  return {
    disabled: false, hidden: false, textContent: "", style: {}, attributes: {}, listeners: {},
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener(name, callback) { this.listeners[name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelectorAll() { return []; },
    replaceChildren() {}, append() {}, click() {}, remove() {}, scrollIntoView() {},
    getBoundingClientRect() { return { top: 0 }; },
    emit(name, event = {}) { this.listeners[name]?.(event); },
  };
}

function browser() {
  const elements = new Map();
  const timers = new Map();
  class Request {
    constructor() { this.listeners = {}; this.upload = element(); this.headers = {}; }
    open() {}
    setRequestHeader(name, value) { this.headers[name] = value; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    send() { context.request = this; }
    emit(name) { this.listeners[name](); }
  }
  const context = vm.createContext({
    crypto: { randomUUID }, FormData: class { append() {} }, XMLHttpRequest: Request,
    AbortSignal, Blob, navigator: { sendBeacon() { return true; } },
    fetch: () => new Promise(() => {}),
    setTimeout(callback) { timers.set(callback, callback); return callback; },
    clearTimeout(callback) { timers.delete(callback); },
    window: { setInterval() {}, addEventListener() {}, scrollTo() {} },
    document: {
      querySelector(selector) {
        if (!elements.has(selector)) {
          const node = element(); node.parentElement = element(); elements.set(selector, node);
        }
        return elements.get(selector);
      },
      createElement: element, body: element(),
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8"), context);
  return { context, elements, timers, run: (source) => vm.runInContext(source, context) };
}

test("folder saves preserve existing names and reserve each new filename", () => {
  const { run } = browser();
  assert.equal(run('availableFilename("photo.png", new Set(["photo.png", "photo (2).png"]))'), "photo (3).png");
  assert.equal(run('availableFilename("PHOTO.png", new Set(["photo.png"]))'), "PHOTO (2).png");
  assert.equal(run('const names = new Set(); availableFilename("x.pdf", names); availableFilename("x.pdf", names)'), "x (2).pdf");
});

test("empty and oversized files are rejected before upload", () => {
  const { run, elements } = browser();
  run(`renderQueue = () => {};
    state.capabilities = { limits: { max_files: 50, max_batch_bytes: 2097152 },
      formats: { txt: { category: "documents", targets: ["pdf"] } } };
    addFiles([{ name: "empty.txt", size: 0 }, { name: "large.txt", size: 2097152 },
      { name: "good.txt", size: 100 }]);`);
  assert.equal(run("state.files.length"), 1);
  assert.equal(run("state.files[0].file.name"), "good.txt");
  assert.match(elements.get("#toast").textContent, /limit/);
});

test("conversion freezes queue changes and recovers results after a lost response", async () => {
  const { context, run, elements } = browser();
  run(`state.files = [{ file: { name: "x.txt", size: 10 }, target: "pdf" }];
    renderResults = (payload) => { globalThis.rendered = payload; };
    convertBatch();`);
  assert.equal(run("state.busy"), true);
  assert.equal(elements.get("#bulk-target").disabled, true);
  run('addFiles([{ name: "extra.txt", size: 5 }]); resetBatch();');
  assert.equal(run("state.files.length"), 1);
  assert.match(context.request.headers["X-Conversion-ID"], /^[a-f0-9]{32}$/);
  context.fetch = async () => ({ ok: true, json: async () => ({
    status: "complete", job_id: "recovered", results: [], success_count: 0,
  }) });
  context.request.emit("error");
  await new Promise(setImmediate);
  assert.equal(run("state.busy"), false);
  assert.equal(context.rendered.job_id, "recovered");
  context.request.status = 500;
  context.request.responseText = '{"error":"late response"}';
  context.request.emit("load");
  assert.equal(context.rendered.job_id, "recovered");
});

test("live progress uses completed files and resets controls after HTTP errors", async () => {
  const { context, run, elements } = browser();
  run('state.files = [{ file: { name: "x.txt", size: 10 }, target: "pdf" }]; convertBatch();');
  context.fetch = async () => ({ ok: true, json: async () => ({
    status: "running", total: 4, completed: 2, current_file: "third.txt",
  }) });
  context.request.upload.emit("load");
  await new Promise(setImmediate);
  assert.equal(elements.get("#progress-percent").textContent, "60%");
  assert.match(elements.get("#progress-label").textContent, /3 of 4: third.txt/);
  context.request.status = 429;
  context.request.responseText = '{"error":"Another batch is converting."}';
  context.request.emit("load");
  assert.equal(run("state.busy"), false);
  assert.equal(elements.get("#convert-button").disabled, false);
  assert.match(elements.get("#toast").textContent, /Another batch/);
});

test("unreadable successful responses produce a useful error", () => {
  const { context, run, elements } = browser();
  run('state.files = [{ file: { name: "x.txt", size: 10 }, target: "pdf" }]; convertBatch();');
  context.request.status = 200;
  context.request.responseText = "not JSON";
  context.request.emit("load");
  assert.equal(run("state.busy"), false);
  assert.match(elements.get("#toast").textContent, /unreadable response/);
});

test("folder saves stream content with unique names while batch controls stay locked", async () => {
  const { context, run, elements } = browser();
  const saved = [];
  context.window.showDirectoryPicker = async () => ({
    async *keys() { yield "ONE.pdf"; },
    async getFileHandle(name) {
      assert.equal(run("state.busy"), true);
      return { createWritable: async () => new WritableStream({
        write(chunk) { saved.push([name, new TextDecoder().decode(chunk)]); },
      }) };
    },
  });
  context.fetch = async () => ({ ok: true, body: new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode("content")); controller.close(); },
  }) });
  await run(`state.jobId = "saved";
    state.successfulResults = [{ file_id: "1", output_name: "one.pdf" },
      { file_id: "2", output_name: "two.pdf" }];
    saveSeparateFiles();`);
  assert.deepEqual(saved, [["one (2).pdf", "content"], ["two.pdf", "content"]]);
  assert.equal(run("state.busy"), false);
  assert.equal(elements.get("#new-batch-button").disabled, false);
});
