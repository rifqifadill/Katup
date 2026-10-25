import os
import subprocess

def generate_all_simulation_files(sim_dir=r"C:\Users\rifqi\KATUP_Simulation"):
    os.makedirs(sim_dir, exist_ok=True)
    print("=" * 60)
    print("Membangun Jaringan Simulasi KATUP Modern & Realistis...")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1. NODES FILE (katup.nod.xml)
    # -------------------------------------------------------------
    nod_content = """<?xml version="1.0" encoding="UTF-8"?>
<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <!-- Pintu Masuk Arteri Luar Kota (Barat) -->
    <node id="node_W_far" x="-550.0" y="0.0" type="priority"/>
    
    <!-- SIMPANG 1: Simpang 4 Barat (Gerbang Masuk Kawasan Permukiman & Arteri Barat) -->
    <node id="node_W" x="-300.0" y="0.0" type="priority"/>
    <node id="node_NW" x="-300.0" y="150.0" type="priority"/>
    <node id="node_SW" x="-300.0" y="-150.0" type="priority"/>
    
    <!-- SIMPANG 2: Simpang 4 Titik Urai (Simpang Bersinyal Terkendali KATUP) -->
    <node id="titik_urai" x="0.0" y="0.0" type="traffic_light"/>
    
    <!-- SIMPANG 3: Simpang 4 Boulevard Utara -->
    <node id="node_N" x="0.0" y="150.0" type="priority"/>
    <node id="node_N_far" x="0.0" y="320.0" type="priority"/>
    
    <!-- SIMPANG 4: Simpang 4 Kawasan Selatan (Terminal & Lingkar Selatan) -->
    <node id="node_S" x="0.0" y="-150.0" type="priority"/>
    <node id="node_S_far" x="0.0" y="-320.0" type="priority"/>
    
    <!-- KORIDOR PENYEMPITAN / BOTTLENECK (Galian Proyek Saluran Air) -->
    <node id="node_bottle_in" x="200.0" y="0.0" type="priority"/>
    <node id="node_bottle_out" x="350.0" y="0.0" type="priority"/>
    <node id="node_merge" x="450.0" y="0.0" type="priority"/>
    
    <!-- SIMPANG 5: Simpang 4 Bypass Timur (Pertemuan Bypass & Akses Tol Timur) -->
    <node id="node_alt_corner" x="450.0" y="150.0" type="priority"/>
    <node id="node_NE" x="450.0" y="320.0" type="priority"/>
    <node id="node_NE_east" x="650.0" y="150.0" type="priority"/>
    
    <!-- SIMPANG 6: Simpang 4 Gerbang Timur CBD (Pusat Kota) -->
    <node id="node_E" x="650.0" y="0.0" type="priority"/>
    <node id="node_SE" x="650.0" y="-150.0" type="priority"/>
    <node id="node_CBD" x="850.0" y="0.0" type="priority"/>
</nodes>
"""
    with open(os.path.join(sim_dir, "katup.nod.xml"), "w", encoding="utf-8") as f:
        f.write(nod_content)
    print("[OK] [1/6] katup.nod.xml berhasil dibuat (6 simpang kota).")

    # -------------------------------------------------------------
    # 2. EDGES FILE (katup.edg.xml)
    # -------------------------------------------------------------
    edg_content = """<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <!-- ============================================================== -->
    <!-- KORIDOR UTAMA SISTEM KATUP (Kompatibel 100% dengan Controller) -->
    <!-- ============================================================== -->
    <edge id="edge_W2J" from="node_W" to="titik_urai" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_J2W" from="titik_urai" to="node_W" priority="3" numLanes="2" speed="13.89"/>
    
    <edge id="edge_N2J" from="node_N" to="titik_urai" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_J2N" from="titik_urai" to="node_N" priority="2" numLanes="2" speed="11.11"/>
    
    <edge id="edge_S2J" from="node_S" to="titik_urai" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_J2S" from="titik_urai" to="node_S" priority="2" numLanes="2" speed="11.11"/>
    
    <edge id="edge_pre_bottle" from="titik_urai" to="node_bottle_in" priority="3" numLanes="2" speed="13.89"/>
    <!-- BOTTLENECK (Galian Proyek): 1 lajur sempit 12 km/h -->
    <edge id="edge_bottleneck" from="node_bottle_in" to="node_bottle_out" priority="3" numLanes="1" speed="3.50"/>
    <edge id="edge_bottle_exit" from="node_bottle_out" to="node_merge" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_post_merge" from="node_merge" to="node_E" priority="3" numLanes="2" speed="13.89"/>
    
    <!-- Rute Alternatif Bypass Utara -->
    <edge id="edge_alt_1" from="node_N" to="node_alt_corner" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_alt_2" from="node_alt_corner" to="node_merge" priority="2" numLanes="2" speed="11.11"/>
    
    <!-- ============================================================== -->
    <!-- JARINGAN PERKOTAAN & SIMPANG PELENGKAP LAINNYA                 -->
    <!-- ============================================================== -->
    <!-- Ekstensi Koridor Barat (Simpang 4 Barat) -->
    <edge id="edge_W_far2W" from="node_W_far" to="node_W" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_W2W_far" from="node_W" to="node_W_far" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_NW2W" from="node_NW" to="node_W" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_W2NW" from="node_W" to="node_NW" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_SW2W" from="node_SW" to="node_W" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_W2SW" from="node_W" to="node_SW" priority="2" numLanes="2" speed="11.11"/>
    
    <!-- Lingkar Utara (Boulevard & Akses Tol Timur) -->
    <edge id="edge_N_far2N" from="node_N_far" to="node_N" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_N2N_far" from="node_N" to="node_N_far" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_NW2N" from="node_NW" to="node_N" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_N2NW" from="node_N" to="node_NW" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_NE2alt" from="node_NE" to="node_alt_corner" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_alt2NE" from="node_alt_corner" to="node_NE" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_alt2NE_east" from="node_alt_corner" to="node_NE_east" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_NE_east2alt" from="node_NE_east" to="node_alt_corner" priority="2" numLanes="2" speed="13.89"/>
    
    <!-- Lingkar Selatan (Kawasan Pemukiman & Pergudangan) -->
    <edge id="edge_S_far2S" from="node_S_far" to="node_S" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_S2S_far" from="node_S" to="node_S_far" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_SW2S" from="node_SW" to="node_S" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_S2SW" from="node_S" to="node_SW" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_S2SE" from="node_S" to="node_SE" priority="2" numLanes="2" speed="13.89"/>
    <edge id="edge_SE2S" from="node_SE" to="node_S" priority="2" numLanes="2" speed="13.89"/>
    
    <!-- Koridor Timur Menuju CBD (Pusat Kota) -->
    <edge id="edge_E2CBD" from="node_E" to="node_CBD" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_CBD2E" from="node_CBD" to="node_E" priority="3" numLanes="2" speed="13.89"/>
    <edge id="edge_NE_east2E" from="node_NE_east" to="node_E" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_E2NE_east" from="node_E" to="node_NE_east" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_SE2E" from="node_SE" to="node_E" priority="2" numLanes="2" speed="11.11"/>
    <edge id="edge_E2SE" from="node_E" to="node_SE" priority="2" numLanes="2" speed="11.11"/>
</edges>
"""
    with open(os.path.join(sim_dir, "katup.edg.xml"), "w", encoding="utf-8") as f:
        f.write(edg_content)
    print("[OK] [2/6] katup.edg.xml berhasil dibuat.")

    # -------------------------------------------------------------
    # 3. CONNECTIONS FILE (katup.con.xml)
    # -------------------------------------------------------------
    con_content = """<?xml version="1.0" encoding="UTF-8"?>
<connections xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/connections_file.xsd">
    <!-- Penyatuan 2 lajur menuju penyempitan 1 lajur (Bottleneck Galian) -->
    <connection from="edge_pre_bottle" to="edge_bottleneck" fromLane="0" toLane="0"/>
    <connection from="edge_pre_bottle" to="edge_bottleneck" fromLane="1" toLane="0"/>
    
    <!-- Simpang Titik Urai (Arah Masuk Barat): Lurus (Bottleneck), Belok Kiri (Bypass), Belok Kanan (Selatan) -->
    <connection from="edge_W2J" to="edge_pre_bottle" fromLane="0" toLane="0"/>
    <connection from="edge_W2J" to="edge_pre_bottle" fromLane="1" toLane="1"/>
    <connection from="edge_W2J" to="edge_J2N" fromLane="0" toLane="0"/>
    <connection from="edge_W2J" to="edge_J2N" fromLane="1" toLane="1"/>
    <connection from="edge_W2J" to="edge_J2S" fromLane="0" toLane="0"/>
</connections>
"""
    with open(os.path.join(sim_dir, "katup.con.xml"), "w", encoding="utf-8") as f:
        f.write(con_content)
    print("[OK] [3/6] katup.con.xml berhasil dibuat.")

    # -------------------------------------------------------------
    # 4. BUILD NETWORK WITH NETCONVERT (katup.net.xml)
    # -------------------------------------------------------------
    net_file = os.path.join(sim_dir, "katup.net.xml")
    cmd = [
        "netconvert",
        "--node-files", os.path.join(sim_dir, "katup.nod.xml"),
        "--edge-files", os.path.join(sim_dir, "katup.edg.xml"),
        "--connection-files", os.path.join(sim_dir, "katup.con.xml"),
        "--output-file", net_file,
        "--offset.disable-normalization", "true",
        "--tls.allred.time", "2",
        "--tls.yellow.time", "3"
    ]
    subprocess.run(cmd, check=True)
    print("[OK] [4/6] katup.net.xml berhasil dikompilasi dengan netconvert.")

    # -------------------------------------------------------------
    # 5. POLYGONS & ENVIRONMENT (katup.poly.xml)
    # Pinggir jalan tidak flat putih: Rumput, trotoar, gedung, taman,
    # kanal air, zona galian proyek, dan marka jalan.
    # -------------------------------------------------------------
    poly_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                  '<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">']

    # --- KANAL / SUNGAI KOTA (Kanal Air Biru di x = 185 s.d 205) ---
    poly_lines.append('    <!-- Kanal Sungai Kota melintang Utara-Selatan -->')
    poly_lines.append('    <poly id="water_canal" color="45,130,195" fill="true" layer="-2" shape="186,-350 204,-350 204,350 186,350"/>')
    poly_lines.append('    <poly id="canal_bank_west" color="170,178,185" fill="true" layer="-1.5" shape="183,-350 186,-350 186,350 183,350"/>')
    poly_lines.append('    <poly id="canal_bank_east" color="170,178,185" fill="true" layer="-1.5" shape="204,-350 207,-350 207,350 204,350"/>')

    # --- TAMAN KOTA BESAR TITIK URAI (Grand Urban Park di Antara Titik Urai & Bottleneck) ---
    poly_lines.append('    <!-- Taman Kota Titik Urai (Ruang Terbuka Hijau & Danau Rekreasi) -->')
    poly_lines.append('    <poly id="park_central_lawn" color="36,98,42" fill="true" layer="-1" shape="25,18 175,18 175,135 25,135"/>')
    poly_lines.append('    <poly id="park_central_pond" color="50,140,205" fill="true" layer="-0.5" shape="80,50 120,50 125,95 75,95"/>')
    poly_lines.append('    <poly id="park_walkway_1" color="220,215,200" fill="true" layer="-0.4" shape="25,72 175,72 175,76 25,76"/>')
    poly_lines.append('    <poly id="park_walkway_2" color="220,215,200" fill="true" layer="-0.4" shape="98,18 102,18 102,135 98,135"/>')
    # Pohon-pohon taman
    poly_lines.append('    <poly id="tree_1" color="20,70,25" fill="true" layer="0" shape="45,35 55,35 58,45 42,45"/>')
    poly_lines.append('    <poly id="tree_2" color="22,78,28" fill="true" layer="0" shape="140,35 152,35 155,47 138,47"/>')
    poly_lines.append('    <poly id="tree_3" color="20,70,25" fill="true" layer="0" shape="45,105 55,105 58,118 42,118"/>')
    poly_lines.append('    <poly id="tree_4" color="22,78,28" fill="true" layer="0" shape="140,105 152,105 155,118 138,118"/>')

    # --- TAMAN SELATAN (Area Rekreasi Hijau) ---
    poly_lines.append('    <poly id="park_south_lawn" color="36,98,42" fill="true" layer="-1" shape="25,-18 175,-18 175,-135 25,-135"/>')
    poly_lines.append('    <poly id="tree_s1" color="22,78,28" fill="true" layer="0" shape="50,-60 62,-60 65,-72 48,-72"/>')
    poly_lines.append('    <poly id="tree_s2" color="20,70,25" fill="true" layer="0" shape="135,-60 148,-60 150,-72 132,-72"/>')

    # --- TROTOAR PEJALAN KAKI (Paved Granite Sidewalks sepanjang jalan) ---
    poly_lines.append('    <!-- Trotoar Paving Sepanjang Koridor Utama & Bypass -->')
    # Koridor Barat (edge_W2J)
    poly_lines.append('    <poly id="sw_W_north" color="200,205,210" fill="true" layer="-0.8" shape="-300,7 -15,7 -15,11 -300,11"/>')
    poly_lines.append('    <poly id="sw_W_south" color="200,205,210" fill="true" layer="-0.8" shape="-300,-7 -15,-7 -15,-11 -300,-11"/>')
    # Koridor Pre-Bottleneck
    poly_lines.append('    <poly id="sw_pre_north" color="200,205,210" fill="true" layer="-0.8" shape="15,7 185,7 185,11 15,11"/>')
    poly_lines.append('    <poly id="sw_pre_south" color="200,205,210" fill="true" layer="-0.8" shape="15,-7 185,-7 185,-11 15,-11"/>')
    # Koridor Pasca Bottleneck s.d Simpang Timur
    poly_lines.append('    <poly id="sw_exit_north" color="200,205,210" fill="true" layer="-0.8" shape="350,7 635,7 635,11 350,11"/>')
    poly_lines.append('    <poly id="sw_exit_south" color="200,205,210" fill="true" layer="-0.8" shape="450,-7 635,-7 635,-11 450,-11"/>')
    # Trotoar Bypass Utara
    poly_lines.append('    <poly id="sw_alt_north" color="200,205,210" fill="true" layer="-0.8" shape="15,157 435,157 435,161 15,161"/>')
    poly_lines.append('    <poly id="sw_alt_south" color="200,205,210" fill="true" layer="-0.8" shape="15,143 435,143 435,139 15,139"/>')

    # --- AREA GALIAN PROYEK / BOTTLENECK (Visual Realistis Zona Pekerjaan Jalan) ---
    poly_lines.append('    <!-- Area Galian Proyek Saluran Air (Penyebab Bottleneck) -->')
    # Zona galian sisi utara lajur bottleneck (menutup 1 lajur)
    poly_lines.append('    <poly id="galian_base" color="70,55,45" fill="true" layer="-0.2" shape="200,1 350,1 350,7 200,7"/>')
    poly_lines.append('    <poly id="galian_trench" color="45,35,30" fill="true" layer="-0.1" shape="210,2 340,2 340,6 210,6"/>')
    # Pagar barikade oranye/putih safety hazard
    poly_lines.append('    <poly id="hazard_strip_1" color="235,120,20" fill="true" layer="0.2" shape="200,0.5 350,0.5 350,1.2 200,1.2"/>')
    poly_lines.append('    <poly id="hazard_marker_1" color="255,200,0" fill="true" layer="0.3" shape="220,1.2 230,1.2 230,3.5 220,3.5"/>')
    poly_lines.append('    <poly id="hazard_marker_2" color="255,200,0" fill="true" layer="0.3" shape="270,1.2 280,1.2 280,3.5 270,3.5"/>')
    poly_lines.append('    <poly id="hazard_marker_3" color="255,200,0" fill="true" layer="0.3" shape="320,1.2 330,1.2 330,3.5 320,3.5"/>')
    # Alat Berat (Ekskavator Proyek Kuning)
    poly_lines.append('    <poly id="excavator_body" color="230,140,15" fill="true" layer="0.4" shape="255,2.5 267,2.5 267,5.5 255,5.5"/>')
    poly_lines.append('    <poly id="excavator_arm" color="40,40,40" fill="true" layer="0.5" shape="267,4.0 278,4.0 278,4.6 267,4.6"/>')

    # POI Peringatan Proyek
    poly_lines.append('    <poi id="poi_proyek" color="255,180,0" layer="2" x="275.0" y="8.0" type="warning"/>')

    # --- PAPAN INFORMASI VMS KATUP ELEKTRONIK (Gantry Signboard Sebelum Titik Urai) ---
    poly_lines.append('    <!-- Struktur Gantry Papan VMS KATUP Digital -->')
    poly_lines.append('    <poly id="vms_gantry" color="60,65,75" fill="true" layer="1.0" shape="-90,-8 -86,-8 -86,8 -90,8"/>')
    poly_lines.append('    <poly id="vms_screen" color="20,25,30" fill="true" layer="1.1" shape="-89,-6 -87,-6 -87,6 -89,6"/>')
    poly_lines.append('    <poi id="poi_vms" color="0,255,100" layer="2" x="-88.0" y="14.0" type="vms"/>')

    # --- GEDUNG PERKANTORAN, PERTOKOAN (RUKO), & PUSAT KOTA (3D City Blocks) ---
    poly_lines.append('    <!-- Blok Bangunan Perkotaan di Sekitar Simpang -->')
    # Kawasan Barat (Ruko & Hunian Modern)
    poly_lines.append('    <poly id="bldg_w1" color="185,195,205" fill="true" layer="0.1" shape="-280,25 -220,25 -220,55 -280,55"/>')
    poly_lines.append('    <poly id="bldg_w1_roof" color="155,165,178" fill="true" layer="0.2" shape="-276,28 -224,28 -224,52 -276,52"/>')
    poly_lines.append('    <poly id="bldg_w2" color="210,195,180" fill="true" layer="0.1" shape="-280,75 -220,75 -220,115 -280,115"/>')
    poly_lines.append('    <poly id="bldg_w3" color="190,200,210" fill="true" layer="0.1" shape="-280,-25 -220,-25 -220,-60 -280,-60"/>')
    poly_lines.append('    <poly id="bldg_w4" color="205,185,175" fill="true" layer="0.1" shape="-280,-85 -220,-85 -220,-125 -280,-125"/>')

    # Kawasan Titik Urai (Traffic Command Center & Perkantoran Pusat)
    poly_lines.append('    <poly id="bldg_its_center" color="65,130,175" fill="true" layer="0.1" shape="-160,25 -100,25 -100,70 -160,70"/>')
    poly_lines.append('    <poly id="bldg_its_roof" color="45,105,150" fill="true" layer="0.2" shape="-155,29 -105,29 -105,66 -155,66"/>')
    poly_lines.append('    <poly id="bldg_commercial_south" color="195,190,185" fill="true" layer="0.1" shape="-160,-25 -100,-25 -100,-65 -160,-65"/>')

    # Kawasan Boulevard Utara & Bypass (Deretan Ruko & Hotel)
    poly_lines.append('    <poly id="bldg_hotel_north" color="175,185,200" fill="true" layer="0.1" shape="220,175 320,175 320,230 220,230"/>')
    poly_lines.append('    <poly id="bldg_hotel_roof" color="140,155,175" fill="true" layer="0.2" shape="226,180 314,180 314,225 226,225"/>')
    poly_lines.append('    <poly id="bldg_ruko_north1" color="215,190,165" fill="true" layer="0.1" shape="340,175 420,175 420,215 340,215"/>')

    # Kawasan Timur / Gerbang CBD (Pusat Bisnis & Menara Pencakar Langit)
    poly_lines.append('    <poly id="bldg_cbd_tower1" color="80,105,130" fill="true" layer="0.1" shape="480,25 560,25 560,95 480,95"/>')
    poly_lines.append('    <poly id="bldg_cbd_tower1_roof" color="55,80,105" fill="true" layer="0.2" shape="488,32 552,32 552,88 488,88"/>')
    poly_lines.append('    <poly id="bldg_cbd_mall" color="180,165,190" fill="true" layer="0.1" shape="480,-25 570,-25 570,-100 480,-100"/>')
    poly_lines.append('    <poly id="bldg_cbd_mall_roof" color="150,135,160" fill="true" layer="0.2" shape="488,-32 562,-32 562,-92 488,-92"/>')
    poly_lines.append('    <poly id="bldg_cbd_tower2" color="95,120,145" fill="true" layer="0.1" shape="690,25 780,25 780,110 690,110"/>')
    poly_lines.append('    <poly id="bldg_cbd_tower2_roof" color="70,95,120" fill="true" layer="0.2" shape="698,33 772,33 772,102 698,102"/>')

    # --- MARKA ZEBRA CROSS (Penyeberangan Pejalan Kaki di Setiap Simpang) ---
    poly_lines.append('    <!-- Marka Penyeberangan Zebra Cross Putih -->')
    # Zebra cross Titik Urai
    poly_lines.append('    <poly id="zebra_W" color="245,245,250" fill="true" layer="0.1" shape="-16,-6 -13,-6 -13,6 -16,6"/>')
    poly_lines.append('    <poly id="zebra_E" color="245,245,250" fill="true" layer="0.1" shape="13,-6 16,-6 16,6 13,6"/>')
    poly_lines.append('    <poly id="zebra_N" color="245,245,250" fill="true" layer="0.1" shape="-6,13 6,13 6,16 -6,16"/>')
    poly_lines.append('    <poly id="zebra_S" color="245,245,250" fill="true" layer="0.1" shape="-6,-16 6,-16 6,-13 -6,-13"/>')

    poly_lines.append('</additional>')

    poly_content = "\n".join(poly_lines)
    with open(os.path.join(sim_dir, "katup.poly.xml"), "w", encoding="utf-8") as f:
        f.write(poly_content)
    print("[OK] [5/6] katup.poly.xml berhasil dibuat (Taman, Kanal Air, Trotoar, Bangunan 3D, Area Proyek).")

    # -------------------------------------------------------------
    # 6. ROUTES & VEHICLE TYPES (katup.rou.xml)
    # Bentuk mobil seperti mobil sungguhan: vClass, guiShape,
    # dimensi proporsional, lampu depan/belakang, dan warna variatif.
    # -------------------------------------------------------------
    rou_content = """<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <!-- =================================================================== -->
    <!-- DISTRIBUSI MOBIL PENUMPANG REALISTIS (BENTUK MOBIL ASLI)           -->
    <!-- Menggunakan guiShape passenger/sedan, hatchback, wagon, van, taxi   -->
    <!-- =================================================================== -->
    <vTypeDistribution id="car">
        <!-- Sedan Silver Metalik -->
        <vType id="sedan_silver" vClass="passenger" guiShape="passenger/sedan" length="4.55" width="1.80" height="1.45" accel="2.8" decel="4.5" sigma="0.4" maxSpeed="16.67" color="215,220,225" probability="0.22"/>
        <!-- Sedan Hitam Eksekutif -->
        <vType id="sedan_black" vClass="passenger" guiShape="passenger/sedan" length="4.60" width="1.82" height="1.45" accel="2.8" decel="4.5" sigma="0.4" maxSpeed="16.67" color="25,28,32" probability="0.18"/>
        <!-- Sedan Putih Mutiara -->
        <vType id="sedan_white" vClass="passenger" guiShape="passenger/sedan" length="4.50" width="1.80" height="1.45" accel="2.8" decel="4.5" sigma="0.4" maxSpeed="16.67" color="245,248,252" probability="0.15"/>
        <!-- Sedan Biru Tua Metalik -->
        <vType id="sedan_blue" vClass="passenger" guiShape="passenger/sedan" length="4.55" width="1.80" height="1.45" accel="2.8" decel="4.5" sigma="0.4" maxSpeed="16.67" color="25,70,140" probability="0.08"/>
        <!-- Sedan Merah Metalik -->
        <vType id="sedan_red" vClass="passenger" guiShape="passenger/sedan" length="4.50" width="1.80" height="1.45" accel="2.8" decel="4.5" sigma="0.4" maxSpeed="16.67" color="185,30,35" probability="0.07"/>
        <!-- Compact Hatchback Abu-Abu -->
        <vType id="hatchback_gray" vClass="passenger" guiShape="passenger/hatchback" length="4.05" width="1.75" height="1.48" accel="2.6" decel="4.5" sigma="0.4" maxSpeed="15.0" color="110,115,122" probability="0.12"/>
        <!-- Family SUV / Station Wagon Gelap -->
        <vType id="suv_dark" vClass="passenger" guiShape="passenger/wagon" length="4.80" width="1.90" height="1.70" accel="2.7" decel="4.5" sigma="0.4" maxSpeed="16.0" color="45,52,62" probability="0.10"/>
        <!-- Taksi Kuning Perkotaan -->
        <vType id="car_taxi" vClass="passenger" guiShape="passenger/sedan" length="4.50" width="1.80" height="1.45" accel="2.9" decel="4.8" sigma="0.4" maxSpeed="16.67" color="245,185,15" probability="0.06"/>
    </vTypeDistribution>

    <!-- Kendaraan Komersial & Layanan Tambahan -->
    <vType id="delivery_van" vClass="delivery" guiShape="delivery" length="5.80" width="2.05" height="2.30" accel="2.0" decel="3.8" sigma="0.5" maxSpeed="13.89" color="235,235,240"/>
    <vType id="city_bus" vClass="bus" guiShape="bus" length="11.80" width="2.50" height="3.20" accel="1.5" decel="3.2" sigma="0.4" maxSpeed="13.89" color="20,120,200"/>
    <vType id="truck_logistics" vClass="truck" guiShape="truck" length="8.50" width="2.40" height="3.20" accel="1.4" decel="3.0" sigma="0.5" maxSpeed="11.11" color="35,80,140"/>

    <!-- =================================================================== -->
    <!-- DEFINISI RUTE KENDARAAN                                            -->
    <!-- =================================================================== -->
    <!-- Rute 1: Jalur Utama (Melintasi Penyempitan / Bottleneck Galian Proyek) -->
    <route id="route_main" edges="edge_W2J edge_pre_bottle edge_bottleneck edge_bottle_exit edge_post_merge"/>
    
    <!-- Rute 2: Jalur Alternatif (Bypass memutari galian lewat Utara) -->
    <route id="route_bypass" edges="edge_W2J edge_J2N edge_alt_1 edge_alt_2 edge_post_merge"/>
    
    <!-- Rute Arus Silang (Utara <-> Selatan) Melintasi Simpang Titik Urai -->
    <route id="route_NS" edges="edge_N_far2N edge_N2J edge_J2S edge_S2S_far"/>
    <route id="route_SN" edges="edge_S_far2S edge_S2J edge_J2N edge_N2N_far"/>

    <!-- Rute Antar Simpang Baru (Menghidupkan Simpang Lainnya) -->
    <!-- Simpang Barat ke Boulevard Utara -->
    <route id="route_west_to_north" edges="edge_W_far2W edge_W2NW edge_NW2N"/>
    <!-- Simpang Barat ke Kawasan Selatan -->
    <route id="route_west_to_south" edges="edge_W_far2W edge_W2SW edge_SW2S"/>
    <!-- Boulevard Utara Lanjut ke Tol Timur -->
    <route id="route_north_to_east" edges="edge_NW2N edge_alt_1 edge_alt2NE_east"/>
    <!-- Akses Timur Masuk Menuju CBD -->
    <route id="route_east_to_cbd" edges="edge_NE_east2E edge_E2CBD"/>
    <!-- Lingkar Selatan Menuju Timur -->
    <route id="route_south_to_east" edges="edge_SW2S edge_S2SE edge_SE2E"/>

    <!-- =================================================================== -->
    <!-- ARUS LALU LINTAS (TRAFFIC FLOWS)                                   -->
    <!-- =================================================================== -->
    <!-- Arus Utama Menuju Bottleneck: 1500 kendaraan/jam (Fokus KATUP) -->
    <flow id="flow_main" type="car" route="route_main" begin="0" end="3600" vehsPerHour="1500" departLane="best" departSpeed="max"/>
    
    <!-- Arus Silang Utara - Selatan: 350 kendaraan/jam -->
    <flow id="flow_NS" type="car" route="route_NS" begin="0" end="3600" vehsPerHour="350" departLane="best" departSpeed="max"/>
    <flow id="flow_SN" type="car" route="route_SN" begin="0" end="3600" vehsPerHour="350" departLane="best" departSpeed="max"/>

    <!-- Arus Kendaraan di Simpang Tambahan (Menjadikan Jaringan Kota Hidup & Aktif) -->
    <flow id="flow_w2n" type="car" route="route_west_to_north" begin="0" end="3600" vehsPerHour="200" departLane="best" departSpeed="max"/>
    <flow id="flow_w2s" type="car" route="route_west_to_south" begin="0" end="3600" vehsPerHour="200" departLane="best" departSpeed="max"/>
    <flow id="flow_n2e" type="car" route="route_north_to_east" begin="0" end="3600" vehsPerHour="250" departLane="best" departSpeed="max"/>
    <flow id="flow_e2cbd" type="delivery_van" route="route_east_to_cbd" begin="0" end="3600" vehsPerHour="180" departLane="best" departSpeed="max"/>
    <flow id="flow_s2e" type="truck_logistics" route="route_south_to_east" begin="0" end="3600" vehsPerHour="150" departLane="best" departSpeed="max"/>
</routes>
"""
    with open(os.path.join(sim_dir, "katup.rou.xml"), "w", encoding="utf-8") as f:
        f.write(rou_content)
    print("[OK] [6/6] katup.rou.xml berhasil dibuat (Model mobil nyata: sedan, hatchback, SUV, van, bus).")

    # -------------------------------------------------------------
    # 7. VIEW SETTINGS (katup.view.xml)
    # Latar rumput hidup, jalan aspal gelap, trotoar & marka jelas,
    # dan kualitas render mobil 2D detail (vehicleQuality="2").
    # -------------------------------------------------------------
    view_content = """<viewsettings>
    <scheme name="KATUP_Realistic_Urban">
        <opengl antialiase="1" dither="1"/>
        <background backgroundColor="48,115,52" showGrid="0"/>
        <edges laneEdgeMode="0" scaleMode="0" laneShowBorders="1" showLinkDecals="1" showRails="0" hideConnectors="1" widthExaggeration="1.00">
            <colorScheme name="uniform">
                <entry color="38,41,45" name="road"/>
                <entry color="200,205,210" name="sidewalk"/>
                <entry color="192,66,44" name="bike lane"/>
                <entry color="45,115,48" name="green verge"/>
                <entry color="45,130,195" name="waterway"/>
            </colorScheme>
        </edges>
        <!-- vehicleQuality="2" merender bentuk mobil asli dengan kap, atap, kaca, lampu & roda -->
        <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1.50" vehicle_exaggeration="1.00" vehicle_constantSize="0" showBlinker="1" showBrakeLight="1">
            <colorScheme name="given vehicle/type/route color">
                <entry color="yellow"/>
            </colorScheme>
        </vehicles>
        <junctions junctionMode="0" drawShape="1">
            <colorScheme name="uniform">
                <entry color="38,41,45"/>
            </colorScheme>
        </junctions>
        <polys poly_minSize="0.00" poly_exaggeration="1.00" polyName_show="0"/>
        <pois poi_minSize="1.00" poi_exaggeration="1.00" poiName_show="1" poiName_size="14.00" poiName_color="255,255,255"/>
        <viewport zoom="120" x="220" y="50"/>
        <delay value="45"/>
    </scheme>
</viewsettings>
"""
    with open(os.path.join(sim_dir, "katup.view.xml"), "w", encoding="utf-8") as f:
        f.write(view_content)
    print("[OK] katup.view.xml diperbarui (Latar rumput, aspal realistis, model mobil berkualitas tinggi).")

    # -------------------------------------------------------------
    # 8. CONFIGURATION (katup.sumocfg)
    # Memuat net-file, route-files, additional-files (poly), dan view
    # -------------------------------------------------------------
    cfg_content = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="katup.net.xml"/>
        <route-files value="katup.rou.xml"/>
        <additional-files value="katup.poly.xml"/>
        <gui-settings-file value="katup.view.xml"/>
    </input>

    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1.0"/>
    </time>

    <processing>
        <time-to-teleport value="-1"/>
    </processing>

    <gui_only>
        <start value="true"/>
        <quit-on-end value="false"/>
    </gui_only>
</configuration>
"""
    with open(os.path.join(sim_dir, "katup.sumocfg"), "w", encoding="utf-8") as f:
        f.write(cfg_content)
    print("[OK] katup.sumocfg diperbarui dengan additional-files poly.")
    print("=" * 60)
    print("Selesai! Seluruh berkas simulasi KATUP berhasil ditingkatkan.")
    print("=" * 60)

if __name__ == "__main__":
    generate_all_simulation_files()
