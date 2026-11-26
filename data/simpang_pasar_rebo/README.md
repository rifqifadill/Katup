# Riset simpang Pasar Rebo menuju Ciliwung

Titik yang diminta: **−6.306099, 106.865299**. Periode pencarian: **20–26 November 2026 WIB**, tujuh hari penuh sebelum 27 November. Riset dilakukan pada 27 November 2026 WIB.

## Kesimpulan yang bisa dipakai

Geometri jalan biasa di sekitar simpang Raya Bogor–TB Simatupang tersedia melalui snapshot OpenStreetMap. Simpang terbagi menjadi beberapa simpul di peta; simpul kendali model berada sekitar 31 meter dari pin. Jalur yang diuji keluar simpang ke barat melalui TB Simatupang, menuju kawasan Ciliwung. Jalan tol dan ramp tol tidak dimasukkan ke jaringan jalan biasa.

**Belum ditemukan dataset publik terukur untuk titik ini pada 20–26 November 2026 yang dapat diakses dan diverifikasi saat riset.** Belum ada dasar untuk mengisi jumlah kendaraan, kecepatan, panjang antrean, durasi tertutupnya simpang, dan status galian per hari. Semua kolom itu berisi `NA`: belum tersedia, bukan nol. Ini lembar audit ketersediaan data, bukan hasil survei tujuh hari.

Laporan detikNews tanggal 2 Juni 2026 menyebut galian di TB Simatupang arah Pasar Minggu dan antrean sampai TL Pasar Rebo. Liputan 4 Juni menjelaskan peninjauan galian di area pertigaan Pasar Rebo arah Jakarta Selatan. Keduanya mendukung latar belakang kasus hambatan hilir, tetapi **tidak memverifikasi kondisi minggu terakhir atau lokasi galian yang sama dengan pin**. Volume dan panjang antrean numerik tidak disediakan.

Pengamatan pengguna tentang galian sekitar Oktober 2026 dicatat sebagai keterangan saksi yang belum diverifikasi. Pengumuman pekerjaan jembatan tol 22–28 November hanya ditemukan melalui mirror akun Jasa Marga; sumber asli tidak dapat diakses langsung. Informasi tersebut tidak dipakai sebagai bukti galian jalan biasa menuju Ciliwung. Pernyataan PAL Jaya tanggal 8 November membahas pekerjaan di dalam area gedung di Jakarta Selatan, sehingga juga tidak memastikan status galian pada pin.

Portal resmi Satu Data Indonesia menyediakan metadata rekap lalu lintas DKI, tetapi resource ditandai “URL Bermasalah”, dengan tag tahun 2014. Tanggal pembaruan metadata 3 September 2026 bukan tanggal observasi 20–26 November. Arsip CCTV dan hitungan per gerakan selama tujuh hari belum diperoleh. Ketiadaan data yang ditemukan tidak berarti tidak ada kemacetan.

## Isi berkas

- `datasheet.xlsx`: ringkasan, 21 baris audit harian untuk tiga kelompok arah, daftar sumber, dan asumsi simulasi
- `weekly_observations.csv`: data harian dengan nilai hilang eksplisit
- `sources.json` dan `sources.csv`: tanggal kejadian/publikasi, cakupan lokasi, status bukti, dan URL
- `search_log.json`: kata pencarian, periode, dan keterbatasan akses
- `simulation_assumptions.json`: parameter eksperimen yang dibaca dari jaringan hasil konversi

## Skenario yang ditambahkan

Pilihan `simpang_pasar_rebo` memakai jalan asli dari OSM dengan dua alternatif melalui Pendidikan/Jati–Mahoni–Kesehatan. Konektivitas rute mengikuti snapshot, bukan rekomendasi pengalihan resmi untuk dipakai di lapangan. Pembatasan yang tidak tercatat di OSM masih memerlukan pemeriksaan lapangan.

Zona galian ditempatkan pada ruas pertama setelah simpang ke barat sebagai **asumsi eksperimen**, bukan lokasi proyek yang sudah diverifikasi. Model menyempitkan dua lajur menjadi satu dan menurunkan kecepatan menjadi sekitar 5 km/jam. Panjang dan ruang antrean aktual model tercantum di lembar asumsi. Arus, tipe kendaraan, durasi, dan pengaturan lampu adalah parameter uji, belum dikalibrasi. Tanpa KATUP, tiap pendekat terlayani memiliki hijau tetap 40 detik, kuning 3 detik, semua-merah 2 detik. Dengan KATUP, agen menyesuaikan layanan dan mempertimbangkan rute alternatif. Ini bukan rekaman siklus APILL asli.

Perbandingan wajib menggunakan jaringan, zona galian, permintaan, seed, dan durasi yang sama. Kendaraan yang belum masuk atau belum selesai tetap dihitung. Angka hasil SUMO adalah hasil model; belum menjadi persentase perbaikan kondisi nyata Pasar Rebo. Mode AI tanpa API memakai fallback heuristik.

## Supaya bisa menjadi data lapangan yang valid

Butuh rekaman/survei bertanggal untuk tujuh hari, waktu pengamatan, arah tiap gerakan, klasifikasi dan jumlah kendaraan per interval, panjang antrean dalam meter, antrean yang masuk kotak simpang, durasi dan fase lampu, serta lokasi/panjang/jam kerja penutupan lajur. Catat asal rekaman, metode hitung, dan satuan. Data hari yang hilang tetap `NA`. Setelah diperoleh, baru demand dan kapasitas dikalibrasi, lalu diuji terhadap hari yang berbeda dari data kalibrasi.

Daftar URL sumber dan batas penggunaannya ada di `sources.csv` dan sheet Sumber. Tidak ada pengisian angka berdasarkan perkiraan berita atau ingatan pengguna.
