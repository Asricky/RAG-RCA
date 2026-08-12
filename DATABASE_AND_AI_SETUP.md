# Database dan AI Model Setup

Panduan ini menjelaskan tiga cara menjalankan database serta cara menghubungkan Ollama ke 5G RCA Copilot.

## 1. Konfigurasi local development

`npm run dev` membaca konfigurasi opsional dari file `.env.local` di root repository. File tersebut tidak disimpan ke Git.

```powershell
Copy-Item .env.local.example .env.local
```

Setelah mengubah konfigurasi, restart aplikasi dengan `Ctrl+C`, kemudian:

```powershell
npm run dev
```

## 2. Pilihan database

### Opsi A — SQLite bawaan

Ini pilihan termudah untuk development dan demo. Tidak diperlukan service database terpisah.

`.env.local`:

```env
DATABASE_URL=sqlite:///./rca_copilot.db
```

Database dibuat di `backend/rca_copilot.db`. Pada startup pertama, aplikasi membuat schema dan synthetic demo seed secara otomatis.

Gunakan SQLite hanya untuk single-user development. SQLite tidak disarankan untuk deployment multi-user atau workload paralel.

### Opsi B — PostgreSQL melalui Docker

Jalankan PostgreSQL dan, bila diperlukan, OpenSearch:

```powershell
docker compose up -d postgres opensearch
```

Gunakan koneksi host pada `.env.local`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/rca_copilot
OPENSEARCH_URL=http://127.0.0.1:9200
```

Kemudian jalankan frontend dan backend lokal:

```powershell
npm run dev
```

PostgreSQL dipublikasikan hanya pada `127.0.0.1:5432`, sehingga tidak dapat diakses langsung oleh perangkat lain pada LAN.

### Opsi C — PostgreSQL eksternal

Buat database kosong dan user dengan hak akses schema. Contoh SQL:

```sql
CREATE USER rca_app WITH PASSWORD 'replace-this-password';
CREATE DATABASE rca_copilot OWNER rca_app;
GRANT ALL PRIVILEGES ON DATABASE rca_copilot TO rca_app;
```

Isi `.env.local`:

```env
DATABASE_URL=postgresql+psycopg://rca_app:URL_ENCODED_PASSWORD@database-host:5432/rca_copilot
```

Jika password mengandung karakter khusus seperti `@`, `:`, `/`, atau `#`, lakukan URL encoding.

### Menjalankan migration

Startup development dapat membuat schema kosong secara otomatis. Untuk workflow migration eksplisit:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Untuk mengecek koneksi:

```powershell
Invoke-RestMethod http://localhost:8000/api/health/database
```

Response yang diharapkan:

```json
{"status":"Healthy"}
```

### Reset data development

- SQLite: hentikan aplikasi, pindahkan atau hapus `backend/rca_copilot.db`, lalu jalankan kembali. Ini menghapus seluruh user, conversation, analysis, dan incident lokal.
- Docker PostgreSQL: `docker compose down -v` menghapus volume database dan OpenSearch secara permanen. Gunakan hanya jika memang ingin reset total.

Selalu buat backup sebelum menghapus database yang berisi data penting.

## 3. Menghubungkan model AI melalui Ollama

### Instal dan siapkan model

Install Ollama dari situs resminya, kemudian:

```powershell
ollama pull llama3.2:3b
ollama serve
```

Pada sebagian instalasi Windows, service Ollama sudah berjalan otomatis. Periksa dengan:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

### Konfigurasi aplikasi lokal

`.env.local`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
```

Restart `npm run dev`, login, lalu buka **System**. Service `ollama` harus menunjukkan `Healthy` beserta nama model.

Model lain dapat digunakan selama tersedia di Ollama:

```powershell
ollama pull qwen2.5:7b
```

```env
OLLAMA_MODEL=qwen2.5:7b
```

Model yang lebih besar biasanya memberi reasoning lebih baik, tetapi membutuhkan RAM/VRAM lebih besar dan response lebih lambat.

### Konfigurasi Ollama untuk backend Docker

Pada `.env` yang dipakai Docker Compose:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:3b
```

Kemudian:

```powershell
docker compose up --build
```

### Mode fallback tanpa model

Untuk demo tanpa Ollama:

```env
LLM_PROVIDER=mock
```

Mock provider tetap menghasilkan RCA deterministik berbasis evidence. Mode ini cocok untuk UI development dan automated test, bukan evaluasi kualitas LLM.

## 4. Embedding dan OpenSearch

Local default:

```env
OPENSEARCH_URL=http://127.0.0.1:9200
OPENSEARCH_INDEX=5g-logs-st-v1
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=32
```

Backend memuat model Sentence Transformer secara lazy, memvalidasi dimensi output, membuat normalized document embeddings, lalu menyimpannya pada field `knn_vector` OpenSearch. Query RCA menjalankan `multi_match` OpenSearch untuk BM25 dan HNSW kNN menggunakan query embedding dari model yang sama. Kedua skor dinormalisasi lalu digabungkan memakai `DEFAULT_ALPHA`.

Model pertama kali akan diunduh dari Hugging Face. Pastikan koneksi internet tersedia pada startup pertama. Cache model digunakan kembali pada startup berikutnya.

OpenSearch dapat dinyalakan dengan:

```powershell
docker compose up -d opensearch
```

Periksa:

```powershell
Invoke-RestMethod http://127.0.0.1:9200/_cluster/health
Invoke-RestMethod http://localhost:8000/api/health/opensearch
```

Backend membuat index `5g-logs-st-v1`, menghasilkan embedding untuk synthetic documents, dan melakukan bulk indexing pada startup. Periksa encoder melalui:

```powershell
Invoke-RestMethod http://localhost:8000/api/health/embedding
```

Tidak ada in-memory semantic fallback pada runtime development/production. Analyze with AI dan Evaluation mengembalikan HTTP `503` bila OpenSearch, index, atau Sentence Transformer belum siap. Log table tetap dapat dibuka karena source JSONL lokal masih dipakai untuk live display.

Jika mengganti `EMBEDDING_MODEL`, sesuaikan `EMBEDDING_DIMENSION` dan gunakan nama `OPENSEARCH_INDEX` baru agar vector dari model berbeda tidak tercampur.

## 5. Variabel penting

| Variable | Contoh | Fungsi |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` | Koneksi database aplikasi |
| `JWT_SECRET` | random minimum 32 karakter | Signature access/refresh token |
| `OPENSEARCH_URL` | `http://127.0.0.1:9200` | Endpoint log store |
| `OPENSEARCH_INDEX` | `5g-logs-st-v1` | Nama index log/vector |
| `OPENSEARCH_TIMEOUT_SECONDS` | `30` | Timeout request OpenSearch |
| `LLM_PROVIDER` | `ollama` atau `mock` | Adapter RCA |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Endpoint Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model generation |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Model embedding query dan dokumen |
| `EMBEDDING_DIMENSION` | `384` | Dimensi `knn_vector`; harus cocok dengan model |
| `EMBEDDING_DEVICE` | `cpu` | Device inference (`cpu`, `cuda`, atau `mps`) |
| `EMBEDDING_BATCH_SIZE` | `32` | Batch size saat indexing |
| `DEFAULT_ALPHA` | `0.5` | Bobot BM25 dalam score fusion |
| `DEFAULT_TOP_K` | `10` | Jumlah evidence default |

Jangan commit `.env`, `.env.local`, password database, atau JWT secret.

## 6. Troubleshooting

### Database unavailable

- pastikan container/service PostgreSQL berjalan;
- periksa host dan port pada `DATABASE_URL`;
- untuk backend lokal gunakan `127.0.0.1`, bukan hostname Docker `postgres`;
- pastikan database dan user sudah dibuat;
- periksa firewall dan SSL requirement provider database.

### Ollama unavailable

- jalankan `ollama serve`;
- pastikan `ollama list` menampilkan model yang dikonfigurasi;
- cek `/api/tags` pada port `11434`;
- jika backend berada di Docker, gunakan `host.docker.internal`, bukan `127.0.0.1`;
- restart aplikasi setelah mengubah `.env.local`.

### OpenSearch retrieval belum siap

- pastikan Docker Desktop aktif, lalu jalankan `docker compose up -d opensearch`;
- cek `/api/health/opensearch` dan `/api/health/embedding` untuk detail error;
- tunggu status `Healthy` setelah download model dan bulk indexing pertama;
- bila index tidak kompatibel, gunakan nama `OPENSEARCH_INDEX` baru atau recreate hanya index development tersebut;
- pastikan model dapat diunduh dari Hugging Face pada startup pertama.

### AI masih memakai mock

Response analysis mempunyai field `provider`. Nilai `ollama` berarti model aktif. Nilai `mock` atau `mock-safe-fallback` berarti Ollama tidak dapat dihubungi atau output model gagal memenuhi evidence validation.
