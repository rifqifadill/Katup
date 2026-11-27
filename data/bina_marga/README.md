# Bina Marga–Cipayung, Jakarta Timur

Pin pengguna: −6.319669, 106.889986, di Jalan Bina Marga. Snapshot OpenStreetMap menyimpan geometri, arah, nama, dan koneksi jalan dengan lisensi ODbL. Tangkapan layar pengguna menunjukkan lokasi, bukan foto kondisi pekerjaan.

## Bukti dan batas klaim

Laporan Metro TV tanggal 11 September 2026 mengutip Dishub mengenai proyek SPAM Buaran 3 P7 di koridor Gempol–Bina Marga, dengan rencana rekayasa 8 September 2026–31 Januari 2027. Sumber itu menyebut pekerjaan bertahap dan pengaturan buka-tutup. Tautannya tersedia di `sources.json`, dengan tingkat bukti sebagai laporan sekunder; unggahan asli Dishub belum diperiksa langsung.

Rentang rencana proyek tidak membuktikan posisi atau panjang galian yang masih terbuka pada 28 November. Batas STA dalam jadwal lama belum dipetakan ke pin. Informasi galian panjang dari pengguna disimpan sebagai laporan pengguna, bukan pengukuran independen. `current_conditions.csv` mempertahankan angka observasi yang belum diperoleh sebagai `NA`.

## Model yang ditambahkan

Zona hambatan uji sepanjang sekitar 200 m ditempatkan dekat pin pada lima potongan jalan menuju Cipayung. Panjang, titik awal, kecepatan 5 km/jam, dan lebar lajur 2,4 m adalah asumsi eksperimen. Model mempertahankan satu lajur per arah; tidak menambah lajur untuk membuat penyempitan 4 menjadi 2. Arah balik tetap ada.

Model ini merupakan pendekatan hambatan pada arah ke Cipayung, **belum mereplikasi penggunaan satu lajur bersama dan petugas buka-tutup aktual**. Karena itu hasilnya hanya menilai skenario kapasitas tersebut. Model tidak menutup seluruh koridor proyek sekaligus dan tidak mengklaim seluruh galian terbuka sepanjang rencana proyek.

Lampu uji ditempatkan pada simpang Gempol–Ceger–Bina Marga. Simpang sumber OSM berjenis `priority`; lampu ini adalah perangkat eksperimen KATUP, bukan bukti APILL lapangan. Program baseline tiga pendekat bergantian menggunakan hijau 40 s, kuning 3 s dan semua-merah 2 s, siklus 135 s. Pengamat menggabungkan sekitar 450 m ruas sebelum pekerjaan.

## Rute

Asal yang sama berada di Gempol Raya sebelum pilihan ke Bina Marga/Mpok Nori. Tujuan yang sama berada di Cilangkap Raya setelah simpang Raya Cipayung. Panjang merupakan jumlah ruas eksternal SUMO, tidak termasuk koneksi internal simpang.

| Rute | Jalan | Panjang model |
| --- | --- | ---: |
| Utama | Gempol Raya–Gempol–Bina Marga–Raya Cipayung–Cilangkap | 3.096,75 m |
| Alternatif | Mpok Nori–Mabes Hankam–Setu–Cilangkap | 4.920,70 m |

Satu kandidat alternatif pada jalan umum dipertahankan setelah pemeriksaan konektivitas dan arah. Tidak ada rute tambahan yang dipaksakan melewati gang sempit atau terminal. Jalur alternatif lebih panjang dan bukan pengalihan resmi Dishub; klasifikasi serta lebar dari OSM belum menggantikan survei kelayakan. Agen Rute tetap mengecek kapasitas serta biaya perjalanan sebelum mengalihkan.

## Reproduksi

Konverter sistem 1.18 mengalami assertion saat membaca geometri sumber ini. Netconvert 1.28 digunakan khusus untuk membangun peta ini, sedangkan runtime simulasi tetap SUMO 1.18. Installer hanya menyiapkan konverter pada direktori runtime yang diabaikan Git, tanpa mengganti paket sistem.

```bash
.venv/bin/python tools/install_netconvert.py
.venv/bin/python tools/build_corridors.py bina_marga
python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python tests/evaluate_hybrid.py --corridor bina_marga --seeds 1 42 --output output/bina-paired --without-api
```

Netconvert lain minimal versi 1.28 dapat dipilih dengan `KATUP_NETCONVERT=/path/netconvert`. Snapshot dan spesifikasi disertakan sehingga build tidak perlu mengunduh peta ulang. Detail asumsi ada di `simulation_assumptions.json`; lembar unduhan website adalah `datasheet.xlsx`. LLM nonaktif.
