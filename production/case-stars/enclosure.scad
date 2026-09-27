// Dimensions in millimetres. Export bottom and top separately for printing.
part = "layout"; // [layout,bottom,top,assembled,exploded,interference]
inner_length = 59;
inner_width = 25;
inner_height = 15;
wall = 2;
floor_thickness = 2;
roof_thickness = 2;
clearance = 0.25; // Per side, outside the usable cavity.
skirt_thickness = 1.2;
skirt_depth = 10;
tab_width = 8;
slot_width = 0.8;
hook_projection = 0.70;
pocket_depth = 0.70;
floor_opening_length = 15;
end_opening_height = 5;
end_opening_above_floor = 3;
// Edge softening. Bed-side fillets print as short shallow overhangs on the first layers.
edge_fillet = 1.0;     // Roof top edges and tray bottom edges.
rim_chamfer = 0.4;     // Tray rim outer edge; doubles as a lead-in for the lid.
skirt_chamfer = 0.5;   // Skirt tip outer edge.
skirt_lead_in = 0.3;   // Skirt tip inner edge.
opening_chamfer = 0.5; // Both faces of the port and floor cut-outs.
notch_chamfer = 0.4;   // Outer face of the lid skirt notch.
$fn = 48;
eps = 0.01;
L = inner_length + 2*wall;
W = inner_width + 2*wall;
seat = floor_thickness + inner_height;
H = seat + roof_thickness;
OL = L + 2*(clearance + skirt_thickness);
OW = W + 2*(clearance + skirt_thickness);
tip_z = seat - skirt_depth;
hook_z = tip_z + 1.2;
tab_positions = [-L/4, L/4];
lid_corner = 2.45;
port_z = floor_thickness + end_opening_above_floor;
port_zc = port_z + end_opening_height/2;
floor_opening_xc = -inner_length/2 + floor_opening_length/2;

module rounded_prism(l,w,h,r) {
    linear_extrude(height=h)
        offset(r=r) square([l-2*r,w-2*r],center=true);
}

// Tori (spheres when rv==rf) at the four corners; hull with a prism to round its horizontal edges.
module fillet_ring(l,w,z,rv,rf) {
    for (sx=[-1,1], sy=[-1,1])
        translate([sx*(l/2-rv), sy*(w/2-rv), z])
            if (rv-rf > eps) rotate_extrude() translate([rv-rf,0]) circle(rf);
            else sphere(rf);
}

// 45 degree flare of an l x w opening at a face. Local +z points out of the material.
module flare(l,w,c) {
    hull() {
        translate([0,0,-c]) linear_extrude(eps) square([l,w],center=true);
        linear_extrude(2*eps) square([l+2*c,w+2*c],center=true);
    }
}

module tray_body() {
    hull() {
        fillet_ring(L,W,edge_fillet,1,edge_fillet);
        translate([0,0,edge_fillet])
            rounded_prism(L,W,seat-edge_fillet-rim_chamfer,1);
        translate([0,0,seat-eps])
            rounded_prism(L-2*rim_chamfer,W-2*rim_chamfer,eps,1-rim_chamfer);
    }
}

// Left = negative X, right = positive X along the 59 mm length.
module right_opening() {
    translate([inner_length/2-eps,-inner_width/2,port_z])
        cube([wall+clearance+skirt_thickness+2*eps,
              inner_width,end_opening_height]);
}

module port_flares() {
    translate([L/2,0,port_zc]) rotate([0,90,0])
        flare(end_opening_height,inner_width,opening_chamfer);
    translate([inner_length/2,0,port_zc]) rotate([0,-90,0])
        flare(end_opening_height,inner_width,opening_chamfer);
}

module floor_opening() {
    translate([-inner_length/2,-inner_width/2,-eps])
        cube([floor_opening_length,inner_width,floor_thickness+2*eps]);
    translate([floor_opening_xc,0,0]) rotate([180,0,0])
        flare(floor_opening_length,inner_width,opening_chamfer);
    translate([floor_opening_xc,0,floor_thickness])
        flare(floor_opening_length,inner_width,opening_chamfer);
}

module bottom() {
    difference() {
        tray_body();
        // Square internal corners preserve the complete rectangular cavity.
        translate([-inner_length/2,-inner_width/2,floor_thickness])
            cube([inner_length,inner_width,inner_height+eps]);
        for (x=tab_positions, side=[-1,1])
            translate([x,side*(W/2-pocket_depth/2+eps/2),hook_z])
                cube([tab_width+0.6,pocket_depth+eps,2.0],center=true);
        floor_opening();
        right_opening();
        port_flares();
    }
}

module hook(x, side) {
    // Both slopes are printable ramps; the upper slope permits reopening.
    translate([x,0,0]) scale([1,side,1]) hull() {
        translate([-tab_width/2,W/2+clearance,hook_z-0.8])
            cube([tab_width,0.10,0.02]);
        translate([-tab_width/2,W/2+clearance-hook_projection,hook_z])
            cube([tab_width,hook_projection+0.10,0.02]);
        translate([-tab_width/2,W/2+clearance,hook_z+0.8])
            cube([tab_width,0.10,0.02]);
    }
}

module lid_roof() {
    hull() {
        translate([0,0,seat])
            rounded_prism(OL,OW,roof_thickness-edge_fillet,lid_corner);
        fillet_ring(OL,OW,H-edge_fillet,lid_corner,edge_fillet);
    }
}

module skirt_outer() {
    hull() {
        translate([0,0,tip_z])
            rounded_prism(OL-2*skirt_chamfer,OW-2*skirt_chamfer,eps,lid_corner-skirt_chamfer);
        translate([0,0,tip_z+skirt_chamfer])
            rounded_prism(OL,OW,skirt_depth-skirt_chamfer+eps,lid_corner);
    }
}

module skirt_inner_cut() {
    il = L + 2*clearance;
    iw = W + 2*clearance;
    ir = 1 + clearance;
    translate([0,0,tip_z-eps]) rounded_prism(il,iw,skirt_depth+3*eps,ir);
    hull() {
        translate([0,0,tip_z-eps])
            rounded_prism(il+2*skirt_lead_in,iw+2*skirt_lead_in,eps,ir+skirt_lead_in);
        translate([0,0,tip_z+skirt_lead_in]) rounded_prism(il,iw,eps,ir);
    }
}

module top_assembled() {
    union() {
        lid_roof();
        difference() {
            skirt_outer();
            skirt_inner_cut();
            // Open-ended slots free four cantilevers, leaving a 1 mm root band.
            for (x=tab_positions, side=[-1,1], edge=[-1,1])
                translate([x+edge*(tab_width+slot_width)/2,
                           side*(W/2+clearance+skirt_thickness/2),
                           tip_z+(skirt_depth-1)/2-eps])
                    cube([slot_width,skirt_thickness+2,skirt_depth-1+2*eps],center=true);
            // Clear the overlapping skirt so it cannot cover the end port.
            right_opening();
            translate([OL/2,0,port_zc]) rotate([0,90,0])
                flare(end_opening_height,inner_width,notch_chamfer);
        }
        for (x=tab_positions,side=[-1,1]) hook(x,side);
    }
}


// Star cut-outs through the lid roof, kept inside the cavity footprint.
star_points = 5;
star_inner_ratio = 0.42;
stars = []; // [x, y, outer radius] -- stars removed; add entries to bring them back
module star2d(r) {
    polygon([for (i=[0:2*star_points-1])
        let(a = 90 + i*180/star_points, rr = (i%2==0) ? r : r*star_inner_ratio)
        [rr*cos(a), rr*sin(a)]]);
}
module star_cuts() {
    for (s = stars) translate([s[0], s[1], seat-1]) linear_extrude(roof_thickness+2) star2d(s[2]);
}

// Slide-in rails on the roof for a wooden slab. Enters at -X, stops at +X.
slab_len = 58; slab_wid = 27; slab_thk = 5;
slab_clear_w = 0.15;   // per side
slab_clear_h = 0.3;
rail_lip = 1.5;        // how far the lip reaches over the slab
lip_thk = 1.0;
stop_wall = 1.6;
detent = 0.3;
module slab_rails() {
    hx = slab_wid/2 + slab_clear_w;
    z0 = H - edge_fillet;   // fuses through the roof edge fillet
    zc = H + slab_thk + slab_clear_h;
    zt = zc + lip_thk;
    intersection() {
        translate([0,0,z0]) rounded_prism(OL,OW,zt-z0,lid_corner);
        union() {
            for (s=[-1,1]) {
                translate([-OL/2, s>0 ? hx : -OW/2, z0]) cube([OL, OW/2-hx, zt-z0]);
                translate([-OL/2, s>0 ? hx-rail_lip : -hx, zc]) cube([OL, rail_lip, lip_thk]);
                translate([-OL/2+1.5, s>0 ? hx-rail_lip : -hx, zc-detent]) cube([1, rail_lip, detent+eps]);
            }
            translate([OL/2-stop_wall, -OW/2, z0]) cube([stop_wall, OW, zt-z0]);
        }
    }
}
module top_with_stars() { difference() { union() { top_assembled(); slab_rails(); } star_cuts(); } }
rails_top = H + slab_thk + slab_clear_h + lip_thk;
// Separate glue-on frame. Printed lip side down: no bridges or overhangs.
module rails_print() { translate([0,0,rails_top]) rotate([180,0,0]) slab_rails(); }

module top_print() {
    translate([0,0,rails_top]) rotate([180,0,0]) top_with_stars();
}

if (part=="bottom") bottom();
else if (part=="rails") rails_print();
else if (part=="top") top_print();
else if (part=="assembled") {
    color("SlateGray") bottom();
    color("Orange") top_with_stars();
}
else if (part=="exploded") {
    color("SlateGray") bottom();
    color("Orange") translate([0,0,16]) top_with_stars();
}
else if (part=="interference") intersection() { bottom(); top_assembled(); }
else {
    translate([0,-(OW+6)/2,0]) bottom();
    translate([0,(OW+6)/2,0]) top_print();
}
