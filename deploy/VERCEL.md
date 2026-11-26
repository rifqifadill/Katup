# Deploy frontend KATUP ke Vercel

Vercel hanya menjalankan frontend HTML, CSS, JavaScript, dan aset visual KATUP. SUMO, TraCI, FastAPI, serta WebSocket tetap berjalan di VPS.

1. Import repository `rifqifadill/Katup` ke Vercel dan biarkan Root Directory di `/`.
2. Pada Environment Variables, tambahkan `KATUP_API_BASE` berisi alamat HTTPS tetap backend VPS, tanpa `/` di akhir, contoh `https://api.katup.example.com`.
3. Gunakan nama project `katup` jika tersedia agar alamatnya menjadi `https://katup.vercel.app`, karena nama tersebut bergantung pada ketersediaan Vercel.
4. Pada VPS public, jalankan `sudo systemctl edit katup-dashboard`, isi `[Service]` lalu `Environment=KATUP_FRONTEND_ORIGINS=https://katup.vercel.app`, simpan, jalankan `sudo systemctl daemon-reload` dan `sudo systemctl restart katup-dashboard`.
5. Deploy ulang Vercel. Browser akan mengambil peta, telemetry, hasil simulasi, dan WebSocket dari alamat `KATUP_API_BASE`.

Backend harus memiliki HTTPS dan WebSocket publik yang stabil. Quick Tunnel cocok untuk uji singkat, tetapi alamatnya dapat berubah dan tidak cocok dijadikan `KATUP_API_BASE` tetap.
