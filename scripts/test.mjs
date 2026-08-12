import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import process from "node:process";

const root = resolve(import.meta.dirname, "..");
const isWindows = process.platform === "win32";
const python = resolve(root, "backend", ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
if (!existsSync(python)) {
  console.error("Jalankan `npm run setup` terlebih dahulu.");
  process.exit(1);
}
const backend = spawnSync(python, ["-m", "pytest", "-q"], { cwd: resolve(root, "backend"), stdio: "inherit", env: { ...process.env, APP_ENV: "test" } });
if (backend.status !== 0) process.exit(backend.status ?? 1);
const frontend = spawnSync("npm", ["--prefix", "frontend", "run", "build"], { cwd: root, stdio: "inherit", shell: isWindows });
process.exit(frontend.status ?? 1);
