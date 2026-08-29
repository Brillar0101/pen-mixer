#!/usr/bin/env python3
"""Build the Stylus Mixer v0.1 board: 4-layer, 0.6mm, 11 x 42 mm.
Nets are taken from the exported schematic netlist so the two can't drift."""
import pcbnew, os, re, sys
from pcbnew import VECTOR2I, FromMM as MM

OUT  = "/Users/barakaeli/Desktop/stylus-mixer-hw"
KFP  = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
MYFP = os.path.join(OUT, "stylus.pretty")
BW, BH = 11.0, 42.0          # board width / height in mm
X0, Y0 = 100.0, 60.0         # board origin on the sheet

# ---- ref/pad -> net, straight from the schematic netlist -------------------
xml = open(os.path.join(OUT, "net.xml")).read()
NET = {}
for m in re.finditer(r'<net code="\d+" name="([^"]+)"(.*?)</net>', xml, re.S):
    name = m.group(1)
    if name.startswith("unconnected-"): continue
    for nd in re.finditer(r'<node ref="([^"]+)" pin="([^"]+)"', m.group(2)):
        NET[(nd.group(1), nd.group(2))] = name

# ---- footprint library for each ref ---------------------------------------
LIBFP = {
 "U1": (MYFP, "ISP1807_LGA78_8x8mm"),
 "U2": (KFP+"/Package_LGA.pretty", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y"),
 "U3": (KFP+"/Package_TO_SOT_SMD.pretty", "SOT-23-5"),
 "U4": (KFP+"/Package_SON.pretty", "Texas_X2SON-4_1x1mm_P0.65mm"),
 "J1": (KFP+"/Connector_USB.pretty", "USB_C_Receptacle_G-Switch_GT-USB-7010ASV"),
 "J2": (MYFP, "SolderPad_1.2x2.0mm"),
 "J3": (MYFP, "SolderPad_1.2x2.0mm"),
 "D1": (KFP+"/LED_SMD.pretty", "LED_0402_1005Metric"),
}
for r in range(1,10):  LIBFP[f"R{r}"]  = (KFP+"/Resistor_SMD.pretty","R_0402_1005Metric")
for c in range(1,11):  LIBFP[f"C{c}"]  = (KFP+"/Capacitor_SMD.pretty","C_0402_1005Metric")
for t in range(1,6):   LIBFP[f"TP{t}"] = (MYFP,"TestPad_1.0mm")

# ---- placement: (ref, x, y, rot, back?) local mm from board top-left ------
#  antenna end of U1 faces y=0 (rot 180); USB-C at the far end.
PLACE = {
 "U1": (5.5,  8.0, 180, False),
 "U2": (3.4, 16.5,   0, False),
 "U4": (8.6, 16.2,   0, False),
 "C5": (8.6, 14.0,   0, False), "C6": (8.6, 18.4,  0, False),
 "C7": (3.4, 14.0,   0, False), "C8": (3.4, 18.6,  0, False),
 "R6": (1.6, 20.4,  90, False), "R7": (3.4, 20.4, 90, False),
 "C3": (6.0, 20.4,  90, False), "C4": (8.4, 20.4, 90, False),
 "U3": (3.2, 23.6,   0, False),
 "R3": (7.0, 23.0,  90, False), "C1": (9.0, 23.0, 90, False),
 "C2": (7.0, 25.4,  90, False), "R4": (9.0, 25.4, 90, False),
 "D1": (3.2, 26.6,   0, False),
 "R8": (1.8, 29.0,  90, False), "R9": (3.8, 29.0, 90, False),
 "C10":(5.8, 29.0,  90, False), "C9": (7.8, 29.0, 90, False),
 "R5": (9.6, 29.0,  90, False),
 "J2": (2.2, 33.0,   0, False), "J3": (8.8, 33.0,  0, False),
 "R1": (4.6, 32.2,  90, False), "R2": (6.4, 32.2, 90, False),
 "J1": (5.5, 40.4,   0, False),
 # test pads on the back, in a pogo-friendly row
 "TP1":(2.0, 24.0,   0, True), "TP2":(4.0, 24.0, 0, True),
 "TP3":(6.0, 24.0,   0, True), "TP4":(8.0, 24.0, 0, True),
 "TP5":(5.0, 26.5,   0, True),
}
VALUE = {"R1":"5k1","R2":"5k1","R3":"20k","R4":"1k","R5":"10k","R6":"4k7","R7":"4k7",
 "R8":"1M","R9":"1M","C1":"4u7","C2":"4u7","C3":"1u","C4":"1u","C5":"100n","C6":"10u",
 "C7":"100n","C8":"100n","C9":"100n","C10":"100n","U1":"ISP1807-LR","U2":"LSM6DSV16X",
 "U3":"MCP73831T-2ACI/OT","U4":"TPS7A0233DQN","J1":"USB-C 16P","J2":"BAT","J3":"FSR",
 "D1":"GRN","TP1":"SWDIO","TP2":"SWDCLK","TP3":"nRESET","TP4":"GND","TP5":"+3V3"}

board = pcbnew.NewBoard(os.path.join(OUT, "stylus-mixer.kicad_pcb"))
ds = board.GetDesignSettings()
board.SetCopperLayerCount(4)
ds.m_MinClearance = MM(0.09)
ds.m_CopperEdgeClearance = MM(0.20)   # JLCPCB capable
ds.m_HoleClearance = MM(0.20)
board.SetLayerName(pcbnew.In1_Cu, "GND"); board.SetLayerName(pcbnew.In2_Cu, "PWR")

nets = {}
def net_of(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); nets[name] = ni
    return nets[name]

placed, missing = 0, []
for ref,(lib,fpname) in LIBFP.items():
    if ref not in PLACE: missing.append(ref+" (no placement)"); continue
    fp = pcbnew.FootprintLoad(lib, fpname)
    if fp is None: missing.append(f"{ref}: {fpname} not found"); continue
    board.Add(fp)
    x,y,rot,back = PLACE[ref]
    fp.SetPosition(VECTOR2I(MM(X0+x), MM(Y0+y)))
    if back: fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(rot)
    fp.SetReference(ref); fp.SetValue(VALUE.get(ref,""))
    fp.Reference().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab)
    fp.Reference().SetVisible(True)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.5), MM(0.5)))
    fp.Reference().SetTextThickness(MM(0.08))
    fp.Value().SetLayer(pcbnew.B_Fab if back else pcbnew.F_Fab); fp.Value().SetVisible(False)
    for pad in fp.Pads():
        nm = NET.get((ref, pad.GetNumber()))
        if nm: pad.SetNet(net_of(nm))
        elif ref == "U4" and pad.GetNumber() == "5": pad.SetNet(net_of("GND"))
    placed += 1

# ---- board outline, rounded ends ------------------------------------------
def seg(x1,y1,x2,y2):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(MM(X0+x1),MM(Y0+y1))); s.SetEnd(VECTOR2I(MM(X0+x2),MM(Y0+y2)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
def arc(cx,cy,sx,sy,ex,ey):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(VECTOR2I(MM(X0+cx),MM(Y0+cy)))
    s.SetStart(VECTOR2I(MM(X0+sx),MM(Y0+sy))); s.SetEnd(VECTOR2I(MM(X0+ex),MM(Y0+ey)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
R = 2.0
seg(0,R,0,BH-R); seg(BW,R,BW,BH-R); seg(R,0,BW-R,0); seg(R,BH,BW-R,BH)
arc(R,R,0,R,R,0); arc(BW-R,R,BW-R,0,BW,R)
arc(R,BH-R,R,BH,0,BH-R); arc(BW-R,BH-R,BW,BH-R,BW-R,BH)

# ---- copper pours: GND on F/In1/B, +3V3 on In2, antenna keep-out ---------
def zone(layer, netname, y_from, y_to, prio=0):
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(net_of(netname))
    z.SetAssignedPriority(prio); z.SetLocalClearance(MM(0.3))
    z.SetMinThickness(MM(0.15)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    o = z.Outline(); o.NewOutline()
    for px,py in [(0.4,y_from),(BW-0.4,y_from),(BW-0.4,y_to),(0.4,y_to)]:
        o.Append(MM(X0+px), MM(Y0+py))
    board.Add(z); return z

ANT_CLEAR = 7.2    # antenna occupies board y 4.0-6.4; clear to the near edge
for lyr in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.B_Cu):
    zone(lyr, "GND", ANT_CLEAR, BH-0.4)
zone(pcbnew.In2_Cu, "+3V3", ANT_CLEAR, BH-0.4)

# keep-out rule area over the antenna
ko = pcbnew.ZONE(board)
ko.SetIsRuleArea(True)
ko.SetDoNotAllowZoneFills(True); ko.SetDoNotAllowTracks(True)
ko.SetDoNotAllowVias(True); ko.SetDoNotAllowPads(False)
ko.SetLayerSet(pcbnew.LSET.AllCuMask())
o = ko.Outline(); o.NewOutline()
for px,py in [(0,0),(BW,0),(BW,ANT_CLEAR),(0,ANT_CLEAR)]:
    o.Append(MM(X0+px), MM(Y0+py))
board.Add(ko)

# explicit copper knockouts around the USB-C shell mounting holes
for hx, hy in [(2.61, 37.795), (8.39, 37.795)]:
    k = pcbnew.ZONE(board); k.SetIsRuleArea(True)
    k.SetDoNotAllowZoneFills(True); k.SetLayerSet(pcbnew.LSET.AllCuMask())
    k.SetDoNotAllowPads(False); k.SetDoNotAllowTracks(False)
    k.SetDoNotAllowVias(False); k.SetDoNotAllowFootprints(False)
    ko2 = k.Outline(); ko2.NewOutline()
    for dx,dy in [(-0.62,-0.62),(0.62,-0.62),(0.62,0.62),(-0.62,0.62)]:
        ko2.Append(MM(X0+hx+dx), MM(Y0+hy+dy))
    board.Add(k)

filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
board.Save(os.path.join(OUT, "stylus-mixer.kicad_pcb"))

print(f"placed {placed}/{len(LIBFP)} footprints, {len(nets)} nets")
if missing: print("PROBLEMS:", missing)
rat = board.GetConnectivity().GetUnconnectedCount(False)
print("board", BW, "x", BH, "mm, 4 layers, unrouted connections:", rat)
