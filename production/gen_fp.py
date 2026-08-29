#!/usr/bin/env python3
"""Custom footprints for Stylus Mixer v0.1.
ISP1807 land pattern DERIVED from isp_ble_DS1807_R19 sections 3 (pad map) and
4.2 (SMT guidelines: 0.4x0.4mm standard pads, 0.8x0.8mm corner pads, 0.65mm
pitch, double row + centre array).  ** VERIFY against Insight SiP's official
land pattern before releasing to fab. **"""
import os
LIB = "/Users/barakaeli/Desktop/stylus-mixer-hw/stylus.pretty"
os.makedirs(LIB, exist_ok=True)

P = 0.65          # pitch
OUT_INSET = 0.375 # outer ring centre inset from body edge
IN_INSET  = OUT_INSET + P
STD, COR = 0.40, 0.80
B = 8.0; H = B/2

pads = []   # (number, x, y, w, h)
def add(n,x,y,w=STD,h=STD): pads.append((n,round(x,4),round(y,4),w,h))

# --- top edge (y = -H+inset ; KiCad y grows downward) --------------------
top_out = [48,46,44,42,40,38,36,34,32]          # 9 pads, left -> right
top_in  = [47,45,43,41,39,37,35,33]             # 8 pads, offset half pitch
for i,n in enumerate(top_out): add(n, (i-4)*P, -H+OUT_INSET)
for i,n in enumerate(top_in):  add(n, (i-3.5)*P, -H+IN_INSET)
# --- corners (outer ring, 0.8mm) ----------------------------------------
add(1,  -H+OUT_INSET-0.05, -H+OUT_INSET, COR, COR)
add(31,  H-OUT_INSET+0.05, -H+OUT_INSET, COR, COR)
add(7,  -H+OUT_INSET-0.05, -H+OUT_INSET+5*P, COR, COR)
add(25,  H-OUT_INSET+0.05, -H+OUT_INSET+5*P, COR, COR)
# --- left / right edges --------------------------------------------------
for i,n in enumerate([2,4,6]):   add(n, -H+OUT_INSET, -H+OUT_INSET+(i+1)*P+0.35)
for i,n in enumerate([3,5]):     add(n, -H+IN_INSET,  -H+OUT_INSET+(i+1.5)*P+0.35)
for i,n in enumerate([30,28,26]):add(n,  H-OUT_INSET, -H+OUT_INSET+(i+1)*P+0.35)
for i,n in enumerate([29,27]):   add(n,  H-IN_INSET,  -H+OUT_INSET+(i+1.5)*P+0.35)
# --- bottom of the pad field --------------------------------------------
bot_out = [8,10,12,14,16,18,20,22,24]
bot_in  = [9,11,13,15,17,19,21,23]
yb = -H+OUT_INSET+6*P
for i,n in enumerate(bot_out): add(n, (i-4)*P, yb)
for i,n in enumerate(bot_in):  add(n, (i-3.5)*P, yb-P)
# --- centre 2x8 array ----------------------------------------------------
row1 = [56,55,54,53,52,51,50,49]
row2 = [64,63,62,61,60,59,58,57]
for i,n in enumerate(row1): add(n, (3.5-i)*P, -H+OUT_INSET+2*P)
for i,n in enumerate(row2): add(n, (3.5-i)*P, -H+OUT_INSET+4*P)
# --- NC mechanical pads around the antenna region ------------------------
nc_y0 = yb + 0.9
add(65,-H+OUT_INSET,nc_y0);      add(78, H-OUT_INSET,nc_y0)
add(66,-H+OUT_INSET,nc_y0+0.75); add(77, H-OUT_INSET,nc_y0+0.75)
add(67,-H+OUT_INSET,nc_y0+1.5);  add(76, H-OUT_INSET,nc_y0+1.5)
add(68,-H+OUT_INSET-0.05,H-OUT_INSET,COR,COR); add(75,H-OUT_INSET+0.05,H-OUT_INSET,COR,COR)
for i,n in enumerate([69,70,71,72,73,74]): add(n,(i-2.5)*0.95, H-OUT_INSET)

lines = ['(footprint "ISP1807_LGA78_8x8mm"',
 '\t(version 20240108) (generator "hand") (generator_version "8.0")',
 '\t(layer "F.Cu")',
 '\t(descr "Insight SiP ISP1807 nRF52840 module 8x8x0.95mm 78-pad LGA. '
 'Land pattern DERIVED from datasheet - VERIFY before fab. Antenna occupies '
 'the +Y end: keep all copper clear on every layer under that region.")',
 '\t(tags "ISP1807 nRF52840 BLE module LGA")',
 '\t(attr smd)',
 '\t(property "Reference" "U**" (at 0 -5.2 0) (layer "F.SilkS") (uuid "r1")',
 '\t\t(effects (font (size 0.8 0.8) (thickness 0.12))))',
 '\t(property "Value" "ISP1807" (at 0 5.4 0) (layer "F.Fab") (uuid "v1")',
 '\t\t(effects (font (size 0.8 0.8) (thickness 0.12))))']
# courtyard + fab outline
for lyr,w,off in [("F.CrtYd",0.05,0.25),("F.Fab",0.10,0.0)]:
    lines.append(f'\t(fp_rect (start {-H-off} {-H-off}) (end {H+off} {H+off}) '
                 f'(stroke (width {w}) (type default)) (fill none) (layer "{lyr}") (uuid "c{lyr}"))')
# pin-1 marker
lines.append('\t(fp_circle (center -4.6 -4.6) (end -4.4 -4.6) (stroke (width 0.12) '
             '(type default)) (fill solid) (layer "F.SilkS") (uuid "p1m"))')
# antenna keep-out marker on fab layer
lines.append('\t(fp_rect (start -4 1.6) (end 4 4) (stroke (width 0.1) (type dash)) '
             '(fill none) (layer "F.Fab") (uuid "ant"))')
lines.append('\t(fp_text user "ANT KEEPOUT" (at 0 2.8 0) (layer "F.Fab") (uuid "antt") '
             '(effects (font (size 0.5 0.5) (thickness 0.08))))')
for n,x,y,w,h in pads:
    lines.append(f'\t(pad "{n}" smd rect (at {x} {y}) (size {w} {h}) '
                 f'(layers "F.Cu" "F.Paste" "F.Mask") (uuid "pad{n}"))')
lines.append(')')
open(os.path.join(LIB,"ISP1807_LGA78_8x8mm.kicad_mod"),"w").write("\n".join(lines))

def simple(name, descr, pads_):
    s=[f'(footprint "{name}"','\t(version 20240108) (generator "hand") (generator_version "8.0")',
       '\t(layer "F.Cu")',f'\t(descr "{descr}")','\t(attr smd)',
       '\t(property "Reference" "**" (at 0 -1.6 0) (layer "F.SilkS") (uuid "r")',
       '\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))',
       '\t(property "Value" "" (at 0 1.6 0) (layer "F.Fab") (uuid "v")',
       '\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))']
    for i,(num,x,y,w,h) in enumerate(pads_):
        s.append(f'\t(pad "{num}" smd rect (at {x} {y}) (size {w} {h}) '
                 f'(layers "F.Cu" "F.Paste" "F.Mask") (uuid "p{i}"))')
    s.append(')')
    open(os.path.join(LIB,name+".kicad_mod"),"w").write("\n".join(s))

simple("SolderPad_1.2x2.0mm","Wire solder pad pair, 2.0mm pitch",
       [("1",0,-1.1,1.2,1.4),("2",0,1.1,1.2,1.4)])
simple("TestPad_1.0mm","1.0mm round-ish pogo test pad",[("1",0,0,1.0,1.0)])
print("footprints written:", sorted(os.listdir(LIB)))
print("ISP1807 pads:", len(pads), "(expect 78)")
nums=sorted(p[0] for p in pads); print("missing:", [i for i in range(1,79) if i not in nums])
