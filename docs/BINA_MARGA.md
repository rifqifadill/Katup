# Penambahan koridor Bina Marga

Koridor ini menambah pilihan Bina Marga–Cipayung pada branch `llm` tanpa mengubah `main`. [Lembar riset](../data/bina_marga/README.md) memisahkan bukti proyek, laporan pengguna, geometri OSM, serta asumsi simulasi.

## Bagian kode

| Bagian | Berkas | Peran |
| --- | --- | --- |
| Area peta | `tools/fetch_corridors.py` | Mengambil snapshot jalan biasa, provenance dan checksum |
| Spesifikasi | `scenarios/bina_marga/spec.json` | Pin, koridor, lima potongan zona uji, arus, rute utama dan satu alternatif |
| Konverter | `tools/install_netconvert.py` | Menyiapkan netconvert 1.28 terpisah, checksum diverifikasi terhadap metadata PyPI |
| Pembuatan jaringan | `tools/build_bina_marga.py` | Mempertahankan geometri, arah balik dan jumlah lajur, memasang lampu eksperimen pada simpang Gempol–Ceger–Bina Marga |
| Katalog | `katup_core/scenarios.py` | Mengenalkan pilihan koridor serta label lajur yang sesuai |
| Tiga agen | `katup_controller.py` | Menggunakan mekanisme Pengamat, Katup dan Rute yang sudah ada, sensor beberapa ruas dan pemeriksaan biaya/kapasitas tetap berjalan |
| Peta dan hasil | `deploy/assets/dashboard.js` | Memusatkan area pekerjaan agar kendaraan lebih jelas dan menyebut waktu rata-rata yang memburuk pada ringkasan |
| Sumber publik | `deploy/server.py` | Melayani XLSX dan metadata sumber khusus koridor |

Satu alternatif yang dimasukkan melewati Mpok Nori–Setu–Cilangkap, lebih panjang daripada rute utama. Kandidat melalui gang sempit tidak dipaksakan menjadi rute kendaraan. Jalur utama dan alternatif mempertahankan asal/tujuan yang sama serta koneksi yang sah menurut snapshot. Ini belum menggantikan survei kelayakan pengalihan nyata.

## Validasi

Sebanyak 25 tes otomatis memeriksa API, sumber, checksum, kondisi pengamatan yang tetap `NA`, jumlah lajur, arah balik, jarak zona terhadap pin, konektivitas rute, tidak ada simpul berulang pada alternatif, dan kelompok sinyal. Build ulang jaringan, demand serta profil dari snapshot dan spesifikasi menghasilkan berkas identik.

Enam run berpasangan memakai SUMO 1.18.0, durasi 1.800 detik dan 1.010 kendaraan terjadwal: seed 1/42, masing-masing baseline, heuristik, dan hybrid tanpa API. Konservasi kendaraan, nol tabrakan/teleport, urutan fase, kuning/semua-merah serta jadwal baseline tetap diperiksa sepanjang run. Hybrid tanpa API menghasilkan ringkasan identik dengan heuristik.

| Seed | Tiba baseline → heuristik | Total jam-kendaraan baseline → heuristik | Waktu perjalanan trip selesai | Menunggu trip selesai |
| --- | ---: | ---: | ---: | ---: |
| 1 | 467 → 617 | 154,865 → 119,830 | 355,662 → 407,906 s | 93,443 → 58,180 s |
| 42 | 466 → 638 | 154,356 → 116,214 | 355,451 → 404,332 s | 89,622 → 55,133 s |

Waktu perjalanan rata-rata trip selesai justru lebih lama walaupun jumlah kendaraan tiba dan total jam-kendaraan membaik. Rute yang lebih panjang serta populasi trip selesai yang berbeda perlu dibaca bersama, tanpa menyimpulkan penyebab tunggal dari uji ini. UI menampilkan tradeoff tersebut, bukan menyatakan semua indikator membaik.

Spillback pada sensor dan durasi simpang terhalang tercatat nol pada kedua mode untuk dua seed. Uji ini tidak membuktikan bahwa sistem mencegah persimpangan tertutup pada kasus ini, dan tidak mengkalibrasi kondisi proyek yang sedang berlangsung. Model hambatan satu arah belum mereplikasi satu lajur bersama serta buka-tutup aktual. Bukti tersimpan pada `deploy/evidence/bina-validation.json`, dengan hasil mentah lokal di `output/bina-paired`.

Demo branch `llm` memilih `KATUP_CORRIDOR=bina_marga`. Hasil Kebon Sirih diperbarui melalui SUMO agar tetap dapat dibandingkan setelah perubahan signature. Provider LLM tetap nonaktif, tunnel dan service produksi dipertahankan.
