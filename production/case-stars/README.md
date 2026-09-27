# Slab case (stars removed)

Snap-fit enclosure for the prototype rig, based on the 59 x 25 x 15 mm
snap-fit case (`~/Documents/snap-fit-case-59x25x15-openings`), with slide
rails on top for a 58 x 27 x 5 mm wooden slab. The star cut-outs were
removed; set `stars` in enclosure.scad to bring them back.

- `enclosure.scad`: the source. Stars, rails and slab size are parameters
  near the top. Export with `openscad -D 'part="top"' -o top.stl` (and
  `bottom`, `assembled`, `exploded`, `layout`).
- `bottom.stl`, `top.stl`: print orientation, both at Z = 0. The slab rails
  are part of the lid.
- `stars.3mf`: PrusaSlicer project, both parts side by side on the
  Anycubic Mega S bed with the transparent-PLA settings.
- `stars.gcode`: ready to print on the Mega S. 3 h 50 min, 21.8 g PLA.
- `case_both.blend`: assembled scene with the slab in the rails.
- `megas_pla_prusaslicer.ini`: the base Mega S PLA profile.

## Print settings (transparent PLA)

0.12 mm layers, 5 perimeters, 100% rectilinear infill, 12 top and bottom
layers with monotonic fill, 215 C, 20 mm/s outer walls, aligned seam,
supports in the slab channel only. The solid fill keeps the part evenly translucent; the fine layers
keep edges crisp.

## Notes

- Cavity 59 x 25 x 15 mm. Lid snaps over the tray with four hooked tabs.
- The slab slides in from the -X end and stops against the +X wall; a
  0.3 mm detent under each lip holds it. 0.15 mm side and 0.3 mm top
  clearance.
- The lid prints rails-down, so its roof spans the 27.3 mm slab channel.
  Printing that as an unsupported bridge failed, so the slice puts support
  material inside the channel only (build plate only, 0.2 mm gap, 2
  interface layers). Pull it out through the open entry end; the marks sit
  on the roof face the slab covers.
- 5 mm brim and 65 C bed (70 C first layer) for adhesion. Clean the plate
  with IPA or soap and water first.
