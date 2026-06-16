// Clover <-> MusicXML — client-side converter UI.
// Loads Pyodide, installs the bundled (clean) clover2xml wheel, and runs all
// conversions in-browser. No file ever leaves the machine.

const WHEELS = [
  "./wheels/defusedxml-0.7.1-py2.py3-none-any.whl",
  "./wheels/clover2xml-0.1.0-py3-none-any.whl",
];

const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const sampleBtn = document.getElementById("sampleBtn");
const zipBtn = document.getElementById("zipBtn");

let py = null;
let convert = null;          // Python module proxy
const produced = [];        // {name, bytes} for ZIP-all

function setStatus(msg, kind = "") {
  statusEl.textContent = msg;
  statusEl.className = "status " + kind;
}

async function boot() {
  try {
    py = await loadPyodide();
    setStatus("変換モジュールを読み込み中…");
    await py.loadPackage("micropip");
    const micropip = py.pyimport("micropip");
    for (const w of WHEELS) await micropip.install(w);
    const src = await (await fetch("./convert.py")).text();
    py.FS.writeFile("/convert.py", src);
    py.runPython("import sys; sys.path.insert(0, '/')");
    convert = py.pyimport("convert");
    setStatus("準備完了。ファイルをドロップしてください。", "ok");
    sampleBtn.disabled = false;
  } catch (e) {
    setStatus("読み込みに失敗しました: " + e, "err");
    console.error(e);
  }
}

function download(name, bytes) {
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function addResult(name, bytes, note) {
  produced.push({ name, bytes });
  const li = document.createElement("li");
  li.className = "result-row ok";
  const label = document.createElement("span");
  label.textContent = note;
  const btn = document.createElement("button");
  btn.textContent = "⬇ " + name;
  btn.onclick = () => download(name, bytes);
  li.append(label, btn);
  resultsEl.appendChild(li);
  if (produced.length > 1) zipBtn.hidden = false;
}

function addError(name, msg) {
  const li = document.createElement("li");
  li.className = "result-row err";
  li.textContent = `✗ ${name}: ${msg}`;
  resultsEl.appendChild(li);
}

const TARGET_EXT = { musicxml: ".musicxml", clvz: ".clvz", mid: ".mid" };
const INPUT_OK = [".clvz", ".musicxml", ".xml", ".mid", ".midi"];

async function convertFile(file) {
  const lower = file.name.toLowerCase();
  const base = file.name.replace(/\.[^.]+$/, "");
  if (!INPUT_OK.some((e) => lower.endsWith(e))) {
    addError(file.name, "未対応の拡張子です（.clvz / .musicxml / .mid）");
    return;
  }
  const target = document.getElementById("targetSel").value;
  try {
    const buf = new Uint8Array(await file.arrayBuffer());
    const res = convert.convert(file.name, buf, target);
    const bytes = target === "musicxml"
      ? new TextEncoder().encode(res)
      : res.toJs();
    addResult(base + TARGET_EXT[target], bytes,
              `${file.name} → ${target.toUpperCase()}`);
  } catch (e) {
    addError(file.name, String(e).split("\n").pop());
  }
}

async function handleFiles(files) {
  if (!convert) { setStatus("まだ準備中です…", "err"); return; }
  setStatus(`変換中… (${files.length}件)`);
  for (const f of files) await convertFile(f);
  setStatus(`完了： ${produced.length}件を変換しました。`, "ok");
}

// --- wiring -------------------------------------------------------------
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFiles([...e.target.files]));

["dragover", "dragenter"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.add("over");
  }));
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.remove("over");
  }));
dropzone.addEventListener("drop", (e) =>
  handleFiles([...e.dataTransfer.files]));

sampleBtn.addEventListener("click", async () => {
  const r = await fetch("./samples/demo.clvz");
  const blob = await r.blob();
  const file = new File([blob], "demo.clvz", { type: "application/octet-stream" });
  handleFiles([file]);
});

zipBtn.addEventListener("click", () => {
  const entries = produced.map(({ name, bytes }) => [name, bytes]);
  const zip = convert.make_zip(entries).toJs();
  download("converted.zip", zip);
});

boot();
