# Koridor Jakarta untuk KATUP Hybrid

Geometri jalan berasal dari snapshot OpenStreetMap kawasan Pondok Pinang–Pondok Indah, bukan jaringan jalan buatan yang ditempel di Jakarta. Snapshot hanya mempertahankan ruas trunk, primary, secondary, tertiary, dan ruas penghubungnya. Koordinat dan bentuk jalan dibawa ke SUMO dengan aturan berkendara kiri.

Sumber, bounding box, waktu pengambilan, dan lisensi ODbL dicatat di `source/provenance.json`. Atribusi OpenStreetMap ditampilkan pada dashboard. Snapshot `source/roads.osm.xml` disimpan agar hasil konversi dapat diulang tanpa mengunduh peta lagi.

Simpang kontrol berada pada Kartika Utama–Metro Alam III. Program sinyal ditambahkan untuk eksperimen, bukan salinan jadwal APILL lapangan. Ruas Metro Alam III dibagi menjadi ruas antrean dua lajur sekitar 208 m dan zona kerja satu lajur sekitar 215 m dengan batas 5 km/jam. Jumlah lajur yang tidak tersedia dalam OSM menggunakan inferensi netconvert, dan batas kecepatan simulasi dibatasi maksimum 50 km/jam.

Jalur utama dan dua jalur alternatif mengikuti koneksi sah pada hasil konversi, menuju ruas tujuan yang sama. Jalur alternatif lewat Gedung Hijau Raya atau Niaga Hijau Raya. Identitas ruas, lampu, fase, sensor, dan rute berada di `profile.json`.

**Data kendaraan masih sintetik.** Tidak ada klaim bahwa jumlah, kecepatan, atau kemacetan simulasi adalah kondisi Jakarta saat ini. Penutupan lajur juga merupakan skenario eksperimen. Tidak ada kontrol lampu jalan nyata.

Reproduksi jaringan menggunakan SUMO/netconvert 1.18.0:

```bash
python3 tools/build_jakarta.py
```

Hasil konversi dapat sedikit berubah pada versi SUMO lain. Ulangi pengujian setelah konversi dan gunakan signature skenario baru untuk membandingkan hasil.
