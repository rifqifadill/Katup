"""
================================================================================
SISTEM KATUP (Kendali Antrean Titik Urai Kemacetan Perkotaan)
Implementasi 3 Agen Cerdas:
1. Agen Pengamat: Monitoring panjang antrean, densitas, dan kecepatan rata-rata
2. Agen Katup: Modulasi adaptif durasi lampu lalu lintas di persimpangan titik urai
3. Agen Rute: Pengalihan dinamis sebagian arus ke rute alternatif (Bypass) via VMS
================================================================================
"""

import os
import sys
import time

# Pastikan SUMO tools ada dalam sys.path
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    sys.exit("Harap pastikan environment variable SUMO_HOME sudah diatur.")

import traci

# Konfigurasi Parameter Sistem KATUP
TLS_ID = "titik_urai"
EDGE_PRE_BOTTLENECK = "edge_pre_bottle"
EDGE_INBOUND_WEST = "edge_W2J"
BYPASS_EDGES = ["edge_W2J", "edge_J2N", "edge_alt_1", "edge_alt_2", "edge_post_merge"]

# Ambang Batas (Threshold) Sesuai Bab 1 & 2 Laporan KATUP
MAX_QUEUE_CAPACITY = 18    # Jumlah mobil antre yang mendekati simpang hulu
THRESHOLD_HIGH_RISK = 0.60 # >= 60% - 80% (Kondisi Risiko Tinggi Gridlock)
THRESHOLD_NORMAL = 0.30    # <= 30% - 50% (Kondisi Normal)
RECOVERY_CYCLES_NEEDED = 2 # Butuh 2 siklus evaluasi berturut-turut untuk kembali ke Normal


class AgenPengamat:
    """Agen 1: Memantau kondisi lalu lintas pada segmen sebelum penyempitan jalan."""
    def __init__(self, edge_id):
        self.edge_id = edge_id
        self.consecutive_normal_count = 0

    def evaluate(self):
        # Ambil metrik dari SUMO
        veh_count = traci.edge.getLastStepVehicleNumber(self.edge_id)
        halting_vehs = traci.edge.getLastStepHaltingNumber(self.edge_id)
        occupancy = traci.edge.getLastStepOccupancy(self.edge_id)
        mean_speed = traci.edge.getLastStepMeanSpeed(self.edge_id)
        speed_kmh = mean_speed * 3.6

        # Rasio jumlah kendaraan aktif terhadap kapasitas ruas (185m, 2 lajur)
        density_ratio = min(1.0, veh_count / MAX_QUEUE_CAPACITY)

        # Kondisi risiko tinggi: antrean mendekati kapasitas ATAU macet merayap (speed <= 15 km/h)
        is_high_risk = (density_ratio >= THRESHOLD_HIGH_RISK) or (speed_kmh <= 15.0 and density_ratio >= 0.40)
        is_safe = (density_ratio <= THRESHOLD_NORMAL) and (speed_kmh >= 25.0 or veh_count <= 4)

        if is_safe:
            self.consecutive_normal_count += 1
        else:
            self.consecutive_normal_count = 0

        can_return_to_normal = (self.consecutive_normal_count >= RECOVERY_CYCLES_NEEDED)

        return {
            "veh_count": veh_count,
            "halting": halting_vehs,
            "occupancy": occupancy * 100,
            "mean_speed_kmh": speed_kmh,
            "density_ratio": density_ratio * 100,
            "is_high_risk": is_high_risk,
            "can_return_to_normal": can_return_to_normal
        }


class AgenKatup:
    """Agen 2: Mengatur modulasi durasi sinyal lampu lalu lintas."""
    def __init__(self, tls_id):
        self.tls_id = tls_id
        self.mode = "NORMAL"

    def apply_control(self, is_high_risk, can_return_to_normal):
        current_phase = traci.trafficlight.getPhase(self.tls_id)

        if self.mode == "NORMAL" and is_high_risk:
            self.mode = "KATUP_ACTIVE"
            print("\n>>> [AGEN KATUP] Mode Pengendalian Penyempitan DIAKTIFKAN!")
            print("    Durasi lampu hijau Barat (menuju bottleneck) dipersingkat guna cegah gridlock.")

        elif self.mode == "KATUP_ACTIVE" and can_return_to_normal:
            self.mode = "NORMAL"
            print("\n>>> [AGEN KATUP] Antrean terkendali. Kembali ke MODE NORMAL.")

        # Fase 3 adalah fase hijau Barat (inbound W)
        # Jika KATUP aktif dan sedang fase 3 melebihi durasi aman (misal 10s), paksa lanjut ke fase kuning
        if self.mode == "KATUP_ACTIVE":
            if current_phase == 3:
                spent_time = traci.trafficlight.getSpentDuration(self.tls_id)
                if spent_time >= 10:  # Batasi hijau arah bottleneck hanya 10 detik
                    traci.trafficlight.setPhase(self.tls_id, 4)  # Pindah ke kuning


class AgenRute:
    """Agen 3: Mengalihkan kendaraan ke rute alternatif (Bypass) via simulasi VMS."""
    def __init__(self, inbound_edge, bypass_route):
        self.inbound_edge = inbound_edge
        self.bypass_route = bypass_route
        self.reroute_counter = 0

    def guide_traffic(self, is_active):
        if not is_active:
            return

        # Ambil daftar kendaraan yang sedang mendekati persimpangan pada edge barat
        vehs = traci.edge.getLastStepVehicleIDs(self.inbound_edge)
        
        # Alihkan 50% dari kendaraan yang mendekat ke rute alternatif
        for v in vehs:
            # Hanya alihkan jika belum pernah dialihkan
            route = traci.vehicle.getRoute(v)
            if len(route) > 0 and route[1] != "edge_J2N":
                # Pengalihan proporsional bergantian (1 dari 2 mobil)
                if int(v.split(".")[-1]) % 2 == 0:
                    try:
                        traci.vehicle.setRoute(v, self.bypass_route)
                        # Warnai mobil yang dialihkan dengan warna HIJAU agar terlihat jelas di GUI
                        traci.vehicle.setColor(v, (0, 255, 0, 255))
                        self.reroute_counter += 1
                    except Exception:
                        pass


def run_simulation(enable_katup=True, use_gui=True):
    mode_str = "DENGAN SISTEM KATUP (Skenario 3)" if enable_katup else "BASELINE TANPA KENDALI (Skenario 2)"
    binary = "sumo-gui" if use_gui else "sumo"
    print(f"\n==================================================")
    print(f" Memulai Simulasi: {mode_str} [{binary}]")
    print(f"==================================================\n")

    # Jalankan SUMO
    sumo_cmd = [
        binary,
        "-c", "katup.sumocfg",
        "--start", "true"
    ]
    traci.start(sumo_cmd)

    pengamat = AgenPengamat(EDGE_PRE_BOTTLENECK)
    katup = AgenKatup(TLS_ID)
    rute = AgenRute(EDGE_INBOUND_WEST, BYPASS_EDGES)

    step = 0
    try:
        while step < 1800:  # 1800 detik (30 menit simulasi)
            traci.simulationStep()
            step += 1

            # Evaluasi setiap detik
            metrics = pengamat.evaluate()

            if enable_katup:
                katup.apply_control(metrics["is_high_risk"], metrics["can_return_to_normal"])
                rute.guide_traffic(katup.mode == "KATUP_ACTIVE")

            # Cetak telemetri setiap 15 detik
            if step % 15 == 0:
                status_katup = katup.mode if enable_katup else "DISABLED"
                vms_status = "AKTIF (Bypass Hijau)" if (enable_katup and katup.mode == "KATUP_ACTIVE") else "OFF"
                print(f"[Detik {step:4d}] Kendaraan: {metrics['veh_count']:2d} mobil ({metrics['density_ratio']:5.1f}%) | "
                      f"Kecepatan: {metrics['mean_speed_kmh']:4.1f} km/h | KATUP: {status_katup:<12} | VMS: {vms_status}")

    except traci.exceptions.FatalTraCIError:
        print("\nSimulasi ditutup oleh pengguna.")
    finally:
        try:
            traci.close()
        except Exception:
            pass
        print("\nSimulasi selesai.")


if __name__ == "__main__":
    enable = True
    gui = True
    args = [a.lower() for a in sys.argv[1:]]
    if "baseline" in args or "no-katup" in args or "0" in args:
        enable = False
    if "--nogui" in args or "-nogui" in args:
        gui = False
    run_simulation(enable_katup=enable, use_gui=gui)
