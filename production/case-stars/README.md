# Star case with slab rails

Snap-fit enclosure for the prototype rig, based on the 59 x 25 x 15 mm
snap-fit case (`~/Documents/snap-fit-case-59x25x15-openings`), with star
cut-outs through the lid and slide rails on top for a 58 x 27 x 5 mm
wooden slab.

- `enclosure.scad`: the source. Stars, rails and slab size are parameters
  near the top. Export with `openscad -D 'part="top"' -o top.stl` (and
  `bottom`, `assembled`, `exploded`, `layout`).
- `bottom.stl`, `top.stl`: print orientation, both at Z = 0.
- `stars.3mf`: PrusaSlicer project, both parts side by side on the
  Anycubic Mega S bed with the transparent-PLA settings.
- `stars.gcode`: ready to print on the Mega S. 3 h 54 min, 20.4 g PLA.
- `case_both.blend`: assembled scene with the slab in the rails.
- `megas_pla_prusaslicer.ini`: the base Mega S PLA profile.

## Print settings (transparent PLA)

0.12 mm layers, 5 perimeters, 100% rectilinear infill, 12 top and bottom
layers with monotonic fill, 215 C, 20 mm/s outer walls, aligned seam, no
supports. The solid fill keeps the part evenly translucent; the fine layers
sharpen the star edges.

## Notes

- Cavity 59 x 25 x 15 mm. Lid snaps over the tray with four hooked tabs.
- The slab slides in from the -X end and stops against the +X wall; a
  0.3 mm detent under each lip holds it. 0.15 mm side and 0.3 mm top
  clearance.
- The lid prints roof-down with the rails on the bed, so the roof bridges
  the 27.3 mm channel. Check the star edges on the first print.
- The slab covers the stars; light shows through only with it slid out.
