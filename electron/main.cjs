"use strict";
const { app, BrowserWindow, dialog, ipcMain, shell, Menu } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..");
const IS_DEV = !app.isPackaged;
const START_TIMEOUT_MS = 30000;
const DATA_FILES = ["hearth.json", "hearth.json.bak", "config.json"];

// NOTE: if Chromium's SUID sandbox is not configured (dev checkout), launch with
// `electron . --no-sandbox` (a CLI flag; it cannot be set from JS). See README.

let win = null;
let backend = null; // { proc, stderrTail }
let backendPort = 0;
let dataDir = "";
let quitting = false;

// ---------- config ----------
function configPath() {
  return path.join(app.getPath("userData"), "desktop-config.json");
}
function loadDataDir() {
  try {
    const c = JSON.parse(fs.readFileSync(configPath(), "utf8"));
    if (c.dataDir && typeof c.dataDir === "string") return c.dataDir;
  } catch {}
  return process.env.HEARTH_DATA_DIR || (IS_DEV ? path.join(REPO_ROOT, "data") : path.join(app.getPath("userData"), "data"));
}
function saveDataDir(dir) {
  fs.mkdirSync(app.getPath("userData"), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify({ dataDir: dir }, null, 2));
}

// ---------- backend ----------
function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function backendCommand() {
  const win32 = process.platform === "win32";
  if (IS_DEV) {
    const py = win32 ? path.join(REPO_ROOT, ".venv", "Scripts", "python.exe") : path.join(REPO_ROOT, ".venv", "bin", "python");
    return { cmd: py, args: ["-m", "backend"], cwd: REPO_ROOT, dist: path.join(REPO_ROOT, "dist") };
  }
  const dir = path.join(process.resourcesPath, "hearth-backend");
  const exe = path.join(dir, win32 ? "hearth-backend.exe" : "hearth-backend");
  return { cmd: exe, args: [], cwd: dir, dist: path.join(process.resourcesPath, "dist") };
}

function pingHealth(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/api/health", timeout: 1000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function startBackend() {
  fs.mkdirSync(dataDir, { recursive: true });
  const port = await freePort();
  const b = backendCommand();
  const env = { ...process.env, HEARTH_HOST: "127.0.0.1", HEARTH_PORT: String(port), HEARTH_DATA_DIR: dataDir, HEARTH_DIST_DIR: b.dist, PYTHONUNBUFFERED: "1" };
  const state = { proc: null, stderrTail: "", exited: false, exitInfo: "" };
  const proc = spawn(b.cmd, b.args, { cwd: b.cwd, env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  state.proc = proc;
  const keep = (d) => { state.stderrTail = (state.stderrTail + d.toString()).slice(-4000); };
  proc.stderr.on("data", keep);
  proc.stdout.on("data", (d) => { if (IS_DEV) process.stdout.write("[backend] " + d); keep(d); });
  proc.on("error", (e) => { state.exited = true; state.exitInfo = String(e); state.stderrTail += "\n" + String(e); });
  proc.on("exit", (code, sig) => { state.exited = true; state.exitInfo = `exit code ${code} signal ${sig}`; });
  backend = state;
  backendPort = port;

  const deadline = Date.now() + START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (state.exited) throw new Error(`Backend exited early (${state.exitInfo}).\n\n${state.stderrTail}`);
    if (await pingHealth(port)) {
      console.log(`[hearth] backend up on 127.0.0.1:${port} (data: ${dataDir})`);
      return;
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Backend did not respond within ${START_TIMEOUT_MS / 1000}s.\n\n${state.stderrTail}`);
}

function killTree(proc) {
  if (!proc || proc.exitCode !== null || proc.signalCode) return;
  try {
    if (process.platform === "win32") spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { windowsHide: true });
    else proc.kill("SIGTERM");
  } catch {}
}

function stopBackend() {
  const state = backend;
  backend = null;
  if (!state || !state.proc) return Promise.resolve();
  const proc = state.proc;
  if (proc.exitCode !== null || proc.signalCode) return Promise.resolve();
  return new Promise((resolve) => {
    const t = setTimeout(() => { try { proc.kill("SIGKILL"); } catch {} }, 3000);
    proc.once("exit", () => { clearTimeout(t); resolve(); });
    killTree(proc);
  });
}

// Synchronous last-resort kill (process 'exit' handlers cannot await).
function killBackendNow() {
  if (backend && backend.proc && backend.proc.exitCode === null) {
    try { backend.proc.kill("SIGKILL"); } catch {}
  }
}

// ---------- window ----------
const SPLASH = "data:text/html;charset=utf-8," + encodeURIComponent(`<!doctype html><meta charset=utf-8><title>Hearth Ledger</title>
<style>html,body{height:100%;margin:0;font-family:system-ui,sans-serif;background:#faf7f2;color:#4a3f35;display:flex;align-items:center;justify-content:center;flex-direction:column}
.s{width:34px;height:34px;border:4px solid #e4dccf;border-top-color:#b4572f;border-radius:50%;animation:r 1s linear infinite;margin-bottom:16px}@keyframes r{to{transform:rotate(360deg)}}</style>
<div class=s></div><div>Starting Hearth Ledger&hellip;</div>`);

function createWindow() {
  win = new BrowserWindow({
    width: 1440, height: 960, minWidth: 900, minHeight: 600, autoHideMenuBar: true,
    title: "Hearth Ledger", show: false, backgroundColor: "#faf7f2",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  });
  win.setMenuBarVisibility(false);
  // Open maximised so pages fit without needing to scroll on a normal display.
  win.once("ready-to-show", () => { win.maximize(); win.show(); });
  // Keyboard shortcuts that used to live in the menu: reload (Ctrl/Cmd+R, F5) always,
  // devtools (F12, Ctrl/Cmd+Shift+I) only when running from the repo.
  win.webContents.on("before-input-event", (e, input) => {
    if (input.type !== "keyDown") return;
    const mod = input.control || input.meta;
    const key = (input.key || "").toLowerCase();
    if (key === "f5" || (mod && !input.shift && key === "r")) { win.webContents.reload(); e.preventDefault(); }
    else if (IS_DEV && (key === "f12" || (mod && input.shift && key === "i"))) { win.webContents.toggleDevTools(); e.preventDefault(); }
  });
  win.on("closed", () => { win = null; });
  win.webContents.on("did-finish-load", () => console.log("[hearth] did-finish-load", win && win.webContents.getURL().slice(0, 80)));
  // Never let the page change the window title.
  win.on("page-title-updated", (e) => e.preventDefault());

  const allowed = (url) => {
    if (url.startsWith("data:text/html")) return true; // our splash
    try { return new URL(url).origin === `http://127.0.0.1:${backendPort}`; } catch { return false; }
  };
  win.webContents.on("will-navigate", (e, url) => {
    if (!allowed(url)) { e.preventDefault(); openExternal(url); }
  });
  win.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: "deny" }; });
  win.loadURL(SPLASH);
}

function openExternal(url) {
  try {
    const u = new URL(url);
    if (u.protocol === "http:" || u.protocol === "https:" || u.protocol === "mailto:") shell.openExternal(url);
  } catch {}
}

function buildMenu() {
  // No menu bar at all (no "View" dropdown). Dev shortcuts are handled in createWindow.
  Menu.setApplicationMenu(null);
}

async function boot() {
  try {
    await startBackend();
    if (win) await win.loadURL(`http://127.0.0.1:${backendPort}/`);
  } catch (err) {
    await stopBackend();
    dialog.showErrorBox("Hearth Ledger could not start", String(err.message || err));
    app.quit();
  }
}

// ---------- IPC ----------
function fileExists(p) { try { return fs.statSync(p).isFile(); } catch { return false; } }

ipcMain.handle("hearth:open-data-dir", async () => { await shell.openPath(dataDir); });

ipcMain.handle("hearth:choose-data-dir", async () => {
  const r = await dialog.showOpenDialog(win, {
    title: "Choose data folder", defaultPath: dataDir, properties: ["openDirectory", "createDirectory"],
  });
  if (r.canceled || !r.filePaths[0]) return null;
  const target = path.resolve(r.filePaths[0]);
  if (target === path.resolve(dataDir)) return { path: target };

  if (fileExists(path.join(target, "hearth.json"))) {
    const c = await dialog.showMessageBox(win, {
      type: "question", buttons: ["Use existing data", "Cancel"], defaultId: 1, cancelId: 1,
      title: "Existing data found",
      message: "This folder already contains Hearth Ledger data.",
      detail: `Use the existing data in:\n${target}\n\nNothing there will be overwritten. Your current data stays in ${dataDir}.`,
    });
    if (c.response !== 0) return null;
  } else {
    try {
      fs.mkdirSync(target, { recursive: true });
      for (const f of DATA_FILES) {
        const src = path.join(dataDir, f);
        const dst = path.join(target, f);
        if (fileExists(src) && !fs.existsSync(dst)) fs.copyFileSync(src, dst);
      }
    } catch (e) {
      dialog.showErrorBox("Could not copy data", String(e.message || e));
      return null;
    }
  }

  const previous = dataDir;
  try {
    await stopBackend();
    dataDir = target;
    saveDataDir(target);
    await startBackend();
    if (win) await win.loadURL(`http://127.0.0.1:${backendPort}/`);
  } catch (e) {
    await stopBackend();
    dataDir = previous;
    saveDataDir(previous);
    dialog.showErrorBox("Could not start with new data folder", String(e.message || e));
    try { await startBackend(); if (win) await win.loadURL(`http://127.0.0.1:${backendPort}/`); } catch {}
    return null;
  }
  return { path: target };
});

// ---------- lifecycle ----------
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
  });

  app.whenReady().then(() => {
    dataDir = loadDataDir();
    buildMenu();
    createWindow();
    boot();
  });

  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", (e) => {
    if (quitting) return;
    quitting = true;
    e.preventDefault();
    stopBackend().finally(() => app.quit());
  });
  app.on("will-quit", killBackendNow);

  process.on("exit", killBackendNow);
  for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(sig, () => { stopBackend().finally(() => app.exit(0)); });
  }
  process.on("uncaughtException", (e) => {
    console.error("[hearth] uncaught", e);
    killBackendNow();
    app.exit(1);
  });
}
