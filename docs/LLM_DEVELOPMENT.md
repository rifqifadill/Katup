# KATUP Hybrid, branch llm

Implementasi ini mempertahankan tiga agen heuristik, menambahkan satu pengatur strategi LLM, dan menyediakan peta koridor Jakarta dari OpenStreetMap. Pengerjaan terpisah dari checkout website produksi, tidak memerlukan koneksi API untuk menjalankan simulasi.

## Yang sudah tersedia

- Sembilan koridor, Bina Marga–Cipayung, Kebon Sirih–Thamrin–Tugu Tani, UI–Margonda, Akses UI–Kelapa Dua, Simpang Pasar Rebo–arah Ciliwung, Pasar Rebo–Raya Bogor, TB Simatupang–Tanjung Barat, Pondok Pinang–Pondok Indah, dan jaringan uji lama
- Empat variasi arus, lengang, jam sibuk, lonjakan, dan bypass padat
- Tiga mode, baseline, KATUP Heuristik, dan KATUP Hybrid
- Pengatur strategi asinkron dengan validasi JSON, identitas sesi, umur data, batas permintaan, dan fallback
- Empat pilihan strategi terbatas, balanced, protect_downstream, relieve_upstream, spread_routes
- Peta kendaraan, ringkasan antrean, tindakan KATUP, dan warna lampu
- Perbandingan hasil per koridor dan pola arus, dengan pemeriksaan signature, seed, versi SUMO, durasi, dan sesi selesai
- Import CSV pengamatan, validasi data ganda, agregasi 15 menit, provenance, dan pemisahan tanggal kalibrasi/holdout

Empat koridor tambahan beserta sumber peta, jumlah lajur, dan hasil uji ada di [REGIONAL_CORRIDORS.md](REGIONAL_CORRIDORS.md). UI–Margonda menjadi pilihan awal. Jalan Akses UI yang dipilih memiliki satu lajur per arah menurut jaringan OSM, sehingga skenario memakai pembatasan kecepatan dan lebar lajur, tanpa mengarang penutupan dari dua lajur.

Tambahan simpang pada pin −6.306099, 106.865299 memiliki [lembar riset tersendiri](../data/simpang_pasar_rebo/README.md), termasuk XLSX dan audit harian 20–26 November 2026. Data lalu lintas terukur serta status galian pada periode itu belum diperoleh dari sumber yang dapat diverifikasi. Galian menuju Ciliwung adalah skenario uji dengan label eksplisit, bukan rekonstruksi kejadian yang telah dikalibrasi. Kasus ini tetap tersedia melalui pilihan koridor; default instalasi umum tetap UI–Margonda.

Tambahan terbaru [Kebon Sirih–Thamrin–Tugu Tani](KEBON_SIRIH.md) memakai geometri OSM dan model proyek historis Juli–Agustus 2026 dengan dua alternatif legal yang berbagi ruas utara. Penyempitan empat menjadi dua lajur dibedakan dari snapshot OSM sesudah proyek. Volume, kecepatan zona, dan APILL tetap asumsi, LLM nonaktif. Kasus Kebon Sirih tetap tersedia, dan hasilnya diperbarui saat signature penelitian berubah.

Tambahan [Bina Marga–Cipayung](../data/bina_marga/README.md) mengikuti pin pengguna, memakai satu alternatif jalan umum via Mpok Nori–Setu–Cilangkap. Bukti proyek berasal dari laporan sekunder yang mengutip Dishub; posisi galian terbaru dan data lalu lintas belum terverifikasi. Model hambatan sekitar 200 m bukan replika petugas buka-tutup. Demo memilih `KATUP_CORRIDOR=bina_marga`; service produksi tidak berubah.

Tampilan pengguna memakai nama Tanpa KATUP, Dengan KATUP, dan KATUP + AI. Grafik, timeline, panel agen, serta statistik token dan latency telah dihapus dari halaman. Backend tetap merekam data penelitian. Tabel hasil menampilkan kendaraan sampai tujuan, waktu perjalanan dan menunggu, serta durasi antrean mencapai simpang dan simpang terhalang. Perubahan yang memburuk tetap disebut pada ringkasan hasil. Mode AI yang belum terhubung diberi keterangan singkat pada pilihan simulasi dan hasilnya.

## Menjalankan lokal

```bash
python3 -m venv .venv --system-site-packages
.venv/bin/pip install -r deploy/public-requirements.txt
KATUP_PYTHON="$PWD/.venv/bin/python" bash deploy/llm-preview.sh
```

Buka `http://127.0.0.1:19010`. SUMO harus tersedia dan `SUMO_HOME=/usr/share/sumo` sesuai instalasi. Proses simulasi dan hasil run menggunakan `.runtime-llm`, sehingga tidak menimpa hasil website produksi. Koneksi jarak jauh dapat memakai SSH port forwarding ke port ini. Script ini tidak mengubah layanan systemd maupun Cloudflare Pages.

Contoh dari laptop sendiri, ganti `IP_VPS` dengan alamat VPS:

```bash
ssh -L 19010:127.0.0.1:19010 ubuntu@IP_VPS
```

Buka `http://localhost:19010` di laptop saat preview berjalan di VPS. Branch menggunakan `KATUP_STANDALONE=1`, sehingga launcher menjalankan satu proses SUMO headless terpisah dari layanan produksi.

## Demo publik tanpa API

Cloudflare Quick Tunnel meneruskan HTTPS dan WebSocket ke port lokal 19010. Instalasi khusus branch ini memakai layanan `katup-llm-dashboard` dan `katup-llm-tunnel`, berjalan sebagai pengguna project dan aktif kembali saat VPS menyala. Installer membutuhkan `sudo` untuk pendaftaran layanan, SUMO, virtualenv project, dan binary cloudflared yang sudah tersedia.

```bash
python3 deploy/install-llm-public.py
python3 deploy/llm-public-url.py
```

URL dibaca dari log sesi tunnel saat ini yang disimpan di `.runtime-llm/public-tunnel.log`. Alamat dapat berubah jika tunnel dimulai ulang. Tidak perlu membuka port masuk tambahan. Demo ini terbuka tanpa login dan satu sesi simulasinya dipakai bersama oleh semua pengunjung.

Layanan demo publik secara eksplisit menetapkan provider LLM `disabled` dan kunci kosong, tidak membaca `.env`. Mengisi `.env` untuk preview lokal tidak otomatis mengaktifkan API pada demo publik. Saat nanti mengaktifkan API publik, konfigurasi layanan perlu diperbarui secara terpisah.

```bash
sudo systemctl status katup-llm-dashboard katup-llm-tunnel --no-pager
sudo journalctl -u katup-llm-dashboard -n 40 --no-pager
sudo systemctl stop katup-llm-tunnel katup-llm-dashboard
```

## Menghubungkan API nanti

Salin `.env.example` ke `.env`, lalu isi di VPS sendiri. Berkas `.env` diabaikan Git dan kunci API tidak dikirim ke frontend.

Untuk DeepSeek:

```text
KATUP_LLM_PROVIDER=deepseek
KATUP_LLM_MODEL=deepseek-flash
KATUP_LLM_API_KEY=isi_di_VPS
```

Untuk Gemini:

```text
KATUP_LLM_PROVIDER=gemini
KATUP_LLM_MODEL=gemini-3.8-flash
KATUP_LLM_API_KEY=isi_di_VPS
```

Restart hanya proses preview setelah pengisian. Tidak ada API eksternal yang dipanggil selama pengembangan ini. Adapter diuji memakai respons HTTP tiruan yang diberi label fixture.

## Cara keputusan dijalankan

Agen Pengamat tetap membaca kondisi setiap detik simulasi. Pada mode Hybrid, ringkasan antrean dan biaya/ketersediaan rute dikirim setiap 30 detik simulasi, maksimum 80 permintaan per sesi. Worker terpisah tidak memakai TraCI dan tidak menghentikan langkah SUMO ketika menunggu API. Timeout default 6 detik waktu nyata.

LLM mengembalikan JSON berisi `run_id`, `simulation_time`, `profile`, `route_bias`, dan `reason`. Field tambahan, mode tidak dikenal, rute yang tidak tersedia, jawaban dari sesi berbeda, atau data berumur lebih dari 45 detik simulasi ditolak. Strategi juga kedaluwarsa berdasarkan waktu sumber datanya. Kecepatan demo memengaruhi seberapa cepat keputusan menjadi basi.

Jika API telah dikonfigurasi, perbandingan dengan Hybrid juga mensyaratkan delay playback yang sama. Latency API memakai waktu nyata, sedangkan umur data memakai waktu simulasi, sehingga membandingkan Hybrid 10× dengan mode lain 1× dapat mengubah kesempatan penerapan strateginya. Pada pengujian tanpa API, percepatan playback tidak mengubah kebijakan kendali.

LLM tidak dapat menulis fase lampu atau rute sembarang. Tiga agen tetap memeriksa minimum hijau 10/12 detik, transisi kuning dan semua-merah, batas antrean hilir, kapasitas rute, tujuan kendaraan, dan batas tambahan biaya 30 detik. Bias rute hanya mengubah urutan kandidat yang sah. Target pengalihan maksimum 90 persen kandidat, bukan 90 persen semua kendaraan dalam jaringan.

Alurnya: **SUMO → TraCI → Pengamat → ringkasan supervisor → validasi → Katup dan Rute → SUMO**. Sambil itu, runner menulis telemetry yang dibaca FastAPI dan dikirim melalui WebSocket ke dashboard. Supervisor hanya memilih parameter dari daftar yang diizinkan, ketiga agen tetap mengeksekusi kendali setiap detik simulasi.

| Strategi | Batas hijau arus utama saat antrean silang ada | Tambahan target pengalihan |
| --- | ---: | ---: |
| Seimbang | 30 detik | 0 |
| Lindungi hilir | 20 detik | 5 poin persentase |
| Urai hulu | 35 detik | 0 |
| Sebar arus | 30 detik | 3 poin persentase |

Angka di atas tetap dibatasi pemeriksaan hilir dan minimum hijau, dan tidak memperpanjang durasi fase statik SUMO. Profil `relieve_upstream` dapat melepas arus lebih lama daripada profil Seimbang ketika hilir masih tersedia, bukan jaminan bahwa antrean selalu berkurang.

Tanpa API, status Hybrid adalah `not_configured`, permintaan nol, dan kebijakannya identik dengan heuristik. Dashboard menyatakan kondisi ini dengan jelas. Mengirim data lewat API merupakan inference dengan konteks, bukan fine-tuning model. Hasil Hybrid baru dapat disebut dipengaruhi LLM jika ada keputusan eksternal yang benar-benar diterapkan.

## Data lalu lintas

CSV harus memiliki kolom `timestamp,road_id,direction,vehicle_count,speed_kmh`. Counts harus mewakili interval pengamatan yang tidak saling tumpang tindih. Kecepatan diagregasi sebagai rata-rata sampel, bukan rata-rata berbobot kendaraan. Sumber dan lisensi wajib ditulis.

```bash
python3 tools/import_traffic.py pengamatan.csv --output output/data --source "nama sumber dan periode" --license "lisensi dataset"
```

Tools ini menyiapkan pengamatan untuk kalibrasi. Data belum otomatis mengubah demand SUMO, belum menjadi training LLM, dan belum membuktikan kondisi satu minggu terakhir di Jakarta. Snapshot peta menyediakan geometri, bukan volume lalu lintas.

## Pengujian

```bash
.venv/bin/pip install httpx
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python tests/evaluate_hybrid.py --corridor jakarta_pondok_pinang --seeds 1 2 3 42 --output output/validation --without-api
.venv/bin/python tests/verify_supervisor_sumo.py
```

Setiap run memeriksa konservasi kendaraan pada akhir 1.800 detik, tabrakan, teleport, urutan fase, dan durasi kuning/semua-merah. Pada baseline, fase juga diperiksa terhadap program fixed-time setiap langkah. Pengujian API timeout, jawaban basi, kapasitas rute, dan request budget memakai fixture, bukan klaim hasil API nyata.

Pengujian browser dilakukan pada preview port 19010 dengan API nonaktif:

```bash
.venv/bin/pip install -r deploy/tests/requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python deploy/tests/hybrid_browser.py
```

Script browser menjalankan lalu menghentikan sesi pada instance preview tersebut. Gambar dan keluaran pengujian disimpan di `output/browser`, direktori hasil mentah diabaikan Git.

Catatan penyelarasan Bab 1–5 ada di [REPORT_ALIGNMENT.md](REPORT_ALIGNMENT.md). Laporan lama belum menggambarkan hasil koridor geografis maupun efektivitas model LLM.

Hasil koridor baru tidak boleh dicampur dengan laporan lama. Antrean, spillback, waktu perjalanan, serta beban waktu kendaraan dapat membaik atau memburuk tergantung arus dan struktur jaringan. Nilai nol tabrakan dalam simulasi tidak menjamin keselamatan pada jalan nyata.
