# Deploy ke Google Cloud Run

Aplikasi jalan sebagai **satu container** (lihat `Dockerfile`): FastAPI menyajikan API sekaligus frontend.

Catatan penting soal data:
- Database SQLite ada di `/tmp/data` (`OMNI_DATA`), yaitu memori instance. Data **hilang** setiap kali instance baru menyala.
- Seed (termasuk OCR PDF hasil scan) sudah dijalankan saat **build image**, jadi cold start cepat dan setiap instance baru mulai dari data demo yang sama.
- Saat build belum ada akses Gemini, jadi 5 item antrean AP awalnya terbaca pola teks lokal. Begitu instance menyala dengan Gemini aktif, item itu dibaca ulang dengan Gemini di background (sekitar 1 menit, 5 panggilan Gemini per instance baru; OCR tidak diulang). Kalau Gemini gagal, hasil pola teks lokal tetap dipakai. Hindari mengubah item antrean di menit pertama setelah deploy.
- Pakai `--min-instances=1 --max-instances=1` supaya semua request masuk ke satu instance dan data demo tetap konsisten selama presentasi. Konsekuensinya: 1 instance selalu menyala dan ditagih walau tidak ada trafik.

## 1. Persiapan (sekali saja)

Kebutuhan: [gcloud CLI](https://cloud.google.com/sdk/docs/install), project GCP dengan billing aktif.

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
```

## 2. Akses Gemini lewat Vertex AI

Cloud Run memanggil Gemini di Vertex AI memakai service account-nya sendiri, jadi tidak ada API key di server. Biaya masuk ke billing project GCP. Beri izin ke service account default Cloud Run (`PROJECT_NUMBER` lihat di `gcloud projects describe PROJECT_ID --format="value(projectNumber)"`):

```bash
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"
```

Pilihan model dan lokasi (dites 2026-10-18 pada 7 PDF demo, `scripts/gemini_check.py`):
- `gemini-2.5-flash` di lokasi `global`: 98/98 field cocok, sekitar 10 detik per dokumen. **Dipakai.**
- `gemini-2.5-flash-lite`: 96/98, sekitar 3 detik, tetapi salah membaca total tagihan di skenario F (nominal digelembungkan). Tidak dipakai.
- Lokasi `asia-southeast2` (Jakarta) menolak model ini, jadi pakai `global`. Artinya data tidak dijamin diproses di Jakarta.

## 3. Deploy

Dari root repo (Cloud Build membangun `Dockerfile`, tidak perlu Docker lokal):

```bash
gcloud run deploy omniaudit --source . --region asia-southeast2 --allow-unauthenticated --memory 2Gi --cpu 2 --min-instances 1 --max-instances 1 --timeout 300 --update-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-2.5-flash
```

- `--memory 2Gi`: OCR (RapidOCR/onnxruntime) butuh memori lebih dari default 512Mi.
- `--allow-unauthenticated`: URL bisa dibuka siapa saja yang tahu link-nya. Hapus flag ini kalau demo cukup untuk akun Google tertentu.
- Tanpa env Vertex di atas (dan tanpa API key), aplikasi tetap jalan dalam mode offline (ekstraksi pola teks lokal).

URL layanan muncul di akhir output. Cek mode AI di `URL/api/meta` (`"mode"` harus `gemini`, `"model"` harus `gemini-2.5-flash`).

**Reset data demo:** deploy ulang, atau paksa instance baru dengan `gcloud run services update omniaudit --region asia-southeast2 --update-env-vars RESET=$(date +%s)`.

## 4. Menjalankan lokal dengan Vertex AI

Buat API key di Google Cloud console (Agent Platform, Settings, API Keys), lalu di `backend/.env`:

```
GEMINI_API_KEY=API_KEY_VERTEX
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_GENAI_USE_VERTEXAI=true
```

Jangan isi `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` bersama API key: SDK akan beralih ke login gcloud (ADC). API key Vertex hanya untuk lokal; di Cloud Run tidak perlu.

## 5. Opsi: API key Google AI Studio

Kalau tidak memakai Vertex, simpan key AI Studio di Secret Manager dan pasang sebagai `GEMINI_API_KEY`. Free tier punya kuota harian kecil (habis setelah sekitar 60 dokumen pada 2026-10-18), jadi tidak disarankan untuk demo.

```bash
gcloud services enable secretmanager.googleapis.com
printf %s "ISI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
gcloud secrets add-iam-policy-binding gemini-api-key --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
gcloud run services update omniaudit --region asia-southeast2 --remove-env-vars GOOGLE_GENAI_USE_VERTEXAI,GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

## Uji image secara lokal (butuh Docker)

```bash
docker build -t omniaudit .
docker run --rm -p 8080:8080 -e GEMINI_API_KEY=API_KEY_VERTEX -e GOOGLE_GENAI_USE_VERTEXAI=true -e GEMINI_MODEL=gemini-2.5-flash omniaudit
```

Buka http://localhost:8080.
