# Kasus historis Kebon Sirih

Koridor ini merekonstruksi pekerjaan peningkatan/pembetonan Jalan Kebon Sirih pada Juli–Agustus 2026, bukan galian pipa aktif atau informasi lalu lintas November. Buletin resmi Dinas Bina Marga, halaman cetak 20, memuat berita bertanggal 31 Agustus 2026 yang menyatakan pekerjaan telah selesai.

Sumber resmi menyebut panjang 345 m dari Wisma Penta hingga Gedung BNPP RI dan awal proyek 9 Juli. Liputan Suara pada 13 Juli menyebut sekitar 350 m, empat menjadi dua lajur, serta antrean sekitar 850 m. Keterangan pekerja tentang mulai pekerjaan fisik pada 12 Juli disimpan sebagai atribusi tersendiri. Angka antrean itu bukan hitungan kendaraan per jam dan tidak membuktikan durasi simpang terhalang. Tidak ada pengalihan resmi pada saat liputan tersebut; dua alternatif di KATUP adalah rute eksperimen berdasarkan koneksi OSM.

## Peta dan alternatif

Snapshot OSM diambil 27 November 2026 UTC. Ruas biasa dipilih dari jaringan Thamrin, Kebon Sirih, Wahid Hasyim, Haji Agus Salim, Medan Merdeka Selatan/Timur, M. I. Ridwan Rais, dan Arief Rachman Hakim. Tidak ada sambungan jalan buatan atau bypass melalui jalan tol.

Asal ketiga rute sama: Thamrin sebelum simpang Wahid Hasyim. Tujuannya Arief Rachman Hakim menuju kawasan Tugu Tani. Panjang berikut adalah jumlah panjang ruas eksternal SUMO, tanpa koneksi internal simpang:

| Rute | Jalur | Panjang model |
| --- | --- | ---: |
| Utama | Thamrin utara → Kebon Sirih timur → Arief Rachman Hakim | 1.987,93 m |
| Alternatif 1 | Thamrin → Merdeka Selatan → Merdeka Timur → Ridwan Rais | 2.716,07 m |
| Alternatif 2 | Wahid Hasyim → Agus Salim → Kebon Sirih barat → Thamrin → koridor utara | 3.096,33 m |

Kedua alternatif berbagi ruas utara, sehingga tidak memiliki kapasitas yang sepenuhnya independen. Tidak dibuat belokan langsung Wahid Hasyim–Cemara yang bertentangan dengan koneksi arah jalan pada snapshot. Legalitas diperiksa menurut OSM dan SUMO, belum menjadi rekomendasi pengalihan untuk pengguna jalan nyata.

## Fakta dan asumsi model

- Panjang resmi pekerjaan: 345 m; model eksternal SUMO: 348,67 m pada tiga ruas, selisih geometri lajur/pemrosesan simpang dinyatakan terbuka
- Snapshot sesudah proyek mempunyai tiga lajur pada ruas sumber; konfigurasi empat menjadi dua lajur adalah override historis berdasarkan liputan, bukan klaim atribut OSM saat ini
- Dua lajur tersisa dimodelkan berdampingan sebagai pendekatan kapasitas, bukan salinan pagar pengecoran tahap tengah
- Kecepatan zona 10 km/jam, demand utama 2.400 kendaraan/jam, tiga arus silang masing-masing 350, serta dua arus latar alternatif masing-masing 120 adalah asumsi sintetik
- Semua kendaraan berupa mobil penumpang, tidak mewakili komposisi sepeda motor/bus/truk di lokasi
- Baseline empat kelompok bergantian: hijau 40 detik, kuning 3 detik, semua-merah 2 detik; siklus 180 detik, bukan jadwal APILL terukur atau fixed-time yang dioptimalkan
- Pengamat mengukur lima potongan sebelum proyek sepanjang 302,48 m, bukan hanya konektor pertama sepanjang 0,2 m
- Antrean kelompok menjumlahkan panjang antrean E2 terpanjang tiap potongan, tidak memasukkan celah dan koneksi internal, bukan panjang antrean kontinu seluruh kawasan
- Pengendalian adaptif hanya mengatur simpang Thamrin–Kebon Sirih yang dipilih, bukan semua lampu di jaringan
- LLM belum terhubung; mode Hybrid menggunakan fallback heuristik

Tanpa data volume, komposisi, kecepatan, APILL dan hitungan antrean bertanggal, model belum dikalibrasi ke kondisi lapangan. Antrean 850 m dari media tidak dijadikan target untuk memaksa hasil. Jumlah kendaraan belum masuk dan belum selesai tetap dilaporkan.

## Berkas

`sources.json` dan `sources.csv` menyimpan tautan dan cakupan bukti. `simulation_assumptions.json` menyimpan parameter serta panjang rute. `datasheet.xlsx` adalah versi yang dapat diunduh melalui website. Tidak ada data pengamatan harian yang dikarang. Ringkasan pengujian ada di `deploy/evidence/kebon-validation.json` setelah pengujian selesai.

Bangun ulang dari snapshot dengan `python tools/build_corridors.py kebon_sirih`. Uji pasangan dengan `python tests/evaluate_hybrid.py --corridor kebon_sirih --seeds 1 42 --output output/kebon-final --without-api`.
