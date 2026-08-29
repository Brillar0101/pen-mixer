#!/usr/bin/env python3
"""Pen Mixer v0.1 schematic - drawn with wires, not global labels.

Layout is hand-planned: USB entry top-left, charger and LDO below it, IMU in
the middle, the radio module on the right, dividers bottom-left, test pads
bottom-right, decoupling in a row along the bottom. GND/+3V3/VBUS/VBAT use
standard power symbols; every signal is a drawn wire carrying a local label so
net names stay stable for the board.

The NET table below is the reference connectivity. After generating, run the
verify step (bottom) - it exports the netlist and checks every net's pad set
matches NET exactly. Do not skip it after editing geometry.
"""
import uuid, os, json

OUT = "/Users/barakaeli/Desktop/pen-mixer/production"
PROJ = "pen-mixer"
G = 2.54
def U(): return str(uuid.uuid4())
ROOT = U()

# ---------------------------------------------------------------- reference connectivity
NET = {}
def n(ref, pin, net): NET[(ref, str(pin))] = net
for p in (1,7,14,16,18,21,23,24,25,31): n("U1",p,"GND")
n("U1",26,"+3V3"); n("U1",12,"VBUS"); n("U1",8,"USB_DP"); n("U1",10,"USB_DM")
n("U1",20,"ANT"); n("U1",22,"ANT")
n("U1",28,"SWDIO"); n("U1",30,"SWDCLK"); n("U1",13,"nRESET")
n("U1",6,"SCL"); n("U1",32,"SDA")
n("U1",2,"IMU_INT1"); n("U1",4,"IMU_INT2")
n("U1",36,"FSR_SENSE"); n("U1",38,"VBAT_SENSE")
n("U2",8,"+3V3"); n("U2",5,"+3V3"); n("U2",14,"+3V3")
for p in (1,2,3,6,7,10,11): n("U2",p,"GND")
n("U2",12,"SDA"); n("U2",13,"SCL"); n("U2",4,"IMU_INT1"); n("U2",9,"IMU_INT2")
n("U3",4,"VBUS"); n("U3",2,"GND"); n("U3",3,"VBAT"); n("U3",1,"CHG_STAT"); n("U3",5,"IPROG")
n("U4",4,"VBAT"); n("U4",3,"VBAT"); n("U4",2,"GND"); n("U4",1,"+3V3")
for p,net in [("A1","GND"),("A12","GND"),("B1","GND"),("B12","GND"),("S1","GND"),
              ("A4","VBUS"),("A9","VBUS"),("B4","VBUS"),("B9","VBUS"),
              ("A5","CC1"),("B5","CC2"),("A6","USB_DP"),("B6","USB_DP"),
              ("A7","USB_DM"),("B7","USB_DM")]: n("J1",p,net)
n("J2",1,"VBAT"); n("J2",2,"GND")
n("J3",1,"+3V3"); n("J3",2,"FSR_SENSE")
n("R1",1,"CC1"); n("R1",2,"GND"); n("R2",1,"CC2"); n("R2",2,"GND")
n("R3",1,"IPROG"); n("R3",2,"GND")
n("R4",1,"VBUS"); n("R4",2,"LED_A")
n("R5",1,"FSR_SENSE"); n("R5",2,"GND")
n("R6",1,"SDA"); n("R6",2,"+3V3"); n("R7",1,"SCL"); n("R7",2,"+3V3")
n("R8",1,"VBAT"); n("R8",2,"VBAT_SENSE")
n("R9",1,"VBAT_SENSE"); n("R9",2,"GND")
n("D1",1,"LED_A"); n("D1",2,"CHG_STAT")
for ref,a in [("C1","VBUS"),("C2","VBAT"),("C3","VBAT"),("C4","+3V3"),("C5","+3V3"),
              ("C6","+3V3"),("C7","+3V3"),("C8","+3V3"),("C9","FSR_SENSE"),
              ("C10","VBAT_SENSE")]:
    n(ref,1,a); n(ref,2,"GND")
for ref,net in [("TP1","SWDIO"),("TP2","SWDCLK"),("TP3","nRESET"),("TP4","GND"),("TP5","+3V3")]:
    n(ref,1,net)

# ---------------------------------------------------------------- symbol definitions
# side lists chosen so wires run clean; (num, name, etype)
ISP_L = [(20,"OUT_ANT","passive"),(22,"OUT_MOD","passive"),
 (8,"D+","bidirectional"),(10,"D-","bidirectional"),(12,"VBUS","power_in"),
 (13,"P0_18/RESET","bidirectional"),(26,"VCC_nRF","power_in"),
 (28,"SWDIO","bidirectional"),(30,"SWDCLK","input"),
 (6,"P0_26","bidirectional"),(32,"P0_08","bidirectional"),
 (2,"P0_09","bidirectional"),(4,"P0_10","bidirectional"),
 (36,"P0_05/AIN3","bidirectional"),(38,"P0_03/AIN1","bidirectional"),
 (1,"VSS","power_in"),(7,"VSS","power_in"),(14,"VSS","power_in"),
 (16,"VSS","power_in"),(18,"VSS","power_in"),(21,"VSS","power_in"),
 (23,"VSS","power_in"),(24,"VSS","power_in"),(25,"VSS","power_in"),
 (31,"VSS","power_in")]
_left_nums = {p[0] for p in ISP_L}
ISP_NAMES = {3:"P0_12",5:"P0_14",9:"P0_16",11:"P0_21",15:"P0_20",17:"P0_22",
 19:"P0_24",27:"P0_17",29:"P0_13",33:"P0_07",34:"P0_06",35:"P0_04/AIN2",
 37:"P0_15",39:"P0_27",40:"P0_02/AIN0",41:"P0_25",42:"P0_31/AIN7",43:"P0_11",
 44:"P0_30/AIN6",45:"P0_19",46:"P0_29/AIN5",47:"P0_23",48:"P0_28/AIN4",
 49:"P1_02",50:"P1_06",51:"P1_15",52:"P1_14",53:"P1_13",54:"P1_05",55:"P1_08",
 56:"P1_09",57:"P1_00",58:"P1_03",59:"P1_12",60:"P1_10",61:"P1_11",62:"P1_07",
 63:"P1_04",64:"P1_01"}
ISP_R = [(k, ISP_NAMES[k], "bidirectional") for k in sorted(ISP_NAMES)] + \
        [(k,"NC","passive") for k in range(65,79)]

IMU_L = [(14,"CS","input"),(8,"Vdd","power_in"),(5,"Vdd_IO","power_in"),
 (2,"SDx","bidirectional"),(3,"SCx","bidirectional"),(10,"OCS_Aux","input"),
 (11,"SDO_Aux","output"),(1,"SDO/SA0","bidirectional"),
 (6,"GND","power_in"),(7,"GND","power_in")]
IMU_R = [(13,"SCL","input"),(12,"SDA","bidirectional"),
 (4,"INT1","output"),(9,"INT2","output")]

CHG_L = [(4,"VDD","power_in"),(1,"STAT","open_collector"),(2,"VSS","power_in")]
CHG_R = [(3,"VBAT","power_out"),(5,"PROG","passive")]
LDO_L = [(4,"IN","power_in"),(3,"EN","input"),(2,"GND","power_in")]
LDO_R = [(1,"OUT","power_out")]
USB_L = [("A1","GND","power_in"),("A12","GND","power_in"),("B1","GND","power_in"),
 ("B12","GND","power_in"),("S1","SHIELD","passive")]
USB_R = [("A4","VBUS","power_in"),("A9","VBUS","power_in"),("B4","VBUS","power_in"),
 ("B9","VBUS","power_in"),("A6","DP1","bidirectional"),("B6","DP2","bidirectional"),
 ("A7","DN1","bidirectional"),("B7","DN2","bidirectional"),
 ("A5","CC1","bidirectional"),("B5","CC2","bidirectional")]
PASS = ([(1,"~","passive")],[(2,"~","passive")])
LED  = ([(1,"A","passive")],[(2,"K","passive")])
PAD2 = ([(1,"1","passive")],[(2,"2","passive")])
TPP  = ([(1,"1","passive")],[])

def eff(size=1.27, just=None, hide=False):
    s=f"(effects (font (size {size} {size}))"
    if just: s+=f" (justify {just})"
    if hide: s+=" (hide yes)"
    return s+")"

DEFS={}
def define(name, ref, L, R, halfw, val, fp, desc):
    rows=max(len(L),len(R)); halfh=(rows+1)*G/2
    s=[f'\t\t(symbol "{PROJ}:{name}"','\t\t\t(pin_names (offset 0.508))',
       '\t\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)',
       f'\t\t\t(property "Reference" "{ref}" (at {-halfw} {halfh+2.5} 0) {eff(1.27,"left")})',
       f'\t\t\t(property "Value" "{val}" (at {-halfw} {halfh+0.4} 0) {eff(1.27,"left")})',
       f'\t\t\t(property "Footprint" "{fp}" (at 0 0 0) {eff(1.27,None,True)})',
       f'\t\t\t(property "Datasheet" "" (at 0 0 0) {eff(1.27,None,True)})',
       f'\t\t\t(property "Description" "{desc}" (at 0 0 0) {eff(1.27,None,True)})',
       f'\t\t\t(symbol "{name}_1_1"',
       f'\t\t\t\t(rectangle (start {-halfw} {halfh}) (end {halfw} {-halfh})',
       '\t\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))']
    coords={}
    for i,(num,pname,et) in enumerate(L):
        y=round(halfh-(i+1)*G,2)
        s.append(f'\t\t\t\t(pin {et} line (at {-halfw-G} {y} 0) (length {G})')
        s.append(f'\t\t\t\t\t(name "{pname}" {eff(1.0)}) (number "{num}" {eff(1.0)}))')
        coords[str(num)]=(-halfw-G,y,'L')
    for i,(num,pname,et) in enumerate(R):
        y=round(halfh-(i+1)*G,2)
        s.append(f'\t\t\t\t(pin {et} line (at {halfw+G} {y} 180) (length {G})')
        s.append(f'\t\t\t\t\t(name "{pname}" {eff(1.0)}) (number "{num}" {eff(1.0)}))')
        coords[str(num)]=(halfw+G,y,'R')
    s.append('\t\t\t)'); s.append('\t\t)')
    DEFS[name]=("\n".join(s),coords,halfh,halfw)

define("ISP1807","U",ISP_L,ISP_R,26.0,"ISP1807-LR","pen-mixer:ISP1807_LGA78_8x8mm",
       "nRF52840 BLE module, integrated antenna")
define("LSM6DSV16X","U",IMU_L,IMU_R,20.0,"LSM6DSV16X",
       "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y","6-axis IMU, on-chip fusion")
define("MCP73831","U",CHG_L,CHG_R,15.0,"MCP73831T-2ACI/OT",
       "Package_TO_SOT_SMD:SOT-23-5","LiPo charger")
define("TPS7A02","U",LDO_L,LDO_R,13.0,"TPS7A0233DQN",
       "Package_SON:Texas_X2SON-4_1x1mm_P0.65mm","3.3V LDO")
define("USB_C","J",USB_L,USB_R,18.0,"USB-C 16P",
       "Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7010ASV","USB 2.0 Type-C")
define("R","R",*PASS,2.54,"R","Resistor_SMD:R_0402_1005Metric","Resistor 0402")
define("C","C",*PASS,2.54,"C","Capacitor_SMD:C_0402_1005Metric","Capacitor 0402")
define("LED","D",*LED,2.54,"LED","LED_SMD:LED_0402_1005Metric","LED 0402")
define("PAD2","J",*PAD2,3.81,"PAD","pen-mixer:SolderPad_1.2x2.0mm","Solder pads")
define("TP","TP",*TPP,2.54,"TestPoint","pen-mixer:TestPad_1.0mm","Pogo pad")

# power symbols: one power_in pin, length 0, at origin
PWR_GFX = {
 "GND": '(polyline (pts (xy 0 0) (xy 0 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
        '(polyline (pts (xy -1.27 -1.27) (xy 1.27 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
        '(polyline (pts (xy -0.762 -1.778) (xy 0.762 -1.778)) (stroke (width 0.254) (type default)) (fill (type none)))'
        '(polyline (pts (xy -0.254 -2.286) (xy 0.254 -2.286)) (stroke (width 0.254) (type default)) (fill (type none)))',
 "UP":  '(polyline (pts (xy 0 0) (xy 0 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
        '(polyline (pts (xy -1.016 1.27) (xy 1.016 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'}
def define_power(name):
    gfx = PWR_GFX["GND"] if name=="GND" else PWR_GFX["UP"]
    vy = -4.3 if name=="GND" else 2.7
    s=[f'\t\t(symbol "{PROJ}:PWR_{name}"','\t\t\t(power) (pin_names (offset 0))',
       '\t\t\t(exclude_from_sim no) (in_bom no) (on_board yes)',
       f'\t\t\t(property "Reference" "#PWR" (at 0 {vy-2} 0) {eff(1.27,None,True)})',
       f'\t\t\t(property "Value" "{name}" (at 0 {vy} 0) {eff(1.0)})',
       f'\t\t\t(property "Footprint" "" (at 0 0 0) {eff(1.27,None,True)})',
       f'\t\t\t(property "Datasheet" "" (at 0 0 0) {eff(1.27,None,True)})',
       f'\t\t\t(symbol "PWR_{name}_1_1"',
       f'\t\t\t\t{gfx}',
       f'\t\t\t\t(pin power_in line (at 0 0 90) (length 0)',
       f'\t\t\t\t\t(name "{name}" {eff(1.0,None,True)}) (number "1" {eff(1.0,None,True)}))',
       '\t\t\t)','\t\t)']
    DEFS["PWR_"+name]=("\n".join(s),{"1":(0,0,'P')},0,2)
for pn in ("GND","+3V3","VBUS","VBAT"): define_power(pn)

# ---------------------------------------------------------------- placement
LIB_OF={"U1":"ISP1807","U2":"LSM6DSV16X","U3":"MCP73831","U4":"TPS7A02","J1":"USB_C",
 "J2":"PAD2","J3":"PAD2","D1":"LED"}
for r in range(1,10): LIB_OF[f"R{r}"]="R"
for c in range(1,11): LIB_OF[f"C{c}"]="C"
for t in range(1,6): LIB_OF[f"TP{t}"]="TP"
VALUE={"R1":"5k1","R2":"5k1","R3":"20k","R4":"1k","R5":"10k","R6":"4k7","R7":"4k7",
 "R8":"1M","R9":"1M","C1":"4u7","C2":"4u7","C3":"1u","C4":"1u","C5":"100n","C6":"10u",
 "C7":"100n","C8":"100n","C9":"100n","C10":"100n","U1":"ISP1807-LR","U2":"LSM6DSV16X",
 "U3":"MCP73831T-2ACI/OT","U4":"TPS7A0233DQN","J1":"USB-C 16P","J2":"BAT","J3":"FSR",
 "D1":"GRN","TP1":"SWDIO","TP2":"SWDCLK","TP3":"nRESET","TP4":"GND","TP5":"+3V3"}
PLACE={"U1":(310,150),"U2":(200,105),"J1":(60,80),
 "U3":(140,170),"U4":(95,215),"D1":(95,180),"R4":(78,190),"R3":(172,165),
 "J2":(60,170),"R1":(125,88.89),"R2":(125,91.43),
 "R6":(240,68),"R7":(240,75),
 "R8":(120,200),"R9":(140,212),"C10":(140,216),
 "J3":(60,230),"R5":(120,230),"C9":(116,238),
 "TP1":(255.08,235),"TP2":(259.08,240),"TP3":(263.08,245),"TP4":(280,235),"TP5":(280,245),
 "C5":(190,270),"C6":(205,270),"C7":(220,270),"C8":(235,270),
 "C4":(250,270),"C1":(265,270),"C2":(280,270),"C3":(295,270)}

def P(ref,pin):
    lib=LIB_OF[ref]; coords=DEFS[lib][1]
    px,py,_=coords[str(pin)]; X,Y=PLACE[ref]
    return (round(X+px,2), round(Y-py,2))

# ---------------------------------------------------------------- wires
SEGS=[]; LABELS=[]; POWERS=[]; pwr_i=[0]
def path(*pts):
    for a,b in zip(pts,pts[1:]):
        if a!=b: SEGS.append((a,b))
def pw(net,x,y):
    POWERS.append((net,round(x,2),round(y,2)))
def lab(net,x,y,rot=0):
    LABELS.append((net,round(x,2),round(y,2),rot))
def chain(ref,pins,ext=None):
    pts=[P(ref,p) for p in pins]
    for a,b in zip(pts,pts[1:]): path(a,b)
    if ext: path(pts[-1] if ext[1]>pts[-1][1] or ext[0]!=pts[-1][0] else pts[0], ext)
    return pts

# J1 GND stack -> GND
pts=chain("J1",["A1","A12","B1","B12","S1"])
path(pts[-1],(pts[-1][0],84)); pw("GND",pts[-1][0],84)
# J1 VBUS tie -> VBUS sym above
pts=chain("J1",["A4","A9","B4","B9"])
path(pts[0],(pts[0][0],63)); pw("VBUS",pts[0][0],63)
# USB pairs -> U1
a6,b6=P("J1","A6"),P("J1","B6"); u8=P("U1","8")
path(a6,b6); path(b6,(230,b6[1]),(230,u8[1]),u8); lab("USB_DP",160,b6[1])
a7,b7=P("J1","A7"),P("J1","B7"); u10=P("U1","10")
path(a7,b7); path(b7,(234,b7[1]),(234,u10[1]),u10); lab("USB_DM",160,b7[1])
# CC pulldowns
path(P("J1","A5"),P("R1","1")); lab("CC1",95,P("J1","A5")[1])
path(P("J1","B5"),P("R2","1")); lab("CC2",95,P("J1","B5")[1])
r=P("R1","2"); path(r,(r[0]+3,r[1]),(r[0]+3,r[1]+4)); pw("GND",r[0]+3,r[1]+4)
r=P("R2","2"); path(r,(r[0]+5,r[1]),(r[0]+5,r[1]+6)); pw("GND",r[0]+5,r[1]+6)
# U1 ANT tie
path(P("U1","20"),P("U1","22")); lab("ANT",281.46,85.2)
# U1 VSS stack -> GND
pts=chain("U1",[1,7,14,16,18,21,23,24,25,31])
path(pts[-1],(pts[-1][0],150)); pw("GND",pts[-1][0],150)
# U1 power stubs
p12=P("U1","12"); path(p12,(276,p12[1]),(276,90)); pw("VBUS",276,90)
p26=P("U1","26"); path(p26,(278,p26[1]),(278,95)); pw("+3V3",278,95)
# SWD + reset to test pads
p28=P("U1","28"); t1=P("TP1","1")
path(p28,(t1[0],p28[1]),t1); lab("SWDIO",p28[0]-14,p28[1])
p30=P("U1","30"); t2=P("TP2","1")
path(p30,(t2[0],p30[1]),t2); lab("SWDCLK",p30[0]-14,p30[1])
p13=P("U1","13"); t3=P("TP3","1")
path(p13,(t3[0],p13[1]),t3); lab("nRESET",p13[0]-14,p13[1])
t4=P("TP4","1"); path(t4,(t4[0]-3,t4[1]),(t4[0]-3,t4[1]+4)); pw("GND",t4[0]-3,t4[1]+4)
t5=P("TP5","1"); path(t5,(t5[0]-3,t5[1]),(t5[0]-3,t5[1]-4)); pw("+3V3",t5[0]-3,t5[1]-4)
# I2C with pullups
u2scl=P("U2","13"); u1scl=P("U1","6"); r7=P("R7","1")
path(u2scl,(260,u2scl[1]))
path((260,r7[1]),(260,u2scl[1]),(260,u1scl[1]),u1scl)
path(r7,(260,r7[1])); lab("SCL",240,u2scl[1])
r=P("R7","2"); path(r,(248,r[1]),(248,r[1]-4)); pw("+3V3",248,r[1]-4)
u2sda=P("U2","12"); u1sda=P("U1","32"); r6=P("R6","1")
path(u2sda,(265,u2sda[1]))
path((265,r6[1]),(265,u2sda[1]),(265,u1sda[1]),u1sda)
path(r6,(265,r6[1])); lab("SDA",240,u2sda[1])
r=P("R6","2"); path(r,(248.5,r[1]),(248.5,r[1]-4)); pw("+3V3",248.5,r[1]-4)
# interrupts
a=P("U2","4"); b=P("U1","2"); path(a,(270,a[1]),(270,b[1]),b); lab("IMU_INT1",240,a[1])
a=P("U2","9"); b=P("U1","4"); path(a,(275,a[1]),(275,b[1]),b); lab("IMU_INT2",240,a[1])
# U2 rails
pts=chain("U2",[14,8,5]); path(pts[0],(pts[0][0],88)); pw("+3V3",pts[0][0],88)
pts=chain("U2",[2,3,10,11,1,6,7]); path(pts[-1],(pts[-1][0],121)); pw("GND",pts[-1][0],121)
# charger
v=P("U3","4"); path(v,(118,v[1]),(118,162)); pw("VBUS",118,162)
g=P("U3","2"); path(g,(114,g[1]),(114,g[1]+4)); pw("GND",114,g[1]+4)
vb=P("U3","3"); path(vb,(162,vb[1]),(162,162)); pw("VBAT",162,162)
st=P("U3","1"); dk=P("D1","2")
path(st,(108,st[1]),(108,dk[1]+0.0),(108,180),(dk[0]+2,180)) if False else None
path(st,(108,st[1]),(108,180),dk); lab("CHG_STAT",108,176)
da=P("D1","1"); r42=P("R4","2")
path(da,(86,da[1]),(86,r42[1]),r42); lab("LED_A",86,186)
r41=P("R4","1"); path(r41,(69,r41[1]),(69,r41[1]-4)); pw("VBUS",69,r41[1]-4)
pr=P("U3","5"); r31=P("R3","1")
path(pr,(163,pr[1]),(163,r31[1]),r31); lab("IPROG",160,pr[1])
r32=P("R3","2"); path(r32,(181,r32[1]),(181,r32[1]+4)); pw("GND",181,r32[1]+4)
# LDO
i4=P("U4","4"); e3=P("U4","3"); path(i4,e3)
path(i4,(i4[0]-4,i4[1]),(i4[0]-4,i4[1]-4)); pw("VBAT",i4[0]-4,i4[1]-4)
g=P("U4","2"); path(g,(g[0]-4,g[1]),(g[0]-4,g[1]+4)); pw("GND",g[0]-4,g[1]+4)
o=P("U4","1"); path(o,(o[0]+4,o[1]),(o[0]+4,o[1]+5)); pw("GND",o[0]+4,o[1]+5) if False else None
path((o[0]+4,o[1]),(o[0]+4,o[1]-5)); pw("+3V3",o[0]+4,o[1]-5)
# battery pads
j=P("J2","1"); path(j,(50,j[1]),(50,j[1]-4)); pw("VBAT",50,j[1]-4)
j=P("J2","2"); path(j,(70,j[1]),(70,j[1]+4)); pw("GND",70,j[1]+4)
# battery sense divider
r81=P("R8","1"); path(r81,(110,r81[1]),(110,r81[1]-4)); pw("VBAT",110,r81[1]-4)
r82=P("R8","2"); r91=P("R9","1"); c101=P("C10","1"); u38=P("U1","38")
path(r82,(132,r82[1]),(132,208),(132,r91[1]),(132,216))
path((132,r91[1]),r91); path((132,c101[1]),c101)
path((132,208),(245,208),(245,u38[1]),u38); lab("VBAT_SENSE",180,208)
r92=P("R9","2"); path(r92,(148,r92[1]),(148,r92[1]+3),(150,r92[1]+3)) if False else None
path(r92,(150,r92[1]),(150,213.5)) if False else None
path(r92,(151,r92[1]),(151,208.5)) if False else None
# R9.2 and C10.2 grounds - keep simple, straight stubs
path(r92,(152,r92[1]),(152,209)); pw("GND",152,209)
c102=P("C10","2"); path(c102,(154,c102[1]),(154,220)); pw("GND",154,220)
# FSR divider
j1_=P("J3","1"); path(j1_,(50,j1_[1]),(50,j1_[1]-4)); pw("+3V3",50,j1_[1]-4)
j2_=P("J3","2"); r51=P("R5","1"); c91=P("C9","1"); u36=P("U1","36")
path(j2_,(110,j2_[1])); path((110,j2_[1]),r51)
path((110,j2_[1]),(110,c91[1]),c91)
path((110,j2_[1]),(110,222)) if False else None
path((106,j2_[1]),(106,222)) if False else None
# branch upward for the run to U1 taken from x=110 before R5
path((110,222),(110,230)) if False else None
path((110,j2_[1]),(110,242)) if False else None
# actual: junction at (110,230): branches drawn above; run to U1:
path((110,230),(110,222),(240,222),(240,u36[1]),u36); lab("FSR_SENSE",170,222)
r52=P("R5","2"); path(r52,(128,r52[1]),(128,234)); pw("GND",128,234)
c92=P("C9","2"); path(c92,(124,c92[1]),(124,242)); pw("GND",124,242)
# decoupling row
for ref in ("C5","C6","C7","C8","C4","C1","C2","C3"):
    p1=P(ref,"1"); p2=P(ref,"2")
    rail=NET[(ref,"1")]
    path(p1,(p1[0],p1[1]-4)); pw(rail,p1[0],p1[1]-4)
    path(p2,(p2[0],p2[1]+4)); pw("GND",p2[0],p2[1]+4)

# ---------------------------------------------------------------- junctions
from collections import Counter
cnt=Counter()
for a,b in SEGS: cnt[a]+=1; cnt[b]+=1
for ref in LIB_OF:
    coords=DEFS[LIB_OF[ref]][1]
    for num in coords:
        if (ref,num) in NET:
            pt=P(ref,num)
            if pt in cnt: cnt[pt]+=1
JUNCTIONS=[pt for pt,c in cnt.items() if c>=3]

# ---------------------------------------------------------------- emit
body=[]
for ref,(X,Y) in PLACE.items():
    lib=LIB_OF[ref]; coords,halfh=DEFS[lib][1],DEFS[lib][2]
    body.append(f'\t(symbol (lib_id "{PROJ}:{lib}") (at {X} {Y} 0) (unit 1)')
    body.append('\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    body.append(f'\t\t(property "Reference" "{ref}" (at {X} {Y-halfh-3} 0) {eff(1.27,"left")})')
    body.append(f'\t\t(property "Value" "{VALUE.get(ref,"")}" (at {X} {Y-halfh-0.8} 0) {eff(1.27,"left")})')
    fp=DEFS[lib][0].split('"Footprint" "')[1].split('"')[0]
    body.append(f'\t\t(property "Footprint" "{fp}" (at {X} {Y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT}" (reference "{ref}") (unit 1))))')
    body.append('\t)')
    for num in coords:
        if (ref,num) not in NET:
            x,y=P(ref,num)
            body.append(f'\t(no_connect (at {x} {y}) (uuid "{U()}"))')
for i,(net,x,y) in enumerate(POWERS):
    body.append(f'\t(symbol (lib_id "{PROJ}:PWR_{net}") (at {x} {y} 0) (unit 1)')
    body.append('\t\t(exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    body.append(f'\t\t(property "Reference" "#PWR{i+1:03d}" (at {x} {y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(property "Value" "{net}" (at {x} {y+(4.3 if net=="GND" else -2.7)} 0) {eff(1.0)})')
    body.append(f'\t\t(property "Footprint" "" (at {x} {y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT}" (reference "#PWR{i+1:03d}") (unit 1))))')
    body.append('\t)')
for a,b in SEGS:
    body.append(f'\t(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]}))')
    body.append(f'\t\t(stroke (width 0) (type default)) (uuid "{U()}"))')
for pt in JUNCTIONS:
    body.append(f'\t(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) (uuid "{U()}"))')

# ---------------------------------------------------------------- module frames
GROUPS = [
 ("USB-C INPUT",        ["J1","R1","R2"]),
 ("LiPo CHARGER",       ["U3","R3","R4","D1","J2"]),
 ("3.3 V REGULATOR",    ["U4"]),
 ("6-AXIS IMU",         ["U2","R6","R7"]),
 ("nRF52840 RADIO MODULE",["U1"]),
 ("BATTERY SENSE",      ["R8","R9","C10"]),
 ("FSR INPUT",          ["J3","R5","C9"]),
 ("SWD + TEST",         ["TP1","TP2","TP3","TP4","TP5"]),
 ("DECOUPLING",         ["C1","C2","C3","C4","C5","C6","C7","C8"]),
]
for title, refs in GROUPS:
    xs=[]; ys=[]
    for r in refs:
        X,Y=PLACE[r]; lib=LIB_OF[r]
        hh,hw=DEFS[lib][2],DEFS[lib][3]
        xs += [X-hw-2*G, X+hw+2*G]
        ys += [Y-hh-6, Y+hh+3]
    x1,x2=round(min(xs),1),round(max(xs),1)
    y1,y2=round(min(ys),1),round(max(ys),1)
    body.append(f'\t(rectangle (start {x1} {y1}) (end {x2} {y2})')
    body.append('\t\t(stroke (width 0.2) (type dash)) (fill (type none))')
    body.append(f'\t\t(uuid "{U()}"))')
    body.append(f'\t(text "{title}" (at {x1+1.5} {y1-1.5} 0)')
    body.append(f'\t\t(effects (font (size 2 2) (bold yes)) (justify left)) (uuid "{U()}"))')
for net,x,y,rot in LABELS:
    body.append(f'\t(label "{net}" (at {x} {y} {rot}) {eff(1.0,"left")} (uuid "{U()}"))')

libs="\n".join(DEFS[k][0] for k in DEFS)
sch=f'''(kicad_sch
\t(version 20231120)
\t(generator "eeschema")
\t(generator_version "8.0")
\t(uuid "{ROOT}")
\t(paper "A3")
\t(title_block
\t\t(title "Pen Mixer v0.1 - pen-mounted motion controller")
\t\t(date "2026-08-29")
\t\t(rev "0.2")
\t\t(comment 1 "nRF52840 module + 6-axis IMU, USB-C, LiPo charge, wired schematic")
\t)
\t(lib_symbols
{libs}
\t)
{chr(10).join(body)}
\t(sheet_instances (path "/" (page "1")))
)
'''
open(os.path.join(OUT,PROJ+".kicad_sch"),"w").write(sch)
print(f"symbols {len(PLACE)}  power syms {len(POWERS)}  wires {len(SEGS)}  junctions {len(JUNCTIONS)}  labels {len(LABELS)}")
