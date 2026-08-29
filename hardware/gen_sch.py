#!/usr/bin/env python3
"""Generate the Stylus Mixer v0.1 KiCad schematic.
Pinouts taken from primary datasheets (see PROVENANCE in the writeup)."""
import uuid, os, json

OUT = "/Users/barakaeli/Desktop/stylus-mixer-hw"
PROJ = "stylus-mixer"
def U(): return str(uuid.uuid4())
ROOT_UUID = U()

# ---------------------------------------------------------------- part pinouts
# ISP1807  -- Insight SiP isp_ble_DS1807_R19, section 3 "Pin Description"
ISP = [
 (1,"VSS","power_in"),(2,"P0_09/NFC1","bidirectional"),(3,"P0_12","bidirectional"),
 (4,"P0_10/NFC2","bidirectional"),(5,"P0_14","bidirectional"),(6,"P0_26","bidirectional"),
 (7,"VSS","power_in"),(8,"D+","bidirectional"),(9,"P0_16","bidirectional"),
 (10,"D-","bidirectional"),(11,"P0_21","bidirectional"),(12,"VBUS","power_in"),
 (13,"P0_18/RESET","bidirectional"),(14,"VSS","power_in"),(15,"P0_20","bidirectional"),
 (16,"VSS","power_in"),(17,"P0_22","bidirectional"),(18,"VSS","power_in"),
 (19,"P0_24","bidirectional"),(20,"OUT_ANT","passive"),(21,"VSS","power_in"),
 (22,"OUT_MOD","passive"),(23,"VSS","power_in"),(24,"VSS","power_in"),(25,"VSS","power_in"),
 (26,"VCC_nRF","power_in"),(27,"P0_17","bidirectional"),(28,"SWDIO","bidirectional"),
 (29,"P0_13","bidirectional"),(30,"SWDCLK","input"),(31,"VSS","power_in"),
 (32,"P0_08","bidirectional"),(33,"P0_07","bidirectional"),(34,"P0_06","bidirectional"),
 (35,"P0_04/AIN2","bidirectional"),(36,"P0_05/AIN3","bidirectional"),(37,"P0_15","bidirectional"),
 (38,"P0_03/AIN1","bidirectional"),(39,"P0_27","bidirectional"),(40,"P0_02/AIN0","bidirectional"),
 (41,"P0_25","bidirectional"),(42,"P0_31/AIN7","bidirectional"),(43,"P0_11","bidirectional"),
 (44,"P0_30/AIN6","bidirectional"),(45,"P0_19","bidirectional"),(46,"P0_29/AIN5","bidirectional"),
 (47,"P0_23","bidirectional"),(48,"P0_28/AIN4","bidirectional"),(49,"P1_02","bidirectional"),
 (50,"P1_06","bidirectional"),(51,"P1_15","bidirectional"),(52,"P1_14","bidirectional"),
 (53,"P1_13","bidirectional"),(54,"P1_05","bidirectional"),(55,"P1_08","bidirectional"),
 (56,"P1_09","bidirectional"),(57,"P1_00","bidirectional"),(58,"P1_03","bidirectional"),
 (59,"P1_12","bidirectional"),(60,"P1_10","bidirectional"),(61,"P1_11","bidirectional"),
 (62,"P1_07","bidirectional"),(63,"P1_04","bidirectional"),(64,"P1_01","bidirectional"),
] + [(n,"NC","passive") for n in range(65,79)]

# LSM6DSV16X -- ST DS13510 figure 5 "Pin connections"
IMU = [(1,"SDO/SA0","bidirectional"),(2,"SDx","bidirectional"),(3,"SCx","bidirectional"),
 (4,"INT1","output"),(5,"Vdd_IO","power_in"),(6,"GND","power_in"),(7,"GND","power_in"),
 (8,"Vdd","power_in"),(9,"INT2","output"),(10,"OCS_Aux","input"),(11,"SDO_Aux","output"),
 (12,"SDA","bidirectional"),(13,"SCL","input"),(14,"CS","input")]

# MCP73831 SOT-23-5 -- Microchip DS20001984H table 3-1
CHG = [(1,"STAT","open_collector"),(2,"VSS","power_in"),(3,"VBAT","power_out"),
       (4,"VDD","power_in"),(5,"PROG","passive")]

# TPS7A02 DQN (X2SON-4) -- TI table 5-1
LDO = [(1,"OUT","power_out"),(2,"GND","power_in"),(3,"EN","input"),(4,"IN","power_in")]

USBC = [("A1","GND","power_in"),("A4","VBUS","power_in"),("A5","CC1","bidirectional"),
 ("A6","DP1","bidirectional"),("A7","DN1","bidirectional"),("A9","VBUS","power_in"),
 ("A12","GND","power_in"),("B1","GND","power_in"),("B4","VBUS","power_in"),
 ("B5","CC2","bidirectional"),("B6","DP2","bidirectional"),("B7","DN2","bidirectional"),
 ("B9","VBUS","power_in"),("B12","GND","power_in"),("S1","SHIELD","passive")]

# ---------------------------------------------------------------- netlist
NET = {}
def n(ref, pin, net): NET[(ref, str(pin))] = net

for p in (1,7,14,16,18,21,23,24,25,31): n("U1",p,"GND")
n("U1",26,"+3V3"); n("U1",12,"VBUS"); n("U1",8,"USB_DP"); n("U1",10,"USB_DM")
n("U1",20,"ANT"); n("U1",22,"ANT")            # datasheet: OUT_ANT must tie to OUT_MOD
n("U1",28,"SWDIO"); n("U1",30,"SWDCLK"); n("U1",13,"nRESET")
n("U1",6,"SCL"); n("U1",32,"SDA")
n("U1",2,"IMU_INT1"); n("U1",4,"IMU_INT2")
n("U1",36,"FSR_SENSE"); n("U1",38,"VBAT_SENSE")

n("U2",8,"+3V3"); n("U2",5,"+3V3"); n("U2",14,"+3V3")   # CS high = I2C mode
n("U2",6,"GND"); n("U2",7,"GND"); n("U2",1,"GND")       # SA0 low -> 0x6A
n("U2",2,"GND"); n("U2",3,"GND"); n("U2",10,"GND"); n("U2",11,"GND")
n("U2",12,"SDA"); n("U2",13,"SCL"); n("U2",4,"IMU_INT1"); n("U2",9,"IMU_INT2")

n("U3",4,"VBUS"); n("U3",2,"GND"); n("U3",3,"VBAT"); n("U3",1,"CHG_STAT"); n("U3",5,"IPROG")
n("U4",4,"VBAT"); n("U4",3,"VBAT"); n("U4",2,"GND"); n("U4",1,"+3V3")

for p,net in [("A1","GND"),("A12","GND"),("B1","GND"),("B12","GND"),("S1","GND"),
              ("A4","VBUS"),("A9","VBUS"),("B4","VBUS"),("B9","VBUS"),
              ("A5","CC1"),("B5","CC2"),("A6","USB_DP"),("B6","USB_DP"),
              ("A7","USB_DM"),("B7","USB_DM")]: n("J1",p,net)

n("J2",1,"VBAT"); n("J2",2,"GND")            # battery pads
n("J3",1,"+3V3"); n("J3",2,"FSR_SENSE")      # FSR pads

n("R1",1,"CC1"); n("R1",2,"GND")
n("R2",1,"CC2"); n("R2",2,"GND")
n("R3",1,"IPROG"); n("R3",2,"GND")
n("R4",1,"VBUS"); n("R4",2,"LED_A")
n("R5",1,"FSR_SENSE"); n("R5",2,"GND")
n("R6",1,"SDA"); n("R6",2,"+3V3")
n("R7",1,"SCL"); n("R7",2,"+3V3")
n("R8",1,"VBAT"); n("R8",2,"VBAT_SENSE")
n("R9",1,"VBAT_SENSE"); n("R9",2,"GND")
n("D1",1,"LED_A"); n("D1",2,"CHG_STAT")

for ref,a,b in [("C1","VBUS","GND"),("C2","VBAT","GND"),("C3","VBAT","GND"),
                ("C4","+3V3","GND"),("C5","+3V3","GND"),("C6","+3V3","GND"),
                ("C7","+3V3","GND"),("C8","+3V3","GND"),("C9","FSR_SENSE","GND"),
                ("C10","VBAT_SENSE","GND")]:
    n(ref,1,a); n(ref,2,b)

for ref,net in [("TP1","SWDIO"),("TP2","SWDCLK"),("TP3","nRESET"),("TP4","GND"),("TP5","+3V3")]:
    n(ref,1,net)

# ---------------------------------------------------------------- symbol build
GRID = 2.54; PINLEN = 2.54
def eff(size=1.27, just=None, hide=False):
    s = f"(effects (font (size {size} {size}))"
    if just: s += f" (justify {just})"
    if hide: s += " (hide yes)"
    return s + ")"

def make_lib_symbol(name, ref_pfx, pins, halfw, value, fp, desc):
    """pins: list of (num, name, etype, side) ; side 'L' or 'R'"""
    L = [p for p in pins if p[3]=='L']; R = [p for p in pins if p[3]=='R']
    rows = max(len(L), len(R))
    halfh = (rows+1)*GRID/2
    s = [f'\t\t(symbol "stylus:{name}"',
         '\t\t\t(pin_names (offset 0.508))',
         '\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)',
         f'\t\t\t(property "Reference" "{ref_pfx}" (at {-halfw} {halfh+2.5} 0) {eff(1.27,"left")})',
         f'\t\t\t(property "Value" "{value}" (at {-halfw} {halfh+0.4} 0) {eff(1.27,"left")})',
         f'\t\t\t(property "Footprint" "{fp}" (at 0 0 0) {eff(1.27,None,True)})',
         f'\t\t\t(property "Datasheet" "" (at 0 0 0) {eff(1.27,None,True)})',
         f'\t\t\t(property "Description" "{desc}" (at 0 0 0) {eff(1.27,None,True)})',
         f'\t\t\t(symbol "{name}_1_1"',
         f'\t\t\t\t(rectangle (start {-halfw} {halfh}) (end {halfw} {-halfh})',
         '\t\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))']
    coords = {}
    for i,(num,pname,et,_) in enumerate(L):
        y = halfh - (i+1)*GRID
        s.append(f'\t\t\t\t(pin {et} line (at {-halfw-PINLEN} {y} 0) (length {PINLEN})')
        s.append(f'\t\t\t\t\t(name "{pname}" {eff(1.0)}) (number "{num}" {eff(1.0)}))')
        coords[str(num)] = (-halfw-PINLEN, y, 'L')
    for i,(num,pname,et,_) in enumerate(R):
        y = halfh - (i+1)*GRID
        s.append(f'\t\t\t\t(pin {et} line (at {halfw+PINLEN} {y} 180) (length {PINLEN})')
        s.append(f'\t\t\t\t\t(name "{pname}" {eff(1.0)}) (number "{num}" {eff(1.0)}))')
        coords[str(num)] = (halfw+PINLEN, y, 'R')
    s.append('\t\t\t)'); s.append('\t\t)')
    return "\n".join(s), coords

def split(pins, nleft=None):
    """assign sides: first half left, rest right (right listed bottom-up)"""
    if nleft is None: nleft = (len(pins)+1)//2
    out = [(p[0],p[1],p[2],'L') for p in pins[:nleft]]
    out += [(p[0],p[1],p[2],'R') for p in reversed(pins[nleft:])]
    return out

PASSIVE_L = [(1,"~","passive",'L'),(2,"~","passive",'R')]

DEFS = {}   # libname -> (sexpr, coords)
def define(lib, pins, ref, halfw, val, fp, desc):
    DEFS[lib] = make_lib_symbol(lib, ref, pins, halfw, val, fp, desc)

define("ISP1807", split(ISP,39), "U", 26.0, "ISP1807-LR",
       "stylus:ISP1807_LGA78_8x8mm", "nRF52840 BLE module, integrated antenna, 8x8x0.95mm")
define("LSM6DSV16X", split(IMU,7), "U", 20.0, "LSM6DSV16X",
       "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y", "6-axis IMU with on-chip sensor fusion")
define("MCP73831", split(CHG,3), "U", 15.0, "MCP73831T-2ACI/OT",
       "Package_TO_SOT_SMD:SOT-23-5", "Single-cell LiPo charger")
define("TPS7A02", split(LDO,2), "U", 13.0, "TPS7A0233DQN",
       "Package_SON:Texas_X2SON-4_1x1mm_P0.65mm", "3.3V 200nA-Iq LDO")
define("USB_C", split([(a,b,c) for a,b,c in USBC],8), "J", 18.0, "USB-C 16P",
       "Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7010ASV", "USB 2.0 Type-C receptacle")
define("R", PASSIVE_L, "R", 2.54, "R", "Resistor_SMD:R_0402_1005Metric", "Resistor 0402")
define("C", PASSIVE_L, "C", 2.54, "C", "Capacitor_SMD:C_0402_1005Metric", "Capacitor 0402")
define("LED", [(1,"A","passive",'L'),(2,"K","passive",'R')], "D", 2.54, "LED",
       "LED_SMD:LED_0402_1005Metric", "LED 0402")
define("PAD2", [(1,"1","passive",'L'),(2,"2","passive",'R')], "J", 3.81, "PAD",
       "stylus:SolderPad_1.2x2.0mm", "Solder pad pair")
define("TP", [(1,"1","passive",'L')], "TP", 2.54, "TestPoint",
       "stylus:TestPad_1.0mm", "Pogo test pad")

# ---------------------------------------------------------------- placement
# (ref, lib, value, x, y)
PLACE = [
 ("U1","ISP1807","ISP1807-LR", 70, 160),
 ("U2","LSM6DSV16X","LSM6DSV16X", 190, 60),
 ("U3","MCP73831","MCP73831T-2ACI/OT", 190, 150),
 ("U4","TPS7A02","TPS7A0233DQN", 190, 205),
 ("J1","USB_C","USB-C 16P", 300, 70),
 ("J2","PAD2","BAT", 300, 150),
 ("J3","PAD2","FSR", 300, 170),
 ("D1","LED","GRN", 300, 195),
 ("R1","R","5k1", 380, 60),("R2","R","5k1", 380, 75),("R3","R","20k", 380, 90),
 ("R4","R","1k", 380,105),("R5","R","10k", 380,120),("R6","R","4k7", 380,135),
 ("R7","R","4k7", 380,150),("R8","R","1M", 380,165),("R9","R","1M", 380,180),
 ("C1","C","4u7", 450, 60),("C2","C","4u7", 450, 75),("C3","C","1u", 450, 90),
 ("C4","C","1u", 450,105),("C5","C","100n", 450,120),("C6","C","10u", 450,135),
 ("C7","C","100n", 450,150),("C8","C","100n", 450,165),("C9","C","100n", 450,180),
 ("C10","C","100n", 450,195),
 ("TP1","TP","SWDIO", 520, 60),("TP2","TP","SWDCLK", 520, 75),("TP3","TP","nRESET", 520, 90),
 ("TP4","TP","GND", 520,105),("TP5","TP","+3V3", 520,120),
]

FP_OF = {"ISP1807":"stylus:ISP1807_LGA78_8x8mm",
 "LSM6DSV16X":"Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
 "MCP73831":"Package_TO_SOT_SMD:SOT-23-5",
 "TPS7A02":"Package_SON:Texas_X2SON-4_1x1mm_P0.65mm",
 "USB_C":"Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7010ASV",
 "R":"Resistor_SMD:R_0402_1005Metric","C":"Capacitor_SMD:C_0402_1005Metric",
 "LED":"LED_SMD:LED_0402_1005Metric","PAD2":"stylus:SolderPad_1.2x2.0mm",
 "TP":"stylus:TestPad_1.0mm"}

body = []
for ref, lib, val, X, Y in PLACE:
    _, coords = DEFS[lib]
    hh = max(abs(c[1]) for c in coords.values()) + 2
    body.append(f'\t(symbol (lib_id "stylus:{lib}") (at {X} {Y} 0) (unit 1)')
    body.append('\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    body.append(f'\t\t(property "Reference" "{ref}" (at {X} {Y-hh-3} 0) {eff(1.27,"left")})')
    body.append(f'\t\t(property "Value" "{val}" (at {X} {Y-hh-0.8} 0) {eff(1.27,"left")})')
    body.append(f'\t\t(property "Footprint" "{FP_OF[lib]}" (at {X} {Y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1))))')
    body.append('\t)')
    for num,(px,py,side) in coords.items():
        ax, ay = X + px, Y - py
        net = NET.get((ref, num))
        if net is None:
            body.append(f'\t(no_connect (at {ax} {ay}) (uuid "{U()}"))')
            continue
        ex = ax - GRID if side == 'L' else ax + GRID
        body.append(f'\t(wire (pts (xy {ax} {ay}) (xy {ex} {ay}))')
        body.append(f'\t\t(stroke (width 0) (type default)) (uuid "{U()}"))')
        just = "right" if side == 'L' else "left"
        rot = 180 if side == 'L' else 0
        body.append(f'\t(global_label "{net}" (shape bidirectional) (at {ex} {ay} {rot})')
        body.append(f'\t\t(fields_autoplaced yes) {eff(1.27, just)} (uuid "{U()}"))')

libs = "\n".join(DEFS[k][0] for k in DEFS)

sch = f'''(kicad_sch
\t(version 20231120)
\t(generator "eeschema")
\t(generator_version "8.0")
\t(uuid "{ROOT_UUID}")
\t(paper "A2")
\t(title_block
\t\t(title "Stylus Mixer v0.1 - pen-mounted motion controller")
\t\t(date "2026-08-28")
\t\t(rev "0.1")
\t\t(comment 1 "nRF52840 + 6-axis IMU with on-chip fusion, USB-C, LiPo charge")
\t\t(comment 2 "Pinouts from primary datasheets - see README PROVENANCE")
\t)
\t(lib_symbols
{libs}
\t)
{chr(10).join(body)}
\t(sheet_instances (path "/" (page "1")))
\t(embedded_fonts no)
)
'''
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, PROJ + ".kicad_sch"), "w").write(sch)

pro = {"board":{"design_settings":{"defaults":{}}},"libraries":{"pinned_footprint_libs":[],
 "pinned_symbol_libs":[]},"meta":{"filename":PROJ+".kicad_pro","version":1},
 "net_settings":{"classes":[{"name":"Default","clearance":0.09,"track_width":0.15,
 "via_diameter":0.45,"via_drill":0.2,"microvia_diameter":0.3,"microvia_drill":0.15}]},
 "sheets":[[ROOT_UUID,"Root"]],"text_variables":{}}
open(os.path.join(OUT, PROJ + ".kicad_pro"), "w").write(json.dumps(pro, indent=2))

nets = sorted(set(NET.values()))
print("symbols:", len(PLACE), " connections:", len(NET), " nets:", len(nets))
print("nets:", ", ".join(nets))
print("ROOT_UUID", ROOT_UUID)
