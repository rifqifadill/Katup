# Koridor Kebon Sirih, UI, Depok, Pasar Rebo, dan TB Simatupang

Pilihan regional ini menambah koridor lama pada branch `llm`. Geometri dan nama jalan diambil dari snapshot OpenStreetMap pada 26 November 2026. Volume kendaraan, zona pekerjaan, dan jadwal sinyal adalah skenario eksperimen, bukan kondisi lalu lintas lapangan saat ini.

## Area dan jalan utama

| Pilihan | Jalan utama pada sumber peta | Kondisi simulasi | Jalur alternatif |
| --- | --- | --- | --- |
| Kebon Sirih–Thamrin–Tugu Tani | Jalan Kebon Sirih, proyek historis Wisma Penta–BNPP RI | Historis 4 menjadi 2 lajur, sekitar 349 m pada tiga ruas, bukan galian aktif | Thamrin–Merdeka Selatan dan Wahid Hasyim–Agus Salim, berbagi koridor utara |
| Universitas Indonesia–Margonda, Depok | Jalan Raya Margonda, sekitar simpang Jalan Cengkeh | 3 menjadi 1 lajur, zona lambat sekitar 172 m | Cengkeh–Sawo |
| Akses UI–Kelapa Dua, Depok | Jalan Komjen Polisi Mohammad Jasin, sekitar Jalan Bhakti | Tetap 1 lajur per arah, ruas yang dipantau dibatasi menjadi 5 km/jam dan lebar 2,4 m, sekitar 87 m | Menpor dan Bhakti–Menpor |
| Pasar Rebo–Raya Bogor, Jakarta Timur | Jalan Raya Bogor, sekitar Jalan Pendidikan III | 2 menjadi 1 lajur, zona lambat sekitar 216 m | Pendidikan–Jati dan Pedati–Pendidikan |
| Simpang Pasar Rebo–arah Ciliwung | Simpang Raya Bogor–TB Simatupang, pin −6.306099, 106.865299 | 2 menjadi 1 lajur, zona lambat sekitar 45 m di ruas keluar ke barat, posisi galian adalah asumsi | Pendidikan/Jati–Mahoni–Kesehatan |
| TB Simatupang–Tanjung Barat, Jakarta Selatan | Jalan Tahi Bonar Simatupang, sekitar Jalan Kebagusan I | 2 menjadi 1 lajur, zona lambat sekitar 172 m | Assakinah–Sepat dan Kebagusan I–Raya |

Kebon Sirih memiliki pengecualian historis yang didokumentasikan: snapshot OSM tiga lajur diubah menjadi empat sebelum pekerjaan dan dua pada zona, berdasarkan liputan saat proyek. Rincian sumber, panjang rute, asumsi dan hasil dua seed ada di [KEBON_SIRIH.md](KEBON_SIRIH.md). Koridor lain mengikuti hasil impor OSM untuk jumlah lajur sebelum zona pekerjaan. Sebagian atribut lajur dan kecepatan berasal dari inferensi tipe jalan SUMO saat tag peta tidak lengkap. Tidak ada penambahan lajur hanya untuk membuat koridor tampak seperti skenario dua menjadi satu.

Snapshot memuat jalan umum yang dapat dilalui kendaraan bermotor menurut tag OSM, dengan pengecualian akses privat atau terlarang yang ditandai secara eksplisit. Hal ini belum membuktikan kelayakan fisik setiap gang untuk pengalihan kendaraan nyata. Jalan tol tidak dimasukkan sebagai bypass. Masing-masing jaringan simulasi mempertahankan rute eksperimen dan sekitar 400 ruas konteks agar tetap ringan, bukan seluruh jaringan kota atau seluruh jalan di dalam kampus UI.

Tombol **Lihat lokasi asli** pada dashboard membuka koordinat simpang yang dipilih di OpenStreetMap. Nama jalan dan titik geometri tidak diganti dengan jaringan sintetik yang diberi nama lokasi tersebut.

Simpang Pasar Rebo–arah Ciliwung adalah tambahan terpisah sekitar satu kilometer di utara kasus Pasar Rebo lama. Simpul jalan biasa terdekat berada sekitar 31 m dari pin pengguna. Simpang bermedian tetap terbagi menjadi beberapa simpul OSM; hanya satu simpul kendali yang diatur agen, sedangkan lampu lain memakai program jaringan yang sama pada setiap mode. Model ini tidak mengklaim koordinasi seluruh persimpangan di kawasan tersebut. Akses buntu pendek tanpa arus eksperimen dikeluarkan dari jaringan konteks; tiga pendekat kendali yang digunakan tetap terlayani. Slot sinyal dari koneksi yang dihapus dirapikan agar tidak meninggalkan lampu tanpa fase hijau.

Untuk kasus baru ini, status data tujuh hari dan sumber historis dijelaskan di [lembar riset](../data/simpang_pasar_rebo/README.md). Berita galian Juni 2026 tidak dianggap sebagai bukti kondisi November. Semua angka observasi harian yang belum diperoleh tetap `NA`; parameter simulasi terpisah dari observasi. Spreadsheet dapat diunduh dari catatan singkat di bawah peta.

## Cara jaringan dibangun

Setiap direktori `scenarios/<koridor>` memiliki:

- `source/roads.osm.xml`, snapshot jalan yang dapat dipakai ulang
- `source/provenance.json`, URL API per tile, bbox, waktu, lisensi ODbL, dan checksum snapshot
- `spec.json`, pilihan ruas sumber, simpang, jalur utama, dan alternatif sebelum pemodelan galian
- `network.net.xml`, hasil netconvert berkendara kiri
- `demand.rou.xml`, arus kendaraan sintetik yang sama untuk ketiga mode
- `profile.json`, pemetaan sensor, kelompok fase, dan rute untuk tiga agen

Unduhan menggunakan tile kecil karena API OSM membatasi jumlah titik pada satu permintaan. Snapshot dapat memuat bagian ruas yang melampaui bbox karena OSM mengembalikan geometri lengkap. Jaringan akhir dipilih dari rute yang saling terhubung, tanpa menggambar koneksi jalan baru.

Program sinyal eksperimen melayani satu pendekat bergantian dengan hijau 40 detik, kuning 3 detik, dan semua-merah 2 detik. UI–Margonda dan TB Simatupang memiliki 6 fase, Pasar Rebo 9 fase, dan Akses UI 12 fase. Program ini adalah baseline laboratorium yang konservatif, bukan rekaman APILL setempat atau baseline yang telah dioptimalkan.

Agen Katup tetap mempertahankan minimum hijau 10/12 detik dan transisi kuning/semua-merah. Pada fase silang, pemeriksaan antrean menggunakan pendekat yang sedang dilayani. Pengamat membaca semua pendekat silang yang dikonfigurasi, dan Agen Rute mempertahankan tujuan serta memilih koneksi yang sah.

## Pengujian, seed 42

Semua run berlangsung 1.800 detik dengan SUMO 1.18.0. Ketiga mode menggunakan jaringan dan demand yang sama pada setiap koridor, provider LLM nonaktif. Ada 12 run koridor baru dan 2 run regresi Pondok Pinang, semuanya selesai dengan konservasi kendaraan dan nol tabrakan/teleport. Urutan fase, durasi kuning/semua-merah, serta jadwal fixed-time baseline diperiksa sepanjang simulasi.

| Koridor | Terjadwal | Trip selesai Baseline → Heuristik | Spillback Baseline → Heuristik | Hambatan simpang Baseline → Heuristik |
| --- | ---: | ---: | ---: | ---: |
| UI–Margonda | 985 | 166 → 201 | 512 → 241 s | 0 → 14 s |
| Akses UI | 1.245 | 461 → 490 | 62 → 0 s | 0 → 0 s |
| Pasar Rebo | 1.220 | 489 → 616 | 173 → 48 s | 7 → 0 s |
| TB Simatupang | 1.045 | 168 → 304 | 590 → 617 s | 0 → 0 s |

Hybrid tanpa API identik dengan Heuristik pada keempat koridor, dengan nol permintaan API. Ada perbaikan jumlah trip selesai, tetapi UI masih menunjukkan tambahan hambatan simpang dan TB Simatupang masih menunjukkan tambahan spillback. Angka ini berasal dari satu seed per kasus, belum membuktikan kondisi atau efektivitas lapangan. Kendaraan yang tertahan masuk tetap dihitung pada total jam-kendaraan, sehingga rendahnya jumlah trip selesai tidak disembunyikan.

Sebanyak 17 tes otomatis memeriksa API, strategi, legalitas semua rute, tujuan pengalihan, sumber geometri, jumlah lajur, kelompok sinyal, dan pemilihan antrean pendekat. Uji browser memeriksa empat pilihan koridor, gerak kendaraan, mulai/hentikan, label lajur, tautan peta, serta layar ponsel tanpa overflow. Ringkasan bukti tersimpan di `deploy/evidence/regional-validation.json`.

### Tambahan simpang Pasar Rebo, dua seed

Kasus pin pengguna diuji terpisah sebanyak enam run: seed 1 dan 42, masing-masing baseline, heuristik, serta hybrid tanpa API. Semua memakai 1.220 kendaraan terjadwal selama 1.800 detik. Seluruh run lolos pemeriksaan konservasi kendaraan, nol tabrakan/teleport, jadwal tetap baseline, serta transisi kuning/semua-merah. Hybrid tanpa API menghasilkan ringkasan identik dengan heuristik.

| Seed | Trip selesai baseline → heuristik | Waktu perjalanan trip selesai | Menunggu trip selesai | Antrean mencapai simpang | Simpang terhalang |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 262 → 550 | 632,710 → 527,035 s | 362,695 → 190,069 s | 49 → 36 s | 0 → 0 s |
| 42 | 258 → 563 | 635,058 → 512,009 s | 364,872 → 171,199 s | 41 → 42 s | 130 → 0 s |

Perbaikan tidak terjadi pada semua indikator: seed 42 mengalami tambahan satu detik spillback. Rata-rata waktu hanya dihitung pada trip yang selesai; populasi trip selesai juga berubah. Total jam-kendaraan mencakup kendaraan yang belum selesai dan belum dapat masuk, sehingga dibaca bersama hitungan trip dan kendaraan tersisa. Sensor antrean hanya mencakup ruas yang dikonfigurasi, bukan seluruh panjang antrean di Raya Bogor. Dua seed ini belum cukup untuk menyatakan efektivitas lapangan. Bukti tersimpan di `deploy/evidence/simpang-validation.json`, dan tes otomatis kini berjumlah 18.

## Reproduksi

Snapshot sumber telah disertakan, sehingga konversi ulang tidak memerlukan unduhan peta:

```bash
python tools/build_corridors.py ui_depok akses_ui pasar_rebo tb_simatupang
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/evaluate_hybrid.py --corridor ui_depok --seeds 42 --output output/regions-ui --without-api
```

Untuk mengganti snapshot, gunakan `python tools/fetch_corridors.py ui_depok akses_ui pasar_rebo tb_simatupang` terlebih dahulu. ID ruas pada snapshot baru mungkin berubah, sehingga `spec.json` perlu diperiksa dan seluruh pengujian dijalankan ulang. Hasil dari snapshot atau signature lama tidak dicampur dengan hasil baru.
