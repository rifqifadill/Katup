# Simulasi Sistem KATUP (Kendali Antrean Titik Urai Kemacetan Perkotaan)

Proyek simulasi mikroskopik berbasis **Eclipse SUMO** dan **Python (TraCI)** sesuai rancangan pada **Laporan KATUP Bab 1 & Bab 2** (Tim 3 Teknik Komputer UI).

---

## 🌟 Pembaruan Visual & Tata Kota Realistis

Proyek ini telah diperbarui dengan visualisasi perkotaan modern:
1. **Jaringan 6 Simpang Terintegrasi**:
   - **Simpang 1 (Simpang 4 Barat)**: Pintu masuk arteri hunian/suburban barat.
   - **Simpang 2 (Simpang 4 Titik Urai)**: Simpang bersinyal lampu lalu lintas yang dimonitor dan dikendalikan sistem KATUP.
   - **Simpang 3 (Simpang 4 Boulevard Utara)**: Simpang koridor utara dan awal jalan pintas.
   - **Simpang 4 (Simpang 4 Kawasan Selatan)**: Simpang lingkar selatan dan kawasan pergudangan/terminal.
   - **Simpang 5 (Simpang 4 Bypass Timur)**: Simpang pertemuan rute bypass dengan akses tol timur.
   - **Simpang 6 (Simpang 4 Gerbang Timur CBD)**: Simpang hilir menuju kawasan pusat bisnis (CBD).
2. **Model Kendaraan Nyata (*Vehicle Quality 2D Realistic*)**:
   - Bentuk mobil menyerupai mobil sungguhan lengkap dengan kontur bodi, kap mesin, atap kaca, lampu depan (headlights), lampu rem (brakelights menyala saat melambat), lampu sein (blinkers berkedip saat belok), dan roda hitam.
   - Ragam tipe: *Sedan Metalik*, *Sedan Eksekutif*, *Hatchback Compact*, *Family SUV / Wagon*, *Taksi Kuning*, *Delivery Van*, *Bus Kota*, dan *Truk Logistik*.
   - Mobil yang dialihkan oleh sistem KATUP berubah warna menjadi **HIJAU NEON** agar tampak kontras dan mudah diamati.
3. **Tata Lingkungan (*Realistic Environment Polygons*)**:
   - Latar belakang rumput alami perkotaan (bukan putih flat kosong).
   - Aspal jalan gelap dengan marka lajur (*lane borders*) dan marka penyeberangan (*Zebra Cross*).
   - Trotoar paving pejalan kaki (*granite sidewalks & curbs*) di sepanjang jalan.
   - Kanal/sungai air biru melintang kota dengan jembatan layang.
   - Taman Kota Besar Titik Urai (*Grand Urban Park*) lengkap dengan danau dekoratif, jalur pedestrian, dan pepohonan rindang.
   - Blok gedung bertingkat 3D (menara perkantoran, pusat komando ITS, hotel, mall CBD, ruko).
   - Visualisasi realistis area galian proyek (penyebab bottleneck) dengan barikade safety hazard oranye, parit galian aspal, dan ekskavator proyek.
   - Papan elektronik VMS (*Variable Message Sign*) digital di hulu titik urai.

---

## 📁 Struktur Berkas

| Berkas | Deskripsi |
| :--- | :--- |
| `katup.net.xml` | Jaringan jalan tervalidasi dengan 6 persimpangan, ruas bottleneck (1 lajur), dan Bypass Utara (2 lajur). |
| `katup.rou.xml` | Definisi tipe mobil realistis (guiShape sedan, hatchback, SUV, van, bus) & rute lintas simpang. |
| `katup.poly.xml` | File bentuk tambahan: Trotoar, kanal air, taman kota, bangunan 3D, marka zebra cross, dan area proyek. |
| `katup.sumocfg` | File konfigurasi SUMO yang menggabungkan net, rute, visualisasi lingkungan, dan view. |
| `katup.view.xml` | Skema tampilan realistis SUMO-GUI: latar rumput, aspal jalan, dan kualitas render kendaraan tingkat tinggi. |
| `katup_controller.py` | **Skrip Python TraCI** yang mengintegrasikan 3 Agen Cerdas: **Agen Pengamat**, **Agen Katup**, dan **Agen Rute**. |
| `katup.nod.xml`, `katup.edg.xml`, `katup.con.xml` | File sumber topologi jaringan jalan. |
| `build_network.py` | Skrip automasi Python untuk mengompilasi ulang seluruh file konfigurasi dan jaringan. |

---

## 🚀 Cara Menjalankan Simulasi

Buka PowerShell / Terminal di dalam folder repositori proyek:

### 1. Menjalankan Sistem KATUP Penuh (Skenario 3 - 3 Agen Cerdas Aktif)
Jalankan perintah berikut:
```powershell
python katup_controller.py
```
- Jendela **SUMO-GUI** akan otomatis terbuka dan langsung berjalan.
- **Agen Pengamat** memantau ruas sebelum bottleneck.
- Begitu antrean padat, **Agen Katup** akan membatasi lampu hijau Barat, dan **Agen Rute** akan mengalihkan sebagian mobil ke jalan pintas Utara (**mobil yang dialihkan berwarna HIJAU**).
- Terminal akan mencetak status antrean, kecepatan rata-rata, dan status VMS secara *real-time*.

### 2. Menjalankan Baseline Tanpa Kendali (Skenario 2 - Untuk Komparasi)
```powershell
python katup_controller.py baseline
```
- Menunjukkan bagaimana galian proyek menyebabkan kemacetan parah (antrean 100%) dan mengunci persimpangan hulu (*gridlock*).

### 3. Membuka Peta Simulasi Langsung di SUMO-GUI (Manual)
```powershell
sumo-gui -c katup.sumocfg
```
Lalu tekan tombol **Play (segitiga hijau)** di toolbar atas.
