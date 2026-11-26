# Koridor UI, Depok, Pasar Rebo, dan TB Simatupang

Keempat pilihan ini menambah koridor lama pada branch `llm`. Geometri dan nama jalan diambil dari snapshot OpenStreetMap pada 26 November 2026. Volume kendaraan, zona pekerjaan, dan jadwal sinyal adalah skenario eksperimen, bukan kondisi lalu lintas lapangan saat ini.

## Area dan jalan utama

| Pilihan | Jalan utama pada sumber peta | Kondisi simulasi | Jalur alternatif |
| --- | --- | --- | --- |
| Universitas Indonesia–Margonda, Depok | Jalan Raya Margonda, sekitar simpang Jalan Cengkeh | 3 menjadi 1 lajur, zona lambat sekitar 172 m | Cengkeh–Sawo |
| Akses UI–Kelapa Dua, Depok | Jalan Komjen Polisi Mohammad Jasin, sekitar Jalan Bhakti | Tetap 1 lajur per arah, ruas yang dipantau dibatasi menjadi 5 km/jam dan lebar 2,4 m, sekitar 87 m | Menpor dan Bhakti–Menpor |
| Pasar Rebo–Raya Bogor, Jakarta Timur | Jalan Raya Bogor, sekitar Jalan Pendidikan III | 2 menjadi 1 lajur, zona lambat sekitar 216 m | Pendidikan–Jati dan Pedati–Pendidikan |
| TB Simatupang–Tanjung Barat, Jakarta Selatan | Jalan Tahi Bonar Simatupang, sekitar Jalan Kebagusan I | 2 menjadi 1 lajur, zona lambat sekitar 172 m | Assakinah–Sepat dan Kebagusan I–Raya |

Jumlah lajur sebelum zona pekerjaan mengikuti hasil impor OSM. Sebagian atribut lajur dan kecepatan berasal dari inferensi tipe jalan SUMO saat tag peta tidak lengkap. Tidak ada penambahan lajur hanya untuk membuat koridor tampak seperti skenario dua menjadi satu.

Snapshot memuat jalan umum yang dapat dilalui kendaraan bermotor menurut tag OSM, dengan pengecualian akses privat atau terlarang yang ditandai secara eksplisit. Hal ini belum membuktikan kelayakan fisik setiap gang untuk pengalihan kendaraan nyata. Jalan tol tidak dimasukkan sebagai bypass. Masing-masing jaringan simulasi mempertahankan rute eksperimen dan sekitar 400 ruas konteks agar tetap ringan, bukan seluruh jaringan kota atau seluruh jalan di dalam kampus UI.

Tombol **Lihat lokasi asli** pada dashboard membuka koordinat simpang yang dipilih di OpenStreetMap. Nama jalan dan titik geometri tidak diganti dengan jaringan sintetik yang diberi nama lokasi tersebut.

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

## Reproduksi

Snapshot sumber telah disertakan, sehingga konversi ulang tidak memerlukan unduhan peta:

```bash
python tools/build_corridors.py ui_depok akses_ui pasar_rebo tb_simatupang
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/evaluate_hybrid.py --corridor ui_depok --seeds 42 --output output/regions-ui --without-api
```

Untuk mengganti snapshot, gunakan `python tools/fetch_corridors.py ui_depok akses_ui pasar_rebo tb_simatupang` terlebih dahulu. ID ruas pada snapshot baru mungkin berubah, sehingga `spec.json` perlu diperiksa dan seluruh pengujian dijalankan ulang. Hasil dari snapshot atau signature lama tidak dicampur dengan hasil baru.
