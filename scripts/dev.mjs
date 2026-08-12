import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createHash, randomBytes } from "node:crypto";
import { networkInterfaces } from "node:os";
import { resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import process from "node:process";

const root = resolve(import.meta.dirname, "..");
const backendDir = resolve(root, "backend");
const frontendDir = resolve(root, "frontend");
const isWindows = process.platform === "win32";
const python = resolve(backendDir, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const setupOnly = process.argv.includes("--setup-only");
const backendOnly = process.argv.includes("--backend-only");
const lanMode = process.argv.includes("--lan");
const children = new Set();

function localEnvironment() {
  const path = resolve(root, ".env.local");
  if (!existsSync(path)) return {};
  const values = {};
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const separator = line.indexOf("=");
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
    values[key] = value;
  }
  return values;
}

const paint = {
  cyan: (value) => `\x1b[36m${value}\x1b[0m`,
  green: (value) => `\x1b[32m${value}\x1b[0m`,
  yellow: (value) => `\x1b[33m${value}\x1b[0m`,
  red: (value) => `\x1b[31m${value}\x1b[0m`,
};

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit", shell: false, ...options });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function commandExists(command) {
  const check = spawnSync(isWindows ? "where" : "which", [command], { stdio: "ignore", shell: isWindows });
  return check.status === 0;
}

function setup() {
  console.log(paint.cyan("\n5G RCA Copilot · environment check\n"));
  if (!existsSync(python)) {
    if (!commandExists("uv")) {
      console.error(paint.red("Python environment belum tersedia dan command `uv` tidak ditemukan."));
      console.error("Install uv dari https://docs.astral.sh/uv/ lalu jalankan kembali `npm run dev`.");
      process.exit(1);
    }
    console.log(paint.yellow("Membuat Python virtual environment…"));
    run("uv", ["venv", resolve(backendDir, ".venv")], {
      env: { ...process.env, UV_CACHE_DIR: resolve(root, ".uv-cache") },
    });
  }
  const requirements = resolve(backendDir, "requirements.txt");
  const requirementsMarker = resolve(backendDir, ".venv", ".requirements-ready");
  const requirementsHash = createHash("sha256").update(readFileSync(requirements)).digest("hex");
  const installedHash = existsSync(requirementsMarker) ? readFileSync(requirementsMarker, "utf8").trim() : "";
  if (installedHash !== requirementsHash) {
    if (!commandExists("uv")) {
      console.error(paint.red("Dependency backend berubah tetapi command `uv` tidak ditemukan."));
      process.exit(1);
    }
    console.log(paint.yellow("Memasang dependency backend…"));
    run("uv", ["pip", "install", "--python", python, "-r", requirements], {
      env: { ...process.env, UV_CACHE_DIR: resolve(root, ".uv-cache") },
    });
    writeFileSync(requirementsMarker, `${requirementsHash}\n`);
  }
  if (!existsSync(resolve(frontendDir, "node_modules", "next", "package.json"))) {
    console.log(paint.yellow("Memasang dependency frontend…"));
    run("npm", ["install", "--prefix", frontendDir], { shell: isWindows });
  }
  if (!existsSync(resolve(root, "data", "sample_logs.jsonl"))) {
    console.log(paint.yellow("Membuat synthetic demo dataset…"));
    run(python, [resolve(root, "scripts", "generate_synthetic_data.py")]);
  }
  console.log(paint.green("✓ Environment siap\n"));
}

function start(label, command, args, cwd, env = {}) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: "inherit",
    shell: false,
  });
  children.add(child);
  child.on("exit", (code, signal) => {
    children.delete(child);
    if (!shuttingDown && code !== 0) {
      console.error(paint.red(`${label} berhenti (code ${code ?? signal}).`));
      shutdown(code ?? 1);
    }
  });
  return child;
}

function lanAddresses() {
  return Object.values(networkInterfaces()).flat().filter((item) => item && item.family === "IPv4" && !item.internal).map((item) => item.address);
}

async function waitFor(url, label, attempts = 90) {
  for (let index = 0; index < attempts; index += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 500));
  }
  throw new Error(`${label} tidak merespons di ${url}`);
}

let shuttingDown = false;
function stopChild(child) {
  if (!child.pid) return;
  if (isWindows) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  else child.kill("SIGTERM");
}
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) stopChild(child);
  process.exit(code);
}

setup();
if (setupOnly) process.exit(0);

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const fileEnvironment = localEnvironment();
const runtimeSecret = process.env.JWT_SECRET || fileEnvironment.JWT_SECRET || randomBytes(48).toString("base64url");
start("Backend", python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"], backendDir, {
  ...fileEnvironment,
  APP_ENV: "development",
  JWT_SECRET: runtimeSecret,
});

if (backendOnly) {
  await waitFor("http://127.0.0.1:8000/api/health", "Backend");
  console.log(paint.green("\n✓ Backend ready: http://localhost:8000/docs\n"));
} else {
  const nextBin = resolve(frontendDir, "node_modules", "next", "dist", "bin", "next");
  start("Frontend", process.execPath, [nextBin, "dev", "--hostname", lanMode ? "0.0.0.0" : "127.0.0.1", "--port", "3000"], frontendDir, {
    API_URL: "http://127.0.0.1:8000",
  });
  try {
    await Promise.all([
      waitFor("http://127.0.0.1:8000/api/health", "Backend"),
      waitFor("http://127.0.0.1:3000/login", "Frontend"),
    ]);
    console.log(paint.green("\n✓ 5G RCA Copilot ready"));
    console.log(`  Dashboard : ${paint.cyan("http://localhost:3000")}`);
    console.log(`  API docs  : ${paint.cyan("http://localhost:8000/docs")}`);
    if (lanMode) for (const address of lanAddresses()) console.log(`  LAN       : ${paint.cyan(`http://${address}:3000`)}`);
    console.log("\n  Login     : admin@5grca.local / admin123");
    console.log("  Stop      : Ctrl+C\n");
  } catch (error) {
    console.error(paint.red(`\nStartup gagal: ${error.message}`));
    shutdown(1);
  }
}

await new Promise(() => {});
