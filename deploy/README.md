# KATUP di VPS — SUMO-GUI langsung melalui browser

Instalasi yang diuji 2 November 2026: Ubuntu 22.04.5, 1 vCPU,
RAM 1,9 GiB, swap 4 GiB, disk kosong awal 124 GiB. Layanan game PHP
pada UDP 19132/19133 serta SSH tetap berjalan dengan PID yang sama.
Tidak dilakukan reboot, instalasi paket sistem, perubahan firewall, atau restart layanan lain.

## Pembaruan HTTPS melalui tunnel (2 November 2026)

Pemetaan port validasi 80/443 belum tersedia dari provider. Akses dengan sertifikat
tepercaya disediakan melalui Cloudflare Quick Tunnel, tanpa membuka port baru:

**https://created-predicted-victory-beliefs.trycloudflare.com**

Gunakan login yang sama. Alamat IP `https://163.52.135.171:8443` tetap memakai
sertifikat self-signed; tunnel tidak mengganti sertifikat pada alamat IP itu.
Koneksi browser ke Cloudflare memakai sertifikat publik tepercaya. Tunnel ke
origin juga memakai TLS, dengan sertifikat lokal diverifikasi menggunakan
`--origin-ca-pool` dan hostname `localhost`; verifikasi TLS tidak dinonaktifkan.
Login, cookie Secure/HttpOnly, pemeriksaan Origin, dan autentikasi VNC tetap aktif.

Quick Tunnel adalah akses sementara untuk pengujian. URL dapat berubah ketika
proses tunnel/VPS restart dan tidak memiliki jaminan uptime. Untuk alamat tetap,
gunakan named tunnel dengan akun Cloudflare serta domain milik pengguna.
Dokumentasi penyedia: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

Layanan `katup-tunnel.service` enabled dan otomatis dijalankan kembali. Perintah
berikut dijalankan dari direktori repository:

```bash
source deploy/env.sh
python deploy/access-url.py
journalctl --user -u katup-tunnel -f
systemctl --user status katup-tunnel
# Instalasi ulang opsional; tidak me-restart tunnel yang sudah hidup:
python deploy/install-tunnel.py
```

Binary cloudflared versi 2026.10.7 diunduh dari release resmi dan diverifikasi
SHA-256; terpasang di `../runtime/bin/cloudflared`. Prosedur update aplikasi
mempertahankan proses tunnel agar alamatnya tidak berubah pada update biasa.

Uji browser melalui hostname publik menggunakan verifikasi sertifikat aktif:

```bash
source deploy/env.sh
python deploy/tests/browser_smoke.py --url "$(python deploy/access-url.py)"
```

Uji lewat jaringan publik ini dilakukan oleh browser otomatis pada VPS; pengguna
masih perlu mencoba alamat baru dari laptop/HP. Bukti ada pada
`verification-https.json`. Browser tidak diberi opsi untuk melewati kesalahan
sertifikat.

## Akses dan login awal

- Alamat LAN: **https://192.168.28.56:8443**.
- Dari VPS sendiri: **https://127.0.0.1:8443**.
- Kandidat publik: **https://163.52.135.171:8443**, **belum berhasil diverifikasi**.
  Provider perlu meneruskan TCP `163.52.135.171:8443` ke `192.168.28.56:8443`
  dan mengizinkannya pada firewall provider. IP keluar saja tidak membuktikan
  pemetaan masuk. Jika port publik berbeda, gunakan port yang diberikan provider.
- HTTPS memakai sertifikat self-signed. Browser menampilkan peringatan kepercayaan.
  Domain dan sertifikat tepercaya dapat ditambahkan setelah domain/akses tersedia.
- Nama pengguna `katup`; kata sandi di berkas privat `../runtime/state/credentials.json`.
  Jalankan `cat ../runtime/state/credentials.json` dari repository melalui SSH
  milik administrator. Jangan commit atau salin berkas ini ke GitHub.
- Bila punya SSH publik yang sudah berfungsi, alternatif sementara dari laptop:
  `ssh -p PORT_SSH -L 8443:127.0.0.1:8443 agent@163.52.135.171`, lalu buka
  `https://localhost:8443`. Gunakan port SSH provider yang sebenarnya.

Pilih **KATUP — tiga agen** atau **Baseline — tanpa kendali KATUP**, tekan
**Mulai / Ganti skenario**. **Hentikan** menutup controller dan SUMO dalam satu
cgroup. Tidak ada simulasi kedua yang berjalan bersamaan. Semua pengguna melihat
dan dapat mengendalikan sesi yang sama. Opsi **Hanya lihat** berlaku pada browser
pengguna itu sendiri. Untuk HP, orientasi lanskap membantu membaca toolbar SUMO.

Peta, kendaraan, lampu, zoom, jeda, dan kontrol lainnya adalah SUMO-GUI asli,
dikirim melalui noVNC; tidak ada video atau pemutaran hasil lama. Waktu simulasi
berjalan hingga 1800 detik sesuai controller. Delay awal 1000 ms per langkah
(sekitar waktu nyata: satu sesi berlangsung 30 menit, bergantung beban), dapat diubah di toolbar SUMO.
Setelah selesai, tekan Mulai untuk sesi baru. Renderer memakai CPU Mesa llvmpipe;
1 CPU berbagi dengan layanan game, sehingga frame rate bisa turun.

## Lokasi dan layanan

Instalasi saat ini:

```text
/home/agent/Documents/Codex/2026-11-02-saya-ingin-kamu-langsung-membantu-memasang/
  Katup/                 repository dan deploy/
  runtime/venv/          Python 3.10, SUMO 1.28.0, TraCI 1.28.0
  runtime/root/          pustaka grafis dan utilitas Ubuntu yang diekstrak lokal
  runtime/novnc/         noVNC pada revisi novnc-revision.txt
  runtime/state/         kredensial, sertifikat, Xauthority, telemetri
```

Unit systemd pengguna berada di `~/.config/systemd/user/katup-*.service`:
`katup-display`, `katup-desktop`, `katup-vnc`, `katup-web`, `katup-simulation`.
Empat layanan pendukung enabled dan `loginctl show-user agent -p Linger`
menunjukkan `yes`: layanan pendukung dikonfigurasi hidup setelah reboot.
Simulasi dimulai melalui tombol; sesi penelitian tidak otomatis dimulai ulang
setelah reboot. Reboot sebenarnya belum diuji agar layanan lama tidak terganggu.

Dari direktori repository:

```bash
source deploy/env.sh
systemctl --user status katup-web katup-vnc katup-display
journalctl --user -u katup-web -f
journalctl --user -u katup-simulation -f
systemctl --user stop katup-simulation
systemctl --user restart katup-web
```

Restart seluruh susunan secara bersih:

```bash
source deploy/env.sh
systemctl --user stop katup-simulation katup-web katup-desktop katup-vnc katup-display
systemctl --user start katup-web
```

Log tersimpan di journal systemd. Berkas `runtime/state/telemetry.json` adalah
status terakhir, bukan sumber animasi. Status `running` berasal dari systemd;
telemetri yang masih ada sesudah berhenti adalah sampel terakhir.

## Batas jaringan dan autentikasi

Web HTTPS/WSS pada TCP 8443 memerlukan login. Sesi memakai cookie Secure,
HttpOnly, SameSite=Strict; endpoint kontrol dan WebSocket memeriksa Origin.
Login salah dibatasi per alamat. VNC dilindungi kata sandi terpisah dan hanya
mendengarkan `127.0.0.1:5905`; IPv6 VNC juga dinonaktifkan.
TraCI berjalan dalam network namespace privat bersama controller: hanya loopback
namespace tersebut yang aktif. Tidak ada port TraCI pada antarmuka VPS.
Xvfb menggunakan Xauthority dan `-nolisten tcp`. Jangan membuka port VNC/TraCI
pada panel provider.

## Perubahan terhadap proyek penelitian

`katup_controller.py` asli dan seluruh algoritma/ambang batas tidak diubah.
Launcher `deploy/run_controller.py` mengimpor controller tersebut, mengatur
working directory ke `progress_tahapan/05_visual_urban_enhancements`, menetapkan
SUMO_HOME, seed 42 yang sama untuk kedua skenario, delay GUI, ukuran jendela,
dan keluar bersih ketika simulasi selesai. Instrumentasi hanya mencatat jumlah
pemanggilan agen, posisi sampel kendaraan, mode, serta pengalihan rute.
Baseline tetap memantau lewat Agen Pengamat, tetapi tidak memanggil
`AgenKatup.apply_control` atau `AgenRute.guide_traffic`.

Path Windows pada default `build_network.py` tidak dipakai; file jaringan yang
sudah ada digunakan langsung. Xvfb lokal memiliki penggantian direktori
`xkbcomp` terkompilasi `/usr/bin` menjadi `.` agar dapat dijalankan tanpa sudo;
server diluncurkan dari direktori utilitas privat. Tidak ada binary sistem yang
berubah. Fontconfig memakai konfigurasi serta font lokal untuk menghindari GUI
gagal ketika mesin tidak memiliki font sistem.

## Pemasangan ulang

Untuk Ubuntu 22.04 dengan Python 3.10, git, apt index, openssl, dan dukungan
unprivileged user/network namespaces:

```bash
python3 deploy/bootstrap.py
```

Bootstrap mengunduh paket Ubuntu, memeriksa checksum dari apt, mengekstraknya
ke `../runtime/root`, memasang Python dependencies terkunci, menyiapkan noVNC,
login, TLS lokal, dan unit systemd pengguna. Tidak menjalankan `apt install`.
Pengaktifan linger memerlukan kebijakan loginctl yang mengizinkan pengguna
sendiri; pada VPS saat ini langkah tersebut berhasil tanpa sudo.
Bootstrap disediakan untuk reproduksi; pengujian aktual menggunakan susunan
lokal yang sama, bukan pengujian pemasangan baru pada VPS kedua.

## Pengujian yang sudah dilakukan

- Browser Chromium pada VPS: login, noVNC/WebSocket, peta SUMO asli tampil.
- Waktu simulasi meningkat dan posisi kendaraan yang sama berubah.
- Baseline: pengamat aktif; katup/rute nol, pengalihan nol.
- KATUP: ketiga agen dipanggil, KATUP_ACTIVE terlihat, pengalihan berhasil.
- Kedua skenario dijalankan hingga 1800 langkah dan keluar bersih (lihat JSON).
- Berganti baseline ke KATUP, hentikan, dan mulai ulang lewat tombol berhasil.
- Tampilan HP 390×844 dengan emulasi sentuh dan koneksi noVNC berhasil.
- Tidak ada error JavaScript pada pengujian tersebut.
- Restart layanan KATUP dan login ulang diuji; layanan lama tetap hidup.
- Akses laptop/HP dari internet **belum diuji berhasil**; NAT masih diperlukan.

Bukti: `verification-vps.json`, `full-runs.json`, dan `evidence/`.
Jumlah pemanggilan dalam telemetri diambil saat evaluasi pengamat, sehingga
angka agen katup/rute dapat tertinggal satu langkah dari langkah terakhir.
Screenshot adalah bukti uji; aplikasi tidak menggunakannya untuk menampilkan simulasi.

## Deployment GitHub Actions

Workflow `.github/workflows/deploy-vps.yml` dijalankan manual; GitHub Actions
hanya melakukan SSH deployment, tidak menjadi server SUMO. Siapkan environment
`katup-vps`, Secrets:

- `KATUP_SSH_HOST`: host/IP SSH publik yang dapat dicapai GitHub runner.
- `KATUP_SSH_PORT`: port SSH publik provider.
- `KATUP_SSH_USER`: `agent` atau akun instalasi yang sama.
- `KATUP_SSH_PRIVATE_KEY`: kunci deployment khusus yang diizinkan pada VPS.
- `KATUP_SSH_KNOWN_HOSTS`: host key SSH yang sudah diverifikasi lewat jalur tepercaya.

Variable `KATUP_DEPLOY_PATH` diisi path lengkap direktori repository di atas.
Jangan menyalin private key akun yang sudah ada ke GitHub. Kunci deployment
khusus belum dibuat/dipasang karena akses SSH publik dan Secrets belum tersedia.

Workflow meng-update branch `deploy/katup-vps` dengan fast-forward saja,
menolak working tree yang berubah, memperbarui dependency, dan me-restart
layanan KATUP. Tidak memakai force-push/reset. Repository ini publik, jadi fetch
pada VPS tidak memerlukan token repository. Workflow belum dijalankan karena
Secrets dan jalur SSH publik belum dikonfigurasi. Setelah workflow terdapat di
branch default melalui review tim, tombol manual tersedia di tab Actions.

Untuk mengulangi uji browser lokal (uji ini mengganti/menghentikan sesi bersama):

```bash
source deploy/env.sh
python -m pip install -r deploy/tests/requirements.txt
python -m playwright install chromium --only-shell
python deploy/tests/browser_smoke.py --allow-self-signed
```

Pada instalasi tanpa pustaka browser sistem, Chromium juga memerlukan
`libatk1.0-0`, `libatk-bridge2.0-0`, `libxcomposite1`, dan `libatspi2.0-0`.
Pustaka tersebut sudah diekstrak lokal pada VPS ini. Bukti tambahan kontrol
SUMO melalui noVNC: tombol jeda membekukan waktu simulasi, zoom mengubah
viewport, dan tombol lanjut membuat waktu kembali bertambah.

Catatan uji HTTPS: noVNC mencatat penolakan izin clipboard pada browser otomatis.
Hal ini tidak menghalangi login, tampilan, input desktop, atau kontrol simulasi;
bukan kesalahan sertifikat. Tidak ada exception halaman pada uji tersebut.

## Tampilan saat sesi selesai

Sesi tetap berakhir pada 1800 langkah sesuai controller. Sesudah selesai atau
dihentikan, halaman menampilkan petunjuk dan tombol Mulai di area desktop,
sehingga pengguna tidak hanya melihat desktop hitam. Saat mulai, halaman
menampilkan “Menyiapkan SUMO-GUI” hingga telemetri pertama tersedia. Status
berhenti tidak menampilkan jumlah kendaraan lama sebagai status langsung.

Kecepatan awal diubah dari 100 ms menjadi 1000 ms per langkah agar sesi tidak
habis dalam sekitar 3 menit. Algoritma, ambang kendali, dan jumlah langkah
penelitian tetap sama. Pengguna masih dapat menyesuaikan Delay di toolbar SUMO.
