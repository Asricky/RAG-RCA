import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import process from "node:process";

const root = resolve(import.meta.dirname, "..");
const isWindows = process.platform === "win32";
const python = resolve(root, "backend", ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const setup = spawnSync(process.execPath, [resolve(root, "scripts", "dev.mjs"), "--setup-only"], { cwd: root, stdio: "inherit" });
if (setup.status !== 0) process.exit(setup.status ?? 1);
if (!existsSync(python)) {
  console.error("Run `npm run setup` first.");
  process.exit(1);
}
const backend = spawnSync(python, ["-m", "pytest", "-q"], { cwd: resolve(root, "backend"), stdio: "inherit", env: { ...process.env, APP_ENV: "test" } });
if (backend.status !== 0) process.exit(backend.status ?? 1);
const frontend = spawnSync("npm", ["--prefix", "frontend", "run", "build"], { cwd: root, stdio: "inherit", shell: isWindows });
process.exit(frontend.status ?? 1);
