# 5G RCA Copilot — Codebase Guide dan Technical Audit

Dokumen ini menjelaskan kondisi codebase pada 12 Agustus 2026: tujuan sistem, arsitektur, cara kerja setiap lapisan, model data, API, aliran retrieval/RCA, keamanan, pengalaman pengguna, deployment, testing, serta gap yang masih perlu diselesaikan menuju production.

## 1. Ringkasan produk

5G RCA Copilot adalah aplikasi observability untuk investigasi insiden pada AMF, SMF, dan UPF. Pengguna dapat melihat log, memfilter event, memilih evidence, meminta analisis AI, membuka raw log yang dikutip, dan memeriksa skor retrieval.

Codebase ini dapat berjalan dalam dua profil:

- **Local demo**: Next.js + FastAPI + SQLite + 400 synthetic logs. Retrieval dan RCA mempunyai fallback lokal sehingga demo langsung berjalan.
- **Docker infrastructure**: Next.js + FastAPI + PostgreSQL + OpenSearch. Ollama dapat dijalankan terpisah pada host.

Status implementasi saat ini adalah **runnable research prototype**, bukan production NOC platform. Jalur utama demo berfungsi, tetapi beberapa integrasi PRD masih berupa adapter/fallback yang dijelaskan pada bagian gap.

## 2. Quick start

Requirement minimum:

- Node.js 20 atau lebih baru;
- Python 3.11;
- `uv` untuk membuat environment Python saat setup pertama.

Jalankan dari root repository:

```powershell
npm run dev
```

Launcher [scripts/dev.mjs](scripts/dev.mjs) memeriksa environment, memasang dependency yang belum tersedia, menyalakan backend dan frontend, menunggu health check, lalu mencetak URL. `Ctrl+C` menghentikan kedua child process.

Mode default hanya tersedia dari komputer lokal:

```text
Dashboard  http://localhost:3000
API docs   http://localhost:8000/docs
```

Mode perangkat lain pada LAN harus diaktifkan secara sadar:

```powershell
npm run dev:lan
```

Credential demo:

```text
ADMIN    admin@5grca.local   / admin123
ANALYST  analyst@5grca.local / analyst123
```

Credential demo tidak boleh digunakan pada deployment publik.

## 3. Arsitektur runtime

```text
Browser
  │
  │ HTTP + SSE (port 3000)
  ▼
Next.js frontend
  │
  │ /api/* reverse proxy
  ▼
FastAPI backend (port 8000, loopback pada local launcher)
  ├── SQLAlchemy ── SQLite local / PostgreSQL Docker
  ├── LogStore ──── JSONL memory store + optional OpenSearch indexing
  ├── Retrieval ─── BM25 + semantic feature hashing + score fusion
  └── LLM adapter ─ Ollama + deterministic safe fallback
```

Frontend tidak berkomunikasi langsung dengan OpenSearch. Semua request browser masuk melalui `/api/*` dan diteruskan oleh `frontend/next.config.ts` ke FastAPI.

## 4. Struktur repository

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                 route, lifecycle, seed, validation
│   │   ├── config.py               environment configuration
│   │   ├── database.py             engine dan session SQLAlchemy
│   │   ├── models.py               application persistence models
│   │   ├── security.py             password hashing dan signed token
│   │   └── services/
│   │       ├── log_store.py         query log dan optional indexing
│   │       ├── retrieval.py         BM25, semantic, fusion, bundle
│   │       └── llm.py               Ollama dan safe fallback
│   ├── alembic/                     baseline migration
│   ├── tests/                       API dan retrieval tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                         Next.js App Router pages
│   ├── components/
│   │   ├── AppShell.tsx             sidebar, header, auth boundary
│   │   ├── LogWorkspace.tsx         live operations/log explorer
│   │   └── AssistantPanel.tsx       chat, RCA, evidence inspector
│   ├── lib/api.ts                   API client dan session refresh
│   ├── next.config.ts               API proxy dan security headers
│   ├── Dockerfile
│   └── package.json
├── data/                             synthetic logs/incidents/truth
├── scripts/
│   ├── dev.mjs                       one-command orchestrator
│   ├── test.mjs                      combined verification
│   └── generate_synthetic_data.py    deterministic data generator
├── docker-compose.yml
├── .env.example
├── package.json                      root commands
└── PRD — 5G RCA.md
```

Generated directories seperti `.next`, `.venv`, `node_modules`, `.uv-cache`, database SQLite, dan runtime log tidak disimpan dalam Git.

## 5. Frontend

### Halaman

| Route | Fungsi |
|---|---|
| `/login` | Login email/password dan demo credential |
| `/operations` | Monitoring, summary card, chart, live table, selection, AI panel |
| `/incidents` | Search/filter, detail drawer, pembuatan incident, dan perubahan status |
| `/logs` | Log Explorer dalam search mode tanpa live stream |
| `/datasets` | Upload, validasi, preview status, dan indexing dataset |
| `/evaluation` | Menjalankan benchmark retrieval terhadap ground truth |
| `/system` | Status backend, database, OpenSearch, embedding, dan Ollama |
| `/users` | Daftar user untuk ADMIN |

`AppShell` membaca session user, melakukan route guard client-side, membangun navigasi berdasarkan role, dan merevoke refresh token ketika logout.

`LogWorkspace` dipakai oleh Operations dan Log Explorer. Perbedaan mode dijaga melalui prop `explorer`: Operations membuka SSE sedangkan Explorer fokus pada pencarian historis. Keyword search memiliki debounce 350 ms, filter change membersihkan selection agar konteks tidak stale, dan error API tampil sebagai banner dengan Retry. Selection toolbar menjalankan tiga aksi nyata: Analyze with AI, Related Logs, dan Create Incident. Aksi yang sama tersedia dari log detail drawer.

`AssistantPanel` mengirim selected log IDs, selected nodes, severity, dan keyword sebagai `ui_context`. Hasil menampilkan summary, likely root cause, affected components, reasoning, evidence, recommendation, retrieval detail, serta grouped bar chart BM25/Semantic/Final score. Evidence dapat diklik untuk membuka drawer raw JSON. Panel menggunakan scroll container tersendiri sehingga hasil panjang tidak menggeser viewport utama ke bawah.

Dropdown Operations, Incidents, Users, dan Evaluation memiliki pilihan eksplisit serta empty/loading option yang sesuai konteks. Badge Incidents mengambil jumlah incident aktif dari API dan diperbarui setelah create/status update.

### Session client

Access dan refresh token disimpan pada `sessionStorage`, bukan persistent `localStorage`. API client:

1. menambahkan bearer token;
2. ketika menerima `401`, mencoba refresh satu kali;
3. menggabungkan concurrent refresh melalui satu promise;
4. mengulang request asli;
5. membersihkan session dan kembali ke login jika refresh gagal.

Session storage mengurangi durasi token tersimpan, tetapi tetap dapat dibaca JavaScript. Production sebaiknya memindahkan refresh token ke cookie `HttpOnly`, `Secure`, dan `SameSite`.

### UI dan accessibility

Desain menggunakan dark observability theme, status color, dense log table, responsive cards, dan evidence-focused assistant. Perbaikan audit yang sudah diterapkan:

- AI panel dapat dibuka pada tablet/mobile;
- Log Explorer mempunyai title dan behavior berbeda;
- focus-visible outline untuk keyboard;
- aria-label pada control penting;
- reduced-motion support;
- empty, loading, dan error state;
- font eksternal dihapus agar startup tidak bergantung internet;
- ukuran teks tabel dan badge dinaikkan;
- keyword request diberi debounce.
- notification popover, refresh, create/update, upload/index/delete, dan evaluation controls terhubung ke handler API;
- AI output panjang tetap berada di dalam scroll area assistant.

Keterbatasan UI yang tersisa: tabel belum memakai true row virtualization, incident detail belum mempunyai seluruh tab PRD, Users belum menyediakan form edit lengkap, dan mobile layout belum diuji pada seluruh kombinasi browser/device nyata.

## 6. Backend dan API

FastAPI menggunakan lifespan startup untuk memuat dataset, membuat schema jika belum ada, seed demo, dan mencoba inisialisasi OpenSearch pada background thread.

### Endpoint groups

| Group | Endpoint utama |
|---|---|
| Authentication | `POST /api/auth/login`, `/refresh`, `/logout`, `GET /me` |
| Users | `GET/POST /api/users`, `PATCH/DELETE /api/users/{id}` |
| Logs | `GET /api/logs`, `/api/logs/{id}`, stream ticket, SSE, related search |
| Incidents | `GET/POST /api/incidents`, `GET/PATCH /api/incidents/{id}` |
| Datasets | list, multipart upload, index, delete |
| Conversations | create, detail/history, add message |
| Analysis | retrieve, run, result, expand evidence, SSE progress |
| Evaluation | run, list, detail |
| Health | aggregate, database, OpenSearch, Ollama |

Swagger tersedia pada `/docs`.

### Persistence

Local development memakai `sqlite:///./rca_copilot.db`. Docker memakai PostgreSQL dari `DATABASE_URL`.

Model penting:

- `User`, `RefreshToken`;
- `Dataset`;
- `Incident`, `IncidentNode`, `IncidentMetadata`;
- `Conversation`, `Message`;
- `Analysis`, `AnalysisEvidence`;
- `EvaluationRun`, `GroundTruth`;
- `AuditLog`.

Prototype menyimpan `result_json`, `evidence_json`, dan `ui_context` langsung pada `Analysis`. Ini menyederhanakan demo, tetapi berbeda dari normalisasi penuh PRD (`analysis_results` dan `analysis_context` terpisah). Uploaded dataset sementara diserialisasi melalui record Dataset; production perlu object storage/staging table yang terpisah.

Alembic menyediakan baseline `0001_initial`. Startup juga memanggil `create_all` agar demo kosong langsung dapat dipakai. Pada production, migration harus menjadi satu-satunya mekanisme perubahan schema.

## 7. Hybrid retrieval dan RCA

Pipeline berada pada `backend/app/services/retrieval.py`:

```text
Question + UI context
  → timestamp/node/severity/trace/session candidate filtering
  → tokenization
  → BM25 score
  → deterministic semantic feature-hashing vector + cosine similarity
  → per-channel min-max normalization
  → alpha-weighted score fusion
  → selected-log boost
  → rank, deduplication, Top-K
  → chronological ordered context
  → EvidenceBundle
```

Rumus fusion:

```text
final = alpha × normalized_bm25 + (1 - alpha) × normalized_semantic
```

Default `alpha=0.5`, `top_k=10`, dan incident window ±5 menit. `Search More Evidence` menggunakan Top-20 serta window ±15 menit.

Semantic fallback `feature-hashing-v1` bersifat deterministic, ringan, dan tidak memerlukan download model; ia bukan Sentence Transformer. `log_store.py` dapat membuat index dan mengirim vector ke OpenSearch, tetapi jalur ranking aktif saat ini tetap dilakukan in-process. Untuk memenuhi arsitektur production PRD secara penuh, BM25 harus dijalankan oleh OpenSearch dan semantic query harus menggunakan embedding Sentence Transformer yang sama dengan ingestion.

`llm.py` memanggil Ollama `/api/chat` dengan structured JSON prompt. Jika runtime tidak tersedia atau output invalid, deterministic mock-safe provider menghasilkan RCA berbasis evidence. Semua `evidence_ids` divalidasi terhadap bundle; ID di luar bundle dibuang dan fallback aman dipakai apabila tidak tersisa citation valid.

## 8. Synthetic data dan evaluation

Generator bersifat deterministic (`random.seed(42)`) dan menghasilkan 400 record dengan mayoritas noise normal. Tiga scenario:

1. PFCP association degradation → timeout SMF → PDU session failure;
2. AMF control-plane timeout → retry → UE registration failure;
3. UPF packet drop → QoS degradation → user-plane failure.

Ground truth menghubungkan tiap incident dengan relevant log IDs. Evaluation Lab menghitung Precision@K, Recall@K, Hit Rate@K, MRR, context precision/recall, dan retrieval latency pada tiga scenario tersebut. Sampel ini cukup untuk demo, tetapi terlalu kecil untuk klaim performa akademik yang kuat; eksperimen final perlu dataset, query, dan annotator yang lebih beragam.

## 9. Security review

### Sudah diterapkan

- PBKDF2-HMAC-SHA256 dengan random salt dan 210.000 iteration;
- signed token dengan expiration dan type (`access`, `refresh`, `stream`);
- refresh token hanya disimpan sebagai SHA-256 hash di database dan dapat direvoke;
- login rate limit in-memory: 8 kegagalan per IP per menit;
- dummy password verification untuk mengurangi user enumeration berbasis timing;
- ADMIN dependency untuk user management dan delete dataset;
- input length, enum, upload size, record count, timestamp, severity, dan field validation;
- maximum upload 10 MB dan 50.000 record;
- short-lived 60-second SSE ticket agar access token tidak muncul di URL/access log;
- security headers: no-sniff, frame deny, no-referrer, restricted permissions dan CSP baseline;
- no-store untuk API response;
- default launcher bind localhost; LAN exposure harus eksplisit;
- Docker backend dan OpenSearch bind ke host loopback;
- startup menolak default JWT secret dan demo seed pada `APP_ENV=production`;
- `.env`, runtime log, database, cache, dan build artifact di-ignore.

### Risiko tersisa sebelum production

1. Token masih berada di browser JavaScript storage; gunakan HttpOnly cookie atau BFF session.
2. Rate limit hanya memory per process; gunakan Redis/API gateway untuk multi-instance.
3. Belum ada CSRF design untuk future cookie authentication.
4. OpenSearch Docker menonaktifkan security plugin pada development profile.
5. Belum ada malware/content scanning untuk upload.
6. Belum ada secret manager, key rotation, MFA, SSO, atau password reset workflow.
7. Audit log belum immutable dan belum mempunyai retention/export policy.
8. Endpoint health mengungkap status komponen; batasi pada private network untuk production.
9. Dependency audit perlu dijalankan berkala pada environment dengan network dan ruang disk memadai.
10. LLM prompt-injection resistance masih mengandalkan evidence-only system prompt; production perlu sanitization, policy tests, dan output schema enforcement yang lebih ketat.

Audit dependency terakhir setelah upgrade Next.js 16.3.0 menghasilkan **0 vulnerability** untuk production dependencies (`npm audit --omit=dev`). Audit tetap harus diulang pada CI karena advisory dapat berubah setelah dokumen ini dibuat.

## 10. Usability dan reliability review

### Kekuatan

- demo flow jelas dari login sampai raw evidence;
- informasi retrieval tidak disembunyikan dari analyst;
- filter dan selected log masuk ke konteks AI;
- fallback menjaga aplikasi tetap berguna tanpa infrastructure berat;
- satu command mengurangi setup error;
- backend tests dan production frontend build tersedia dalam satu command.

### Prioritas perbaikan berikutnya

| Prioritas | Area | Rekomendasi |
|---|---|---|
| P0 | Retrieval fidelity | Jalankan BM25/k-NN aktual di OpenSearch dan Sentence Transformer ingestion |
| P0 | Production auth | HttpOnly session, distributed rate limit, secret manager |
| P1 | Log scale | Server pagination + TanStack virtualized table |
| P1 | Data ingestion | Staging storage, mapping UI, async worker, per-row error report |
| P1 | Incident UX | Detail route dan Investigation/Logs/Evidence/History tabs |
| P1 | Tests | Browser E2E untuk login → select → analyze → evidence |
| P2 | Accessibility | Automated axe audit dan manual screen-reader/keyboard test |
| P2 | Observability | Structured application logs, metrics, trace IDs, health retry |
| P2 | Evaluation | Larger benchmark, confidence interval, configuration comparison chart |

## 11. Configuration

`.env.example` mendokumentasikan database, JWT, OpenSearch, embedding, retrieval, Ollama, polling, demo seed, dan CORS. Untuk local one-command launcher, salin `.env.local.example` menjadi `.env.local`; `scripts/dev.mjs` akan membacanya untuk backend. Langkah SQLite/PostgreSQL/Ollama lengkap tersedia di `DATABASE_AND_AI_SETUP.md`.

Production minimum:

```env
APP_ENV=production
JWT_SECRET=<random secret minimum 32 bytes>
SEED_DEMO_USERS=false
DATABASE_URL=<managed PostgreSQL URL>
CORS_ORIGINS=https://dashboard.example.com
```

Jangan commit `.env`. Jangan mengaktifkan credential demo atau synthetic admin pada internet-facing deployment.

## 12. Testing dan quality gate

Jalankan seluruh verification:

```powershell
npm test
```

Perintah ini menjalankan:

1. `pytest -q` untuk API login/log/analysis, evidence validation, stream ticket, PFCP ranking, context filtering, Related Logs, create/update Incident, create/update User, indexing Dataset, dan Evaluation;
2. `next build` untuk TypeScript checking dan optimized production compilation.

Test backend memakai SQLite in-memory melalui `tests/conftest.py`, sehingga tidak membaca atau memodifikasi database development.

Manual smoke test yang direkomendasikan:

1. login sebagai ADMIN dan ANALYST;
2. filter `SMF-01`, search `PFCP`, pilih log;
3. jalankan RCA dan buka evidence;
4. buka retrieval detail dan expand evidence;
5. upload file valid/invalid;
6. run Evaluation Lab;
7. uji session expiry dan logout;
8. uji ukuran desktop, tablet, dan mobile;
9. verifikasi ANALYST tidak dapat membuka API ADMIN;
10. pastikan runtime log tidak berisi password, access token, atau refresh token.

## 13. Deployment guidance

Docker Compose adalah profil development/integration, bukan template internet production. Production membutuhkan TLS reverse proxy, restricted network, authenticated OpenSearch, managed database, secret manager, backup, monitoring, and resource limits. Jalankan frontend sebagai satu-satunya public service; backend, database, OpenSearch, dan Ollama berada pada private network.

## 14. Kesimpulan audit

Aplikasi sudah mempunyai jalur demo yang koheren, visual yang sesuai domain observability, evidence traceability, fallback yang praktis, dan sekarang dapat dijalankan dari root dengan satu perintah. Perbaikan audit menutup risiko token SSE di access log, memperbaiki lifecycle session, input validation, secure defaults, mobile AI access, dan error feedback.

Risiko terbesar bukan pada kelancaran demo, melainkan pada perbedaan antara fallback penelitian lokal dan arsitektur retrieval production yang dijanjikan PRD. Prioritas teknis selanjutnya adalah mengganti ranking in-process dengan OpenSearch BM25/k-NN dan embedding Sentence Transformer aktual, kemudian menguatkan session/auth untuk deployment multi-user.
