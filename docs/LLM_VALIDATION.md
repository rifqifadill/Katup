# Hasil verifikasi branch llm

Dokumen ini mencatat snapshot awal sebelum empat koridor regional ditambahkan. Hasil versi koridor UI, Akses UI, Pasar Rebo, dan TB Simatupang dicatat terpisah pada [REGIONAL_CORRIDORS.md](REGIONAL_CORRIDORS.md). Signature snapshot di bawah bukan signature kode regional terbaru.

Pengujian dilakukan pada 26 November 2026 dengan SUMO 1.18.0, langkah simulasi 1 detik dan durasi 1.800 detik per run. Provider LLM dinonaktifkan untuk seluruh perbandingan kinerja. Tidak ada pemanggilan API eksternal atau hasil model nyata pada tabel ini.

## Cakupan pengujian

- 12 run Pondok Pinang–Pondok Indah pada jam sibuk, seed 1, 2, 3, 42, masing-masing Baseline, Heuristik, dan Hybrid
- 6 run variasi arus lengang, lonjakan, dan bypass padat, seed 42, masing-masing Baseline dan Heuristik
- 2 run regresi koridor sintetik lama, seed 42, Baseline dan Heuristik
- 1 run integrasi supervisor dengan respons tiruan yang bergantian memilih keempat profil, menyisipkan JSON terlarang dan kegagalan API
- 3 run penuh melalui runner website, hasilnya cocok dengan evaluasi seed 42
- 11 tes otomatis untuk validasi strategi, fallback, respons provider tiruan, data CSV, API backend, origin, dan WebSocket
- Uji browser mulai/hentikan ketiga mode, perpindahan koridor, kendaraan benar-benar bergerak, serta layar 360, 390, 768, 1440 piksel
- Uji hasil selesai tiga mode dan penolakan hasil yang berbeda seed atau identitas sesi

Semua 20 run komparasi lolos konservasi kendaraan, tanpa tabrakan atau teleport. Urutan fase dan durasi kuning/semua-merah diperiksa pada setiap perubahan fase, program fixed-time baseline diperiksa setiap langkah. Run supervisor tiruan dan ketiga run website juga selesai tanpa tabrakan atau teleport. Jumlah kendaraan akhir memenuhi `tiba + aktif + tertahan = terjadwal`.

## Rata-rata empat seed pada koridor Jakarta

Arus jam sibuk berjumlah 1.590 kendaraan terjadwal selama 30 menit. Signature jaringan, demand, profil, dan kode kendali adalah `ad2a230fbe2d6805`. Ketiga mode menggunakan masukan dan seed yang berpasangan.

| Indikator | Tanpa KATUP | Heuristik | Hybrid tanpa API |
| --- | ---: | ---: | ---: |
| Trip selesai | 636,75 | 1.001,25 | 1.001,25 |
| Tunggu rata-rata trip selesai | 65,86 s | 32,77 s | 32,77 s |
| Total jam-kendaraan | 254,56 | 168,54 | 168,54 |
| Spillback | 1.145,50 s | 1.376,00 s | 1.376,00 s |
| Simpang terhambat | 257,75 s | 354,50 s | 354,50 s |
| Tabrakan / teleport | 0 / 0 | 0 / 0 | 0 / 0 |

Trip selesai bertambah sekitar **57,2%** dan total jam-kendaraan turun sekitar **33,8%**. Namun spillback bertambah sekitar **20,1%**, dan hambatan simpang bertambah sekitar **37,5%**. Jadi heuristik lama membantu arus keseluruhan, tetapi belum menyelesaikan perlindungan simpang pada geometri baru. Angka ini merupakan ringkasan empat percobaan, bukan jaminan untuk seluruh kondisi Jakarta.

Hybrid tanpa API identik dengan Heuristik pada setiap seed, bukan hanya pada rata-ratanya. Permintaan dan keputusan API sama-sama nol. Peningkatan di tabel tidak boleh disebut hasil kecerdasan LLM.

## Contoh hasil yang tampil pada dashboard

Seed 42 memberikan 642 trip selesai pada Baseline dan 972 pada Heuristik/Hybrid fallback. Spillback berubah dari 1.060 menjadi 1.332 detik, dan hambatan simpang dari 122 menjadi 501 detik. Dashboard menyebut kenaikan trip sekaligus pertambahan spillback dan hambatan, dengan penanda trade-off.

Nilai pada ketiga file hasil runner website dibandingkan dengan evaluator: trip selesai, total jam-kendaraan, kendaraan tertahan/aktif, spillback, dan hambatan simpang cocok. Waktu rata-rata disimpan runner dengan dua angka desimal. Tidak ada angka hasil yang ditulis manual ke dashboard.

Hasil hanya muncul setelah sesi selesai, minimal dua mode memiliki input yang cocok. Koridor, demand, signature, seed, versi SUMO, durasi penuh, dan identitas sesi diperiksa. Jika API Hybrid sudah dikonfigurasi, delay playback juga harus sama. Hasil dari jaringan lama tidak dicampur dengan jaringan geografis.

## Regresi dan variasi arus

| Kasus, seed 42 | Trip Baseline → Heuristik | Hambatan simpang Baseline → Heuristik |
| --- | ---: | ---: |
| Jakarta lengang | 367 → 544 | 147 → 220 s |
| Jakarta lonjakan | 771 → 1.095 | 459 → 452 s |
| Jakarta bypass padat | 667 → 975 | 446 → 0 s |
| Koridor sintetik lama, jam sibuk | 860 → 1.377 | 271 → 0 s |

Hasil lama yang sangat baik pada perlindungan simpang tidak otomatis berpindah ke koridor geografis. Perlu kalibrasi demand, pemeriksaan konflik gerakan, dan pengujian strategi lanjutan dengan data lapangan. Hasil variasi arus hanya menggunakan satu seed per kasus.

## Lokasi bukti dan reproduksi

- Ringkasan terstruktur: `deploy/evidence/llm-validation.json`
- Screenshot akhir: `deploy/evidence/llm-dashboard-desktop.png` dan `llm-dashboard-mobile.png`
- Hasil mentah lokal: `output/final-jakarta`, `output/final-stress`, `output/final-legacy`, `output/supervisor-fixture`, `output/browser`
- Hasil runner lokal yang dapat dibaca preview: `.runtime-llm/runs/jakarta_pondok_pinang-peak`

Direktori hasil mentah dan runtime diabaikan Git. Untuk membuatnya ulang, gunakan [panduan pengembangan](LLM_DEVELOPMENT.md) dan perintah berikut pada environment pengujian:

```bash
python tests/evaluate_hybrid.py --corridor jakarta_pondok_pinang --seeds 1 2 3 42 --output output/final-jakarta --without-api
python tests/evaluate_hybrid.py --corridor jakarta_pondok_pinang --demands light surge bypass_busy --seeds 42 --modes baseline katup --output output/final-stress --without-api
python tests/evaluate_hybrid.py --corridor galian_berat --seeds 42 --modes baseline katup --output output/final-legacy --without-api
python tests/verify_supervisor_sumo.py
```

API nyata belum diuji, data observasi mingguan belum tersedia, dan demand belum dikalibrasi terhadap pengukuran Jakarta. Efektivitas Hybrid perlu dibandingkan kembali setelah API dihubungkan, termasuk jumlah saran yang benar-benar diterapkan, latency, token, kegagalan, serta metrik lalu lintasnya.
