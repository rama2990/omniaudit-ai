# Deploy ke Google Cloud Run

Aplikasi jalan sebagai **satu container** (lihat `Dockerfile`): FastAPI menyajikan API sekaligus frontend.

Catatan penting soal data:
- Database SQLite ada di `/tmp/data` (`OMNI_DATA`), yaitu memori instance. Data **hilang** setiap kali instance baru menyala.
- Seed (termasuk OCR PDF hasil scan) sudah dijalankan saat **build image**, jadi cold start cepat dan setiap instance baru mulai dari data demo yang sama.
- Saat build belum ada `GEMINI_API_KEY`, jadi 5 item antrean AP awalnya terbaca pola teks lokal. Begitu instance menyala dengan key, item itu dibaca ulang dengan Gemini di background (sekitar 1 menit, 5 panggilan Gemini per instance baru; OCR tidak diulang). Kalau Gemini gagal, hasil pola teks lokal tetap dipakai. Hindari mengubah item antrean di menit pertama setelah deploy.
- Pakai `--min-instances=1 --max-instances=1` supaya semua request masuk ke satu instance dan data demo tetap konsisten selama presentasi. Konsekuensinya: 1 instance selalu menyala dan ditagih walau tidak ada trafik.

## 1. Persiapan (sekali saja)

Kebutuhan: [gcloud CLI](https://cloud.google.com/sdk/docs/install), project GCP dengan billing aktif.

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 2. Simpan `GEMINI_API_KEY` di Secret Manager

Ambil key dari https://aistudio.google.com/apikey, lalu:

```bash
printf %s "ISI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
```

Beri izin baca ke service account default Cloud Run (`PROJECT_NUMBER` lihat di `gcloud projects describe PROJECT_ID --format="value(projectNumber)"`):

```bash
gcloud secrets add-iam-policy-binding gemini-api-key --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

Ganti key nanti: `printf %s "KEY_BARU" | gcloud secrets versions add gemini-api-key --data-file=-`, lalu deploy ulang.

## 3. Deploy

Dari root repo (Cloud Build membangun `Dockerfile`, tidak perlu Docker lokal):

```bash
gcloud run deploy omniaudit --source . --region asia-southeast2 --allow-unauthenticated --memory 2Gi --cpu 2 --min-instances 1 --max-instances 1 --timeout 300 --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

- `--memory 2Gi`: OCR (RapidOCR/onnxruntime) butuh memori lebih dari default 512Mi.
- `--allow-unauthenticated`: URL bisa dibuka siapa saja yang tahu link-nya. Hapus flag ini kalau demo cukup untuk akun Google tertentu.
- Tanpa `--set-secrets`, aplikasi tetap jalan dalam mode offline (ekstraksi pola teks lokal).

URL layanan muncul di akhir output. Cek mode AI di `URL/api/meta` (`"mode"` harus `gemini`).

**Reset data demo:** deploy ulang, atau paksa instance baru dengan `gcloud run services update omniaudit --region asia-southeast2 --update-env-vars RESET=$(date +%s)`.

## 4. Opsi: pindah ke Vertex AI

Dengan Vertex AI, tidak perlu API key; akses lewat service account, dan tagihan masuk ke project GCP.

```bash
gcloud services enable aiplatform.googleapis.com
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"
gcloud run services update omniaudit --region asia-southeast2 --remove-secrets GEMINI_API_KEY --update-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=PROJECT_ID,GOOGLE_CLOUD_LOCATION=asia-southeast2,GEMINI_MODEL=gemini-2.5-flash
```

- `GEMINI_MODEL` diisi nama model tetap, karena alias `gemini-flash-latest` belum tentu tersedia di Vertex.
- Kalau model tidak tersedia di `asia-southeast2` (Jakarta), pakai `GOOGLE_CLOUD_LOCATION=global`, dengan catatan data tidak lagi dijamin diproses di Jakarta.

## Uji image secara lokal (butuh Docker)

```bash
docker build -t omniaudit .
docker run --rm -p 8080:8080 -e GEMINI_API_KEY=ISI_API_KEY omniaudit
```

Buka http://localhost:8080.
