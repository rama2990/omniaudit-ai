# Draft submission hackathon: OmniAudit AI

## Pitch Deck

https://claude.ai/artifact/QRJ6jQud3em5jUKGaQrLJk

- 12 slide, bahasa Indonesia, lengkap dengan catatan pembicara.
- Link ini masih **privat**. Buka link-nya, lalu bagikan lewat menu **Share** supaya juri bisa membuka.
- Kalau formulir meminta file, unduh dari menu **Export** sebagai PDF.
- Sebelum submit, isi placeholder `[Nama tim]`, `[Nama hackathon]`, dan `[anggota tim]`.

## Deployed Prototype Link

https://omniaudit-648878449957.asia-southeast2.run.app

Tanpa login. Persona dan SPV dipilih di kanan atas.

## GitHub Repository

https://github.com/rama2990/omniaudit-ai

## Brief description

### Bahasa Indonesia, versi pendek (±60 kata)

OmniAudit AI adalah dasbor audit untuk developer properti multi-SPV. Gemini membaca invoice, BAP, faktur pajak, dan rekening koran. Kode deterministik menghitung PPN, PPh 4(2), retensi, uang muka, denda, dan jurnal. Manusia memutuskan. Hasilnya: overbilling kontraktor terkunci sebelum dibayar, transfer pembeli otomatis cocok ke unitnya, dan setiap keputusan tercatat di jejak audit yang tidak bisa diubah diam-diam.

### Bahasa Indonesia, versi panjang (±160 kata)

Developer properti dengan banyak SPV kehilangan uang di dua arah:
- **Uang keluar:** kontraktor menagih progres melebihi BAP fisik, dan retensi, denda, atau potongan uang muka lupa dipotong.
- **Uang masuk:** transfer pembeli menggantung karena kode unit dan nama pengirim tidak cocok.

OmniAudit AI membagi kerja dengan tegas:
- **Gemini** mengklasifikasi dan membaca dokumen. Setiap angka wajib menunjuk ke kata di dokumen asli, sehingga nilai karangan otomatis ditolak.
- **Kode deterministik** menghitung semua uang sesuai aturan pajak konstruksi Indonesia (PP 9/2022, DPP Nilai Lain 11/12), lalu menjalankan delapan pemeriksaan anomali, misalnya overbilling dan tagihan ganda lintas SPV.
- **Auditor** meninjau di layar split-view, dengan PDF yang disorot di samping perbandingan klaim dan hasil verifikasi.
- **CFO** memutuskan kasus di atas Rp500 juta.

Di sisi AR, match score (kode unit, nama, nominal) mencocokkan transfer ke unit, menghitung denda angsuran, dan mengirim kuitansi ke pembeli.

Prototipe berjalan di Google Cloud Run dengan OCR lokal. Ada 74 tes otomatis dan simulasi satu minggu kerja dengan 15 skenario, semuanya sesuai harapan.

### English, short (~60 words)

OmniAudit AI is an audit dashboard for multi-entity property developers. Gemini reads contractor invoices, inspection reports, tax invoices and bank statements; deterministic code computes VAT, construction withholding tax, retention, down-payment recoupment, late penalties and balanced journals; humans decide. Contractor overbilling is locked before payment, buyer transfers are matched to their units, and every decision lands in a tamper-evident audit trail.

### English, long (~160 words)

Property developers running many project companies (SPVs) leak money in both directions:
- **Outgoing:** contractors bill progress beyond the physical inspection report, and retention, late penalties or down-payment recoupment get missed.
- **Incoming:** buyer transfers sit unallocated because unit codes and payer names do not match.

OmniAudit AI splits the work clearly:
- **Gemini** classifies pages and extracts fields. Every value must point to a word in the original document, so invented values are rejected.
- **Deterministic code** computes all money under Indonesian construction tax rules and runs eight anomaly checks, including overbilling and duplicate invoices across SPVs.
- **Auditors** review in a split view that highlights the source PDF next to the claimed-versus-verified comparison.
- **The CFO** approves anything above IDR 500 million.

On the receivables side, a match score (unit code, name, amount) assigns transfers to units, computes installment penalties and sends receipts to buyers.

The prototype runs on Google Cloud Run with local OCR. It has 74 automated tests and a one-week simulation of 15 scenarios, all matching expectations.
