# 5G RCA Copilot

Prototype observability dan root cause analysis untuk log 5G Core. Aplikasi menyediakan dashboard Next.js, API FastAPI, autentikasi role-based, hybrid retrieval, evidence bundle, RCA berbasis evidence, synthetic dataset, incident management, upload dataset, dan evaluation lab.

## Menjalankan aplikasi

Dari direktori root, cukup jalankan:

```powershell
npm run dev
```

Perintah tersebut otomatis:

1. membuat Python virtual environment jika belum ada;
2. memasang dependency backend dan frontend jika dibutuhkan;
3. membuat synthetic dataset jika belum tersedia;
4. menjalankan FastAPI pada port `8000`;
5. menjalankan Next.js pada port `3000`;
6. menampilkan URL setelah kedua service siap.

Buka <http://localhost:3000> dan login dengan:

```text
Email    : admin@5grca.local
Password : admin123
```

Hentikan seluruh service dengan `Ctrl+C` pada terminal yang sama.

### Akses dari perangkat lain

Gunakan mode LAN secara eksplisit:

```powershell
npm run dev:lan
```

Launcher akan menampilkan URL LAN, misalnya `http://10.x.x.x:3000`. Perangkat harus berada pada jaringan yang sama dan Windows Firewall harus mengizinkan TCP port `3000`. Mode `npm run dev` biasa hanya bind ke localhost untuk keamanan.

### Perintah lain

```powershell
npm run setup          # hanya menyiapkan dependency
npm test               # backend tests + frontend production build
npm run build          # frontend production build
npm run data:generate  # regenerasi 400 synthetic logs
npm run dev:backend    # hanya FastAPI
```

API documentation tersedia di <http://localhost:8000/docs> ketika aplikasi berjalan.

## Docker Compose

Untuk PostgreSQL dan OpenSearch penuh:

```powershell
Copy-Item .env.example .env
# Isi JWT_SECRET dengan nilai acak yang kuat
docker compose up --build
```

OpenSearch dan backend hanya dipublikasikan pada loopback host; browser mengakses API melalui reverse proxy Next.js. Ollama diharapkan berjalan pada host port `11434`. Jika OpenSearch atau Ollama tidak tersedia, aplikasi lokal tetap dapat didemokan menggunakan in-memory retrieval dan mock-safe RCA fallback.

## Dokumentasi

Penjelasan arsitektur, struktur modul, aliran data, API, database, keamanan, hasil audit, testing, dan gap terhadap PRD tersedia di [CODEBASE.md](CODEBASE.md).

Panduan terperinci untuk SQLite/PostgreSQL, Docker database, OpenSearch, serta koneksi model Ollama tersedia di [DATABASE_AND_AI_SETUP.md](DATABASE_AND_AI_SETUP.md).

Semua data bawaan bersifat sintetis dan tidak mengandung data customer.
