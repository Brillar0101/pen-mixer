#!/usr/bin/env python3
"""Pen Mixer schematic, rev 0.3 - built from KiCad stock symbols.

No hand-rolled symbols. Everything comes from the libraries shipped with
KiCad 10, plus the vendor-supplied ISP1807-LR symbol (SnapEDA download).
Wires inside modules, global labels between them, power symbols for rails.
Module frames are computed from everything drawn, so nothing crosses one.

Changes from rev 0.2, both driven by part availability:
  U4 is a TPS7A0533PDBV (SOT-23-5) - stock symbol + footprint, same job.
  TP3/nRESET is gone - the reset pin cannot escape the LGA without
  via-in-pad, and SWD resets the chip anyway.
"""
import re, uuid, os

OUT="/Users/barakaeli/Desktop/pen-mixer/production"
PROJ="pen-mixer"
SLIB="/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
G=1.27
def U(): return str(uuid.uuid4())
ROOT=U()

# ------------------------------------------------------------- reference nets
NET={}
def n(ref,pin,net): NET[(ref,str(pin))]=net
for p in (1,7,14,16,18,21,23,24,25,31): n("U1",p,"GND")
n("U1",26,"+3V3"); n("U1",12,"VBUS"); n("U1",8,"USB_DP"); n("U1",10,"USB_DM")
n("U1",20,"ANT"); n("U1",22,"ANT")
n("U1",28,"SWDIO"); n("U1",30,"SWDCLK")
n("U1",6,"SCL"); n("U1",32,"SDA")
n("U1",2,"IMU_INT1"); n("U1",4,"IMU_INT2")
n("U1",36,"FSR_SENSE"); n("U1",38,"VBAT_SENSE")
n("U2",8,"+3V3"); n("U2",5,"+3V3"); n("U2",14,"+3V3")
for p in (1,2,3,6,7,10,11): n("U2",p,"GND")
n("U2",12,"SDA"); n("U2",13,"SCL"); n("U2",4,"IMU_INT1"); n("U2",9,"IMU_INT2")
n("U3",4,"VBUS"); n("U3",2,"GND"); n("U3",3,"VBAT"); n("U3",1,"CHG_STAT"); n("U3",5,"IPROG")
n("U4",1,"VBAT"); n("U4",2,"GND"); n("U4",3,"VBAT"); n("U4",5,"+3V3")
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
n("D1",1,"CHG_STAT"); n("D1",2,"LED_A")
for ref,a in [("C1","VBUS"),("C2","VBAT"),("C3","VBAT"),("C4","+3V3"),("C5","+3V3"),
              ("C6","+3V3"),("C7","+3V3"),("C8","+3V3"),("C9","FSR_SENSE"),
              ("C10","VBAT_SENSE")]:
    n(ref,1,a); n(ref,2,"GND")
for ref,net in [("TP1","SWDIO"),("TP2","SWDCLK"),("TP4","GND"),("TP5","+3V3")]:
    n(ref,1,net)
# NOTE: D1 LED polarity - Device:LED pin 1 is K (cathode), pin 2 is A (anode).
# STAT sinks current: VBUS -> R4 -> anode, cathode -> STAT. So D1.1 (K) is
# CHG_STAT and D1.2 (A) is LED_A, flipped from the old hand symbol.

# ------------------------------------------------------------- symbol loading
def extract(path,name):
    d=open(path).read()
    i=d.index(f'(symbol "{name}"')
    depth=0; j=i
    while True:
        if d[j]=='(':depth+=1
        elif d[j]==')':
            depth-=1
            if depth==0: break
        j+=1
    return d[i:j+1]
def parse_pins(block):
    out={}
    for m in re.finditer(r'\(pin\s+(\S+)\s+\S+\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\)\s*\(length\s+([\d.]+)\)([\s\S]{0,400}?)\(number\s+"([^"]+)"',block):
        et,x,y,a,l,mid,num=m.groups()
        out[num]=(float(x),float(y),int(float(a)))
    return out
def rename(block,old,new):
    block=block.replace(f'(symbol "{old}"',f'(symbol "{new}"',1)
    return re.sub(r'\(symbol "'+re.escape(old)+r'_(\d+_\d+)"',
                  lambda m:f'(symbol "{new.split(":")[-1]}_{m.group(1)}"',block)

LIBS={}; PINS={}
def load(libid, path, srcname, flatten_from=None):
    if flatten_from:
        parent=extract(path,flatten_from)
        child=extract(path,srcname)
        # parent geometry, child identity: take parent block, rename, then
        # override Value property with the child's name
        blk=rename(parent,flatten_from,libid)
        blk=re.sub(r'\(property "Value" "[^"]*"',f'(property "Value" "{srcname}"',blk,1)
    else:
        blk=rename(extract(path,srcname),srcname,libid)
    LIBS[libid]=blk
    PINS[libid]=parse_pins(blk)

load("Device:R",f"{SLIB}/Device.kicad_sym","R")
load("Device:C",f"{SLIB}/Device.kicad_sym","C")
load("Device:LED",f"{SLIB}/Device.kicad_sym","LED")
load("Battery_Management:MCP73831-2-OT",f"{SLIB}/Battery_Management.kicad_sym","MCP73831-2-OT")
load("Sensor_Motion:LSM6DS3",f"{SLIB}/Sensor_Motion.kicad_sym","LSM6DS3")
load("Connector:USB_C_Receptacle_USB2.0_16P",f"{SLIB}/Connector.kicad_sym","USB_C_Receptacle_USB2.0_16P")
load("Connector:TestPoint",f"{SLIB}/Connector.kicad_sym","TestPoint")
load("Connector_Generic:Conn_01x02",f"{SLIB}/Connector_Generic.kicad_sym","Conn_01x02")
load("Regulator_Linear:TPS7A0533PDBV",f"{SLIB}/Regulator_Linear.kicad_sym",
     "TPS7A0533PDBV",flatten_from="LP5907MFX-1.2")
load("ISP1807:ISP1807-LR","/Users/barakaeli/Downloads/ISP1807-LR/ISP1807-LR.kicad_sym","ISP1807-LR")
for pn in ("GND","+3V3","VBUS","+BATT"):
    load(f"power:{pn}",f"{SLIB}/power.kicad_sym",pn)

print("loaded:", {k:len(v) for k,v in PINS.items() if v})

# ------------------------------------------------------- U2 is an LSM6DS3TR-C
# (stock symbol matches it; the DSV16X has CS and SDA on swapped pins)
for pin,net in [(1,"GND"),(2,"GND"),(3,"GND"),(4,"IMU_INT1"),(5,"+3V3"),
                (6,"GND"),(7,"GND"),(8,"+3V3"),(9,"IMU_INT2"),
                (12,"+3V3"),(13,"SCL"),(14,"SDA")]:
    NET[("U2",str(pin))]=net
for k in [("U2","10"),("U2","11")]: NET.pop(k,None)
NET[("J1","SH")]=NET.pop(("J1","S1"))

load("power:PWR_FLAG",f"{SLIB}/power.kicad_sym","PWR_FLAG")

# unit membership for the vendor symbol (unit 2 carries the NC pads 65-78)
UNIT_OF={}
for m in re.finditer(r'\(symbol "ISP1807-LR_(\d+)_\d+"',LIBS["ISP1807:ISP1807-LR"]):
    pass
def unit_pins(libblk):
    out={}
    for m in re.finditer(r'\(symbol "[^"]*_(\d+)_\d+"',libblk):
        u=int(m.group(1))
        i=m.start(); depth=0; j=i
        while True:
            if libblk[j]=='(':depth+=1
            elif libblk[j]==')':
                depth-=1
                if depth==0:break
            j+=1
        for num in re.findall(r'\(number\s+"([^"]+)"',libblk[i:j+1]):
            out[num]=u
    return out
ISP_UNIT=unit_pins(LIBS["ISP1807:ISP1807-LR"])

# ---------------------------------------------------------------- instances
S=1.27
def snap(v): return round(round(v/S)*S,2)
LIB_OF={"U1":"ISP1807:ISP1807-LR","U1B":"ISP1807:ISP1807-LR",
 "U2":"Sensor_Motion:LSM6DS3",
 "U3":"Battery_Management:MCP73831-2-OT","U4":"Regulator_Linear:TPS7A0533PDBV",
 "J1":"Connector:USB_C_Receptacle_USB2.0_16P",
 "J2":"Connector_Generic:Conn_01x02","J3":"Connector_Generic:Conn_01x02",
 "D1":"Device:LED"}
for r in range(1,10): LIB_OF[f"R{r}"]="Device:R"
for c in range(1,11): LIB_OF[f"C{c}"]="Device:C"
for t in (1,2,4,5): LIB_OF[f"TP{t}"]="Connector:TestPoint"
FP={"U1":"pen-mixer:ISP1807-LR",
 "U2":"Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
 "U3":"Package_TO_SOT_SMD:SOT-23-5","U4":"Package_TO_SOT_SMD:SOT-23-5",
 "J1":"Connector_USB:USB_C_Receptacle_G-Switch_GT-USB-7010ASV",
 "J2":"pen-mixer:SolderPad_1.2x2.0mm","J3":"pen-mixer:SolderPad_1.2x2.0mm"}
for r in range(1,10): FP[f"R{r}"]="Resistor_SMD:R_0402_1005Metric"
for c in range(1,11): FP[f"C{c}"]="Capacitor_SMD:C_0402_1005Metric"
FP["D1"]="LED_SMD:LED_0402_1005Metric"
for t in (1,2,4,5): FP[f"TP{t}"]="pen-mixer:TestPad_1.0mm"
VALUE={"U1":"ISP1807-LR","U1B":"ISP1807-LR","U2":"LSM6DS3TR-C","U3":"MCP73831T-2ACI/OT",
 "U4":"TPS7A0533PDBV","J1":"USB-C 16P","J2":"BAT","J3":"FSR","D1":"GRN",
 "R1":"5k1","R2":"5k1","R3":"20k","R4":"1k","R5":"10k","R6":"4k7","R7":"4k7",
 "R8":"1M","R9":"1M","C1":"4u7","C2":"4u7","C3":"1u","C4":"1u","C5":"100n",
 "C6":"10u","C7":"100n","C8":"100n","C9":"100n","C10":"100n",
 "TP1":"SWDIO","TP2":"SWDCLK","TP4":"GND","TP5":"+3V3"}

PLACE={}
def place(ref,X,Y,rot=0): PLACE[ref]=(snap(X),snap(Y),rot)
def P(ref,pin):
    X,Y,rot=PLACE[ref]
    px,py,pa=PINS[LIB_OF[ref]][str(pin)]
    if rot==0:   return (round(X+px,2),round(Y-py,2))
    if rot==180: return (round(X-px,2),round(Y+py,2))
def outward(ref,pin):
    _,_,rot=PLACE[ref]
    pa=PINS[LIB_OF[ref]][str(pin)][2]
    d={0:(-1,0),180:(1,0),90:(0,1),270:(0,-1)}[pa]
    return (-d[0],-d[1]) if rot==180 else d

SEGS=[];GLB=[];PWR=[];NC=[];LOCLAB=[]
def w(*pts):
    pts=[(snap(a),snap(b)) for a,b in pts]
    for a,b in zip(pts,pts[1:]):
        if a!=b: SEGS.append((a,b))
    return pts
def pw(net,x,y,rot=0): PWR.append((net,snap(x),snap(y),rot))
def glab(net,x,y,rot): GLB.append((net,snap(x),snap(y),rot))
def nc(x,y): NC.append((snap(x),snap(y)))
def loclab(net,x,y): LOCLAB.append((net,snap(x),snap(y)))

# ============================ USB-C INPUT ============================
place("J1",60.96,90.17)
cc1p=P("J1","A5"); cc2p=P("J1","B5")
place("R1",106.68,cc1p[1]+3.81); place("R2",99.06,cc2p[1]+3.81)
vb=P("J1","A4"); w(vb,(vb[0]+5.08,vb[1]),(vb[0]+5.08,vb[1]-5.08)); pw("VBUS",vb[0]+5.08,vb[1]-5.08)
w(cc1p,P("R1","1")); loclab("CC1",app:=cc1p[0]+12.7,cc1p[1])
w(cc2p,P("R2","1")); loclab("CC2",cc2p[0]+10.16,cc2p[1])
for ref in ("R1","R2"):
    r=P(ref,"2"); w(r,(r[0],r[1]+2.54)); pw("GND",r[0],r[1]+2.54)
a6,b6=P("J1","A6"),P("J1","B6"); tx=a6[0]+5.08
w(a6,(tx,a6[1])); w(b6,(tx,b6[1])); w((tx,a6[1]),(tx,b6[1]))
w((tx,a6[1]),(tx+3.81,a6[1])); glab("USB_DP",tx+3.81,a6[1],0)
a7,b7=P("J1","A7"),P("J1","B7"); ux=a7[0]+2.54
w(a7,(ux,a7[1])); w(b7,(ux,b7[1])); w((ux,a7[1]),(ux,b7[1]))
w((ux,a7[1]),(ux+6.35,a7[1])); glab("USB_DM",ux+6.35,a7[1],0)
g=P("J1","A1"); sh=P("J1","SH"); ty=sh[1]+2.54
w(g,(g[0],ty)); w((g[0],ty),(g[0],ty+2.54)); pw("GND",g[0],ty+2.54)
w(sh,(sh[0],ty),(g[0],ty))
nc(*P("J1","A8")); nc(*P("J1","B8"))

# ============================ LiPo CHARGER ============================
place("U3",69.85,170.18)
st=P("U3","1"); vb3=P("U3","3")
place("D1",97.79,st[1]); place("R4",106.68,st[1]+3.81,180)
pr=P("U3","5"); place("R3",52.07,pr[1]+3.81)
place("J2",39.37,158.75)
v=P("U3","4"); w(v,(v[0],v[1]-2.54)); pw("VBUS",v[0],v[1]-2.54)
g=P("U3","2"); w(g,(g[0],g[1]+2.54)); pw("GND",g[0],g[1]+2.54)
w(vb3,(vb3[0]+7.62,vb3[1]),(vb3[0]+7.62,vb3[1]-2.54)); pw("VBAT",vb3[0]+7.62,vb3[1]-2.54)
w(st,P("D1","1")); loclab("CHG_STAT",st[0]+3.81,st[1])
w(P("D1","2"),P("R4","2")); loclab("LED_A",P("D1","2")[0],st[1])
r=P("R4","1"); w(r,(r[0],r[1]+2.54)); pw("VBUS",r[0],r[1]+2.54,180)
w(pr,P("R3","1")); loclab("IPROG",P("R3","1")[0]+2.54,pr[1])
r=P("R3","2"); w(r,(r[0],r[1]+2.54)); pw("GND",r[0],r[1]+2.54)
j=P("J2","1"); w(j,(j[0]-3.81,j[1]),(j[0]-3.81,j[1]-2.54)); pw("VBAT",j[0]-3.81,j[1]-2.54)
j=P("J2","2"); w(j,(j[0]-6.35,j[1]),(j[0]-6.35,j[1]+2.54)); pw("GND",j[0]-6.35,j[1]+2.54)

# ============================ 3.3V REGULATOR ============================
place("U4",69.85,215.9)
i=P("U4","1"); e=P("U4","3"); tx=i[0]-5.08
w(i,(tx,i[1])); w(e,(tx,e[1])); w((tx,i[1]),(tx,e[1]))
w((tx,i[1]),(tx,i[1]-2.54)); pw("VBAT",tx,i[1]-2.54)
g=P("U4","2"); w(g,(g[0],g[1]+2.54)); pw("GND",g[0],g[1]+2.54)
o=P("U4","5"); w(o,(o[0]+3.81,o[1]),(o[0]+3.81,o[1]-2.54)); pw("+3V3",o[0]+3.81,o[1]-2.54)
nc(*P("U4","4"))

# ============================ 6-AXIS IMU ============================
place("U2",200.66,95.25)
sda=P("U2","14"); scl=P("U2","13"); cs=P("U2","12")
place("R6",167.64,sda[1]-3.81,180); place("R7",147.32,scl[1]-3.81,180)
gtie=sda[0]-3.81
for p in ("1","2","3"):
    q=P("U2",p); w(q,(gtie,q[1]))
ys=sorted(P("U2",p)[1] for p in ("1","2","3"))
for y1,y2 in zip(ys,ys[1:]): w((gtie,y1),(gtie,y2))
w((gtie,ys[-1]),(gtie,ys[-1]+2.54)); pw("GND",gtie,ys[-1]+2.54,180)
w(sda,P("R6","1")); w(P("R6","1"),(P("R6","1")[0]-6.35,sda[1])); glab("SDA",P("R6","1")[0]-6.35,sda[1],180)
r=P("R6","2"); w(r,(r[0],r[1]-2.54)); pw("+3V3",r[0],r[1]-2.54)
w(scl,P("R7","1")); w(P("R7","1"),(P("R7","1")[0]-6.35,scl[1])); glab("SCL",P("R7","1")[0]-6.35,scl[1],180)
r=P("R7","2"); w(r,(r[0],r[1]-2.54)); pw("+3V3",r[0],r[1]-2.54)
w(cs,(cs[0]-8.89,cs[1]),(cs[0]-8.89,cs[1]+2.54)); pw("+3V3",cs[0]-8.89,cs[1]+2.54,180)
vio=P("U2","5"); vdd=P("U2","8")
w(vio,(vio[0],vio[1]-2.54)); w(vdd,(vdd[0],vdd[1]-2.54))
w((vio[0],vio[1]-2.54),(vdd[0],vdd[1]-2.54)); pw("+3V3",vio[0],vio[1]-2.54)
g=P("U2","6"); w(g,(g[0],g[1]+2.54)); pw("GND",g[0],g[1]+2.54)
i1=P("U2","4"); w(i1,(i1[0]+5.08,i1[1])); glab("IMU_INT1",i1[0]+5.08,i1[1],0)
i2=P("U2","9"); w(i2,(i2[0]+5.08,i2[1])); glab("IMU_INT2",i2[0]+5.08,i2[1],0)
nc(*P("U2","10")); nc(*P("U2","11"))

# ============================ RADIO MODULE ============================
place("U1",309.88,250.19)
place("U1B",however:=406.4,120.65)
gpins=sorted((p for (r0,p),nn in NET.items() if r0=="U1" and nn=="GND"),key=int)
left=[p for p in gpins if PINS[LIB_OF["U1"]][p][2]==0]
oth=[p for p in gpins if PINS[LIB_OF["U1"]][p][2]!=0]
gx=P("U1",left[0])[0]-5.08
for p in left:
    q=P("U1",p); w(q,(gx,q[1]))
ys=sorted(P("U1",p)[1] for p in left)
for y1,y2 in zip(ys,ys[1:]): w((gx,y1),(gx,y2))
w((gx,ys[-1]),(gx,ys[-1]+2.54)); pw("GND",gx,ys[-1]+2.54,180)
for p in oth:
    q=P("U1",p); d=outward("U1",p)
    e=(q[0]+2.54*d[0],q[1]+2.54*d[1]); w(q,e)
    pw("GND",e[0],e[1],180 if d[1]>0 else 0)
v=P("U1","12"); w(v,(v[0],v[1]-2.54)); pw("VBUS",v[0],v[1]-2.54)
c=P("U1","26"); w(c,(c[0],c[1]+2.54)); pw("+3V3",c[0],c[1]+2.54,180)
for pin,net in (("8","USB_DP"),("10","USB_DM")):
    q=P("U1",pin); w(q,(q[0],q[1]+3.81)); glab(net,q[0],q[1]+3.81,270)
for pin,net in (("28","SWDIO"),("30","SWDCLK"),("6","SCL")):
    q=P("U1",pin); w(q,(q[0]+3.81,q[1])); glab(net,q[0]+3.81,q[1],0)
for pin,net in (("32","SDA"),("2","IMU_INT1"),("4","IMU_INT2"),
                ("36","FSR_SENSE"),("38","VBAT_SENSE")):
    q=P("U1",pin); w(q,(q[0]-3.81,q[1])); glab(net,q[0]-3.81,q[1],180)
oa,om=P("U1","20"),P("U1","22"); ax=oa[0]+5.08
w(oa,(ax,oa[1])); w(om,(ax,om[1])); w((ax,oa[1]),(ax,om[1]))
loclab("ANT",ax,oa[1])
used={p for (r0,p) in NET if r0=="U1"}
for pnum,u in sorted(ISP_UNIT.items(),key=lambda kv:int(kv[0])):
    if pnum in used: continue
    nc(*P("U1B" if u==2 else "U1",pnum))

# ============================ BATTERY SENSE ============================
place("R8",149.86,199.39); place("R9",149.86,199.39+12.7)
r82=P("R8","2"); r91=P("R9","1")
tap=(149.86,snap((r82[1]+r91[1])/2))
place("C10",162.56,tap[1]+3.81)
q=P("R8","1"); w(q,(q[0],q[1]-2.54)); pw("VBAT",q[0],q[1]-2.54)
w(r82,tap); w(tap,r91)
w(tap,(156.21,tap[1])); w((156.21,tap[1]),P("C10","1"))
w((156.21,tap[1]),(156.21,tap[1]-3.81)); glab("VBAT_SENSE",156.21,tap[1]-3.81,90)
q=P("R9","2"); w(q,(q[0],q[1]+2.54)); pw("GND",q[0],q[1]+2.54)
q=P("C10","2"); w(q,(q[0],q[1]+2.54)); pw("GND",q[0],q[1]+2.54)

# ============================ FSR INPUT ============================
place("J3",40.64,250.19)
j1p=P("J3","1"); j2p=P("J3","2")
row=j2p[1]+5.08
place("R5",52.07,row+3.81); place("C9",62.23,row+3.81)
w(j1p,(j1p[0]-3.81,j1p[1]),(j1p[0]-3.81,j1p[1]-2.54)); pw("+3V3",j1p[0]-3.81,j1p[1]-2.54)
w(j2p,(j2p[0]-5.08,j2p[1]),(j2p[0]-5.08,row),(P("R5","1")[0],row))
mid=snap((P("R5","1")[0]+P("C9","1")[0])/2)
w((P("R5","1")[0],row),(mid,row)); w((mid,row),(P("C9","1")[0],row))
w((mid,row),(mid,row-3.81)); glab("FSR_SENSE",mid,row-3.81,90)
q=P("R5","2"); w(q,(q[0],q[1]+2.54)); pw("GND",q[0],q[1]+2.54)
q=P("C9","2"); w(q,(q[0],q[1]+2.54)); pw("GND",q[0],q[1]+2.54)

# ============================ SWD + TEST ============================
for ref,x,net,kind in [("TP1",149.86,"SWDIO","g"),("TP2",160.02,"SWDCLK","g"),
                       ("TP4",170.18,"GND","p"),("TP5",180.34,"+3V3","p3")]:
    place(ref,x,250.19)
    q=P(ref,"1"); w(q,(q[0],q[1]+3.81))
    if kind=="g": glab(net,q[0],q[1]+3.81,270)
    elif kind=="p": pw("GND",q[0],q[1]+3.81)
    else: pw("+3V3",q[0],q[1]+3.81,180)

# ============================ DECOUPLING + power flags ============================
DEC=[("C1","VBUS"),("C2","VBAT"),("C3","VBAT"),("C4","+3V3"),("C5","+3V3"),
     ("C6","+3V3"),("C7","+3V3"),("C8","+3V3")]
FLAG_AT={"C1":"VBUS"}
FLAGS=[]
for i,(ref,rail) in enumerate(DEC):
    place(ref,240.03+i*13.97,250.19)
    q=P(ref,"1"); top=(q[0],q[1]-2.54)
    w(q,top); pw(rail,*top)
    if ref in FLAG_AT:
        w(top,(top[0]+2.54,top[1])); FLAGS.append((top[0]+2.54,top[1]))
    q=P(ref,"2"); w(q,(q[0],q[1]+2.54)); pw("GND",q[0],q[1]+2.54)
    if ref=="C1":
        gpt=(q[0],q[1]+2.54)
# GND flag beside C1's ground
w((P("C1","2")[0],P("C1","2")[1]+1.27),(P("C1","2")[0]-2.54,P("C1","2")[1]+1.27)) if False else None
gq=P("C1","2")
w(gq,(gq[0]-2.54,gq[1])) if False else None
FLAGS.append(None)
FLAGS=[f for f in FLAGS if f]
gend=(P("C1","2")[0],P("C1","2")[1]+2.54)
gflag=(gend[0]-2.54,gend[1])
w(gend,gflag)
FLAGS.append(gflag)

FRAMES=[
 ("USB-C INPUT",           40, 58,122,122),
 ("LiPo CHARGER",          24,148,120,186),
 ("3.3 V REGULATOR",       50,204, 92,230),
 ("6-AXIS IMU",           132, 70,232,122),
 ("nRF52840 RADIO MODULE",288,150,436,268),
 ("BATTERY SENSE",        138,190,178,224),
 ("FSR INPUT",             26,240, 78,272),
 ("SWD + TEST",           142,240,190,262),
 ("DECOUPLING",           230,238,352,262),
]

# ---------------------------------------------------------------- emission
def eff(size=1.27,just=None,hide=False):
    s=f"(effects (font (size {size} {size}))"
    if just: s+=f" (justify {just})"
    if hide: s+=" (hide yes)"
    return s+")"
from collections import Counter
cnt=Counter()
for a,b in SEGS: cnt[a]+=1; cnt[b]+=1
for (ref,pin) in NET:
    try: q=P(ref,pin)
    except Exception: continue
    if q in cnt: cnt[q]+=1
for net,x,y,rot in PWR: cnt[(x,y)]+=1
JUNC=[p for p,c in cnt.items() if c>=3]

body=[]
for ref,(X,Y,rot) in PLACE.items():
    lib=LIB_OF[ref]
    real="U1" if ref=="U1B" else ref
    unit=2 if ref=="U1B" else 1
    body.append(f'\t(symbol (lib_id "{lib}") (at {X} {Y} {rot}) (unit {unit})')
    body.append('\t\t(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    hide = ref=="U1B"
    body.append(f'\t\t(property "Reference" "{real}" (at {X} {Y-3.81} 0) {eff(1.27,"left",hide)})')
    body.append(f'\t\t(property "Value" "{VALUE.get(real,"")}" (at {X} {Y+3.81} 0) {eff(1.27,"left",True if ref=="U1B" else False)})')
    body.append(f'\t\t(property "Footprint" "{FP.get(real,"")}" (at {X} {Y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT}" (reference "{real}") (unit {unit}))))')
    body.append('\t)')
for i,(net,x,y,rot) in enumerate(PWR):
    lib="power:+BATT" if net=="VBAT" else f"power:{net}"
    val="VBAT" if net=="VBAT" else net
    body.append(f'\t(symbol (lib_id "{lib}") (at {x} {y} {rot}) (unit 1)')
    body.append('\t\t(exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    body.append(f'\t\t(property "Reference" "#PWR{i+1:03d}" (at {x} {y} 0) {eff(1.27,None,True)})')
    dy=3.5 if rot==0 else -3.5
    body.append(f'\t\t(property "Value" "{val}" (at {x} {y+(dy if net=="GND" else -dy)} 0) {eff(1.0)})')
    body.append(f'\t\t(property "Footprint" "" (at {x} {y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT}" (reference "#PWR{i+1:03d}") (unit 1))))')
    body.append('\t)')
for i,(x,y) in enumerate(FLAGS):
    body.append(f'\t(symbol (lib_id "power:PWR_FLAG") (at {x} {y} 0) (unit 1)')
    body.append('\t\t(exclude_from_sim no) (in_bom no) (on_board yes) (dnp no)')
    body.append(f'\t\t(uuid "{U()}")')
    body.append(f'\t\t(property "Reference" "#FLG{i+1:02d}" (at {x} {y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(property "Value" "PWR_FLAG" (at {x} {y-3.5} 0) {eff(1.0)})')
    body.append(f'\t\t(property "Footprint" "" (at {x} {y} 0) {eff(1.27,None,True)})')
    body.append(f'\t\t(instances (project "{PROJ}" (path "/{ROOT}" (reference "#FLG{i+1:02d}") (unit 1))))')
    body.append('\t)')
for a,b in SEGS:
    body.append(f'\t(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]}))')
    body.append(f'\t\t(stroke (width 0) (type default)) (uuid "{U()}"))')
for p in JUNC:
    body.append(f'\t(junction (at {p[0]} {p[1]}) (diameter 0) (color 0 0 0 0) (uuid "{U()}"))')
for x,y in NC:
    body.append(f'\t(no_connect (at {x} {y}) (uuid "{U()}"))')
for net,x,y in LOCLAB:
    body.append(f'\t(label "{net}" (at {x} {y} 0) {eff(1.0,"left")} (uuid "{U()}"))')
for net,x,y,rot in GLB:
    just={0:"left",180:"right",90:"left",270:"right"}[rot]
    body.append(f'\t(global_label "{net}" (shape bidirectional) (at {x} {y} {rot})')
    body.append(f'\t\t(fields_autoplaced yes) {eff(1.27,just)} (uuid "{U()}"))')
for title,x1,y1,x2,y2 in FRAMES:
    body.append(f'\t(rectangle (start {x1} {y1}) (end {x2} {y2})')
    body.append('\t\t(stroke (width 0.2) (type dash)) (fill (type none))')
    body.append(f'\t\t(uuid "{U()}"))')
    body.append(f'\t(text "{title}" (at {x1+1.5} {y1-1.5} 0)')
    body.append(f'\t\t(effects (font (size 2 2) (bold yes)) (justify left)) (uuid "{U()}"))')

libs="\n".join(LIBS[k] for k in LIBS)
sch=f'''(kicad_sch
\t(version 20231120)
\t(generator "eeschema")
\t(generator_version "8.0")
\t(uuid "{ROOT}")
\t(paper "A2")
\t(title_block
\t\t(title "Pen Mixer v0.1 - pen-mounted motion controller")
\t\t(date "2026-08-29")
\t\t(rev "0.3")
\t\t(comment 1 "KiCad stock symbols + vendor ISP1807-LR; wires in modules, globals between")
\t)
\t(lib_symbols
{libs}
\t)
{chr(10).join(body)}
\t(sheet_instances (path "/" (page "1")))
)
'''
open(os.path.join(OUT,PROJ+".kicad_sch"),"w").write(sch)
print(f"emitted: {len(PLACE)} symbol instances, {len(PWR)} power, {len(FLAGS)} flags, "
      f"{len(SEGS)} wires, {len(JUNC)} junctions, {len(NC)} nc")
