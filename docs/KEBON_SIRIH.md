# Kebon Sirih–Thamrin–Tugu Tani

Pilihan baru pada branch `llm` menambahkan kasus historis peningkatan Jalan Kebon Sirih pada Juli–Agustus 2026. Geometri, arah jalan, dan koneksi diambil dari snapshot OpenStreetMap, sedangkan pekerjaan 4 menjadi 2 lajur mengikuti liputan historis. Proyek telah dinyatakan selesai dalam berita resmi bertanggal 31 Agustus. Sumber dan batasan lengkap ada di [lembar riset](../data/kebon_sirih/README.md).

## Implementasi

| Bagian | Berkas | Fungsi |
| --- | --- | --- |
| Batas peta dan snapshot | `tools/fetch_corridors.py`, `scenarios/kebon_sirih/source/` | Mempertahankan asal geometri dan lisensinya |
| Spesifikasi kasus | `scenarios/kebon_sirih/spec.json` | Memilih ruas proyek, simpang, rute utama dan dua alternatif |
| Pembentukan jaringan historis | `tools/build_workzone.py` melalui `tools/build_corridors.py` | Membentuk pekerjaan pada tiga ruas dengan total eksternal 348,67 m, sesuai panjang resmi sekitar 345 m |
| Katalog dan sensor | `katup_core/scenarios.py` | Menambahkan pilihan koridor dan sensor E2 pada setiap potongan pendekat |
| Agen Pengamat | `katup_controller.py`, `AgenPengamat.evaluate` | Menggabungkan lima ruas sepanjang 302,48 m sebelum pekerjaan, jumlah kendaraan, okupansi berbobot panjang lajur, dan kecepatan berbobot jumlah kendaraan |
| Agen Katup | `katup_controller.py`, `AgenKatup.apply_control` | Membaca antrean pendekat sampai ruas hulu, mempertahankan minimum hijau dan transisi kuning/semua-merah |
| Agen Rute | `katup_controller.py`, `AgenRute.refresh_routes` dan `guide_traffic` | Mempertahankan asal/tujuan, mengecek ruas bersama pada kedua alternatif, tidak mengalihkan ke ruas yang terisi di atas ambang kapasitas |
| Telemetri | `deploy/run_controller.py` | Mengirim ringkasan beberapa ruas dan posisi SUMO yang sesungguhnya |
| Peta website | `deploy/assets/dashboard.js` | Menampilkan ketiga ruas pekerjaan, label historis dan unduhan riset |

Konektor OSM pertama setelah simpang panjangnya hanya 0,2 m. Mengukurnya sendirian akan menghasilkan kapasitas yang tidak masuk akal. Karena itu profil mendefinisikan `pre_edges`, `bottleneck_edges`, `detector_groups`, dan `approach_edges`. Profil lama tetap memakai satu ruas ketika kelompok tidak didefinisikan. Antrean kelompok merupakan jumlah antrean terpanjang per potongan, bukan pengukuran antrean kontinu melewati seluruh simpang internal.

## Hasil uji berpasangan

Enam simulasi 1.800 detik dengan SUMO 1.18.0 menggunakan dua seed, 1 dan 42, masing-masing baseline, heuristik, dan hybrid tanpa API. Jaringan, demand, seed dan durasi sama pada perbandingan setiap pasangan, dengan 1.845 kendaraan terjadwal. Jadwal baseline tetap, urutan fase, kuning/semua-merah, konservasi kendaraan dan nol tabrakan/teleport diperiksa selama run.

| Seed | Tiba baseline → heuristik | Total jam-kendaraan baseline → heuristik | Dialihkan heuristik |
| --- | ---: | ---: | ---: |
| 1 | 580 → 747 | 333,494 → 298,666 | 170 |
| 42 | 581 → 779 | 332,432 → 291,352 | 184 |

Pada konfigurasi ini, perbaikan terjadi pada jumlah perjalanan yang selesai dan total jam-kendaraan. Spillback di sensor sebelum pekerjaan dan hambatan simpang tercatat nol pada kedua mode untuk kedua seed; hasil ini **tidak membuktikan** bahwa KATUP mencegah simpang tertutup pada kasus ini. Antrean hulu tetap terjadi, dan model tidak dikalibrasi untuk mereproduksi angka antrean 850 m dalam berita. Hybrid tanpa API menghasilkan ringkasan yang sama dengan heuristik.

Total jam-kendaraan menghitung kendaraan berjalan dan tertahan masuk, sehingga hasil tidak hanya melihat perjalanan yang telah selesai. Rata-rata waktu perjalanan dan menunggu tetap dibaca sebagai statistik trip selesai dengan populasi yang berbeda. Bukti terpilah tersimpan di `deploy/evidence/kebon-validation.json`; keluaran mentah trip dan audit berada pada direktori `output/` lokal yang diabaikan Git.

## Reproduksi dan demo

```bash
.venv/bin/python tools/build_corridors.py kebon_sirih
python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python tests/evaluate_hybrid.py --corridor kebon_sirih --seeds 1 42 --output output/kebon-final --without-api
```

Instalasi umum tetap memakai default yang sudah ada. Demo VPS khusus branch `llm` memilih Bina Marga sebagai tampilan awal melalui override service `katup-llm-dashboard`; Kebon Sirih tetap tersedia pada pilihan koridor dengan hasil yang diperbarui setelah perubahan signature. Tunnel yang sama dipertahankan; service produksi branch utama tidak diubah. LLM tetap nonaktif.
