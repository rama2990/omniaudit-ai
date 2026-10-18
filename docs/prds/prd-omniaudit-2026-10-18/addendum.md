# Addendum PRD OmniAudit AI — catatan teknis

Isi di sini bukan requirement. Ini konteks untuk tahap desain dan arsitektur.

## Stack yang sudah diputuskan
- **Backend:** FastAPI (Python). Mesin kalkulasi dan aturan memakai `decimal.Decimal`.
- **Frontend:** React.
- **AI:** produk Google, yaitu Gemini. Untuk hackathon dipakai **Google AI Studio (API key)**. Kode memakai SDK `google-genai`, yang bisa dialihkan ke Vertex AI (region `asia-southeast2`) hanya dengan mengubah konfigurasi. Model juga disimpan di konfigurasi.
- **OCR lokal:** PyMuPDF untuk PDF digital (teks dan koordinat kata langsung tersedia). Untuk halaman hasil scan, Tesseract (`ind+eng`) atau PaddleOCR. Pilihannya ditentukan di tahap arsitektur. Kriteria: hasilnya bagus pada angka dan mudah dipasang di Windows.
- **Integrasi:** SSO, ERP, WhatsApp, email, dan webhook bank semuanya mock.

## Kenapa OCR lokal + Gemini (bukan Gemini membaca PDF langsung)
- Gemini tidak mengembalikan koordinat yang andal. Bounding box di split-view butuh koordinat kata yang presisi, dan OCR lokal menyediakannya.
- Pola "grounding": Gemini memilih nilai dari daftar kata OCR yang sudah diberi ID, misalnya `{"progres_bap": {"value": "75", "word_ids": ["p2_w118"], "confidence": 0.93}}`. Backend mengecek bahwa `word_ids` memang berisi nilai tersebut. Jika tidak cocok, keyakinan = 0. Inilah dasar FR-5 dan FR-6.
- Pakai *structured output* (JSON schema) Gemini supaya hasilnya bisa langsung divalidasi.

## Telemetry
Aliran langkah agen dikirim ke UI lewat Server-Sent Events (SSE). Setiap langkah adalah satu event `{agent, message, ts}`.

## Alternatif yang ditolak
- **Claude API untuk ekstraksi:** diganti karena ada syarat memakai produk Google.
- **Next.js satu aplikasi:** user memilih FastAPI + React.
- **LLM yang menghitung pajak/denda:** ditolak. Hasilnya tidak deterministik dan tidak bisa diaudit.
- **Full mock tanpa AI:** ditolak karena juri harus bisa melihat ekstraksi sungguhan.

## Data seed
PDF contoh dibuat oleh script (misalnya reportlab) supaya setiap skenario anomali bisa diulang. Beberapa halaman di-raster agar jalur OCR scan ikut teruji.
