# Galian berat v2

Skenario ini dibangun oleh `python3 katup_scenario.py` dari jaringan tahap 5.
Baseline dan KATUP memakai jaringan, demand, perilaku pengemudi, waktu simulasi,
dan seed yang sama. Perbedaan perlakuan adalah agent pengendali dan saran rute.

- Arus utama 1.500 kendaraan/jam, total 3.180 kendaraan/jam.
- Horizon 1.800 detik, total 1.590 kendaraan dijadwalkan.
- Asal arus utama di `edge_W_far2W`, tujuan di `edge_E2CBD`.
- Zona galian nominal 150 m, panjang lajur hasil netconvert 142 m, satu lajur dengan batas 1,39 m/s.
- Pemilihan lajur keberangkatan acak untuk kedua mode, menggunakan seed yang sama.
- Koneksi masuk menuju ruas galian memakai `keepClear=0` di kedua mode. Ini adalah asumsi stress test tentang pengemudi yang bisa memasuki kotak simpang saat hilir padat.
- Baseline memakai siklus 90 detik. Setiap arus masuk memiliki hijau 40 s, kuning 3 s, merah 47 s. Utara/Selatan bersamaan, Barat bergantian. Jeda semua-merah 2 s tetap ada di tiap pergantian. Cabang Timur melayani arus keluar dari simpang kendali.
- KATUP memilih pengalihan 70%, 82%, atau 90% kandidat menurut beban ruas hilir. Kandidat hanya dialihkan jika tujuan bisa dipertahankan, kapasitas alternatif tersedia, dan estimasi biaya memenuhi kriteria. Biaya rute diperbarui tiap 5 s dan memperhitungkan kendaraan yang baru mendapat saran rute.
- Lampu KATUP melayani antrean kedua kelompok arus, mengakhiri hijau kosong, dan melindungi ruang hilir. Minimum hijau 12 s untuk Utara/Selatan dan 10 s untuk Barat. Kuning dan semua-merah mengikuti fase asli.

Detektor E2 mengukur panjang antrean dalam meter. Spillback dihitung saat antrean
terpanjang mencapai 90% ruas hilir. Waktu simpang terhambat menghitung kejadian
kendaraan berhenti di internal simpang selama setidaknya 5 detik berturut-turut.
Indikator ini mengukur okupansi simpang oleh kendaraan berhenti.

Rata-rata waktu tunggu/perjalanan berasal dari tripinfo kendaraan yang tiba.
Total jam-kendaraan mengintegrasikan semua kendaraan aktif dan yang menunggu
insertion, sehingga antrean di batas jaringan ikut dihitung.

Pengujian yang dapat diulang:

```bash
SUMO_HOME=/usr/share/sumo python3 tests/evaluate_scenarios.py --seeds 1 2 3 42 --output /tmp/katup-validation
```

Pengujian memeriksa jadwal lampu baseline, konservasi jumlah kendaraan, tabrakan,
teleport, spillback, trip selesai, serta waktu seluruh kendaraan. Hash skenario
mencegah dashboard membandingkan hasil dari versi model/pengendali yang berbeda.
