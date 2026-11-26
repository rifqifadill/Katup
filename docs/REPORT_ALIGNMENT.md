# Penyelarasan laporan dengan branch llm

Acuan pemeriksaan adalah `KATUP_Reports_Chapter_1_to_5.docx` yang diberikan pada percakapan ini. Berkas laporan asli tidak diubah. Bab 1–5 menjelaskan generasi sistem terdahulu, sedangkan branch ini memisahkan koridor uji lama dan koridor geografis baru.

## Bagian yang perlu diperbarui sebelum dipresentasikan

| Isi laporan | Implementasi saat ini |
| --- | --- |
| Koridor dimodelkan dari kondisi Pondok Pinang | Skenario lama tetap sintetik, koridor baru benar-benar mengimpor geometri OSM Pondok Pinang–Pondok Indah, tetapi volume kendaraan, jadwal lampu, dan galian masih skenario eksperimen |
| Risiko pada 60% kapasitas atau kombinasi kecepatan rendah | `AgenPengamat.evaluate()` memakai antrean fisik: rasio hilir ≥55% atau antrean hulu ≥180 m |
| Kapasitas tetap 18 kendaraan | Kapasitas dihitung dari jumlah panjang lajur dibagi 7,5 m, bukan konstanta 18 untuk semua ruas |
| Pemulihan dua siklus | Hilir <20% panjang ruas dan antrean hulu <70 m selama 15 detik berturut-turut |
| Kendali hanya hidup setelah mode padat | Pada mode Heuristik dan Hybrid, Katup dan Rute tetap bekerja setiap langkah, status `KATUP_ACTIVE` menandai risiko, bukan satu-satunya syarat pengalihan |
| Pengalihan tetap 60% | Target kandidat 70%, 82%, atau 90% menurut jumlah kendaraan hilir, dibatasi biaya dan kapasitas rute |
| Pelepasan hijau tetap 25 detik | Heuristik memakai batas utama 30 detik saat antrean silang ada, Hybrid dapat memilih 20/30/35 detik, dengan minimum hijau serta proteksi hilir tetap berlaku |
| Seed 42, 100, 202, 303 di pembuka Bab 5 | Bagian lain menyebut 42, 101, 2024, 777, kedua daftar ini tidak konsisten, bukti branch ini menggunakan 1, 2, 3, 42 untuk jam sibuk dan seed 42 untuk variasi arus |
| Spillback/hambatan simpang menjadi nol | Ini dapat terjadi pada skenario lama tertentu, hasil koridor Jakarta baru tidak selalu nol dan tidak membaik pada semua indikator |
| Persentase perbaikan pada abstrak dan Bab 5 | Harus dikaitkan ke jaringan, demand, seed, versi SUMO, dan keluaran yang sama, tidak boleh dipindahkan ke Hybrid atau koridor baru |

## Rumus yang sesuai kode

- Antrean hilir `Q` adalah maksimum panjang kemacetan sensor E2 antar-lajur, rasio antrean `r = Q / panjang ruas hilir`
- Spillback dicatat ketika `r ≥ 0,90`, gerbang hilir menahan arus ketika `Q > 0,75 × panjang ruas`, setelah minimum hijau tercapai
- Rute tersedia jika jumlah kendaraan pada setiap ruas rute berada di bawah `0,8 × kapasitas ruas`, diperbarui setiap 5 detik simulasi
- Skor pemilihan rute adalah `estimasi waktu + 3 × reservasi 45 detik terakhir − bias preferensi`, bias yang dipilih supervisor bernilai 5 detik
- Batas detour diperiksa tanpa pengurangan bias: `estimasi waktu + penalti reservasi ≤ biaya jalur utama + 30 detik`, tujuan kendaraan tetap sama
- Total jam-kendaraan adalah `Σ(kendaraan aktif + kendaraan tertahan masuk) / 3600`, dengan langkah simulasi 1 detik
- Rata-rata tunggu dan perjalanan hanya dihitung dari trip selesai, sehingga harus dibaca bersama jumlah trip selesai, kendaraan aktif, dan kendaraan tertahan
- Hambatan simpang berarti ada kendaraan berhenti di bagian internal simpang selama setidaknya 5 detik berturut-turut, bukan verifikasi seluruh simpang kota

## Peta kode untuk penjelasan

| Bagian | Lokasi utama |
| --- | --- |
| Pengamat, Katup, Rute, dan loop penggabungan | `katup_controller.py`: `AgenPengamat`, `AgenKatup`, `AgenRute`, `run_simulation` |
| Pilihan profil, adapter provider, validasi, dan fallback | `katup_core/strategy.py`: `PROFILES`, `LLMClient`, `validate_decision`, `Supervisor` |
| Jaringan, demand, sensor, dan signature perbandingan | `katup_core/scenarios.py`: `get_profile`, `build_case` |
| Konversi snapshot Jakarta | `tools/build_jakarta.py`: `build`, `alternative_paths` |
| Persiapan CSV observasi | `tools/import_traffic.py`: `import_traffic` |
| Integrasi simulasi dengan telemetry | `deploy/run_controller.py`: `publish_step`, `make_state`, `trip_summary` |
| API, pembatasan origin, dan WebSocket | `deploy/server.py`: `start`, `comparison_data`, `telemetry_stream` |
| Peta, gerak kendaraan, alasan keputusan, hasil | `deploy/assets/dashboard.js`: `buildMap`, `animate`, `renderDecision`, `renderComparison` |

## Batas klaim

LLM berfungsi sebagai pengawas strategi, bukan pengganti tiga agen dan bukan sistem pembelajaran yang telah dilatih dengan lalu lintas Jakarta. Adapter DeepSeek/Gemini siap dikonfigurasi, tetapi efektivitas model belum diuji dengan API nyata. CSV importer juga belum melakukan kalibrasi otomatis. Data lapangan terbaru dengan sumber yang sah masih diperlukan untuk menilai kesesuaian simulasi dengan Jakarta sebenarnya.

Tidak ada hasil emisi pada pengujian branch ini. Tidak ada koneksi ke APILL/ATCS atau perangkat jalan nyata. Bukti dan hasil numerik pengujian ada pada [LLM_VALIDATION.md](LLM_VALIDATION.md).
