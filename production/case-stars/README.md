# Slab case (stars removed)

Snap-fit enclosure for the prototype rig, based on the 59 x 25 x 15 mm
snap-fit case (`~/Documents/snap-fit-case-59x25x15-openings`), with slide
rails on top for a 58 x 27 x 5 mm wooden slab. The star cut-outs were
removed; set `stars` in enclosure.scad to bring them back.

- `enclosure.scad`: the source. Stars, rails and slab size are parameters
  near the top. Export with `openscad -D 'part="top"' -o top.stl` (and
  `bottom`, `assembled`, `exploded`, `layout`).
- `bottom.stl`, `top.stl`, `rails.stl`: print orientation, all at Z = 0. The
  rails are a separate frame glued onto the lid roof after printing.
- `stars.3mf`: PrusaSlicer project, both parts side by side on the
  Anycubic Mega S bed with the transparent-PLA settings.
- `stars.gcode`: ready to print on the Mega S. 3 h 44 min, 20.4 g PLA.
- `case_both.blend`: assembled scene with the slab in the rails.
- `megas_pla_prusaslicer.ini`: the base Mega S PLA profile.

## Print settings (transparent PLA)

0.12 mm layers, 5 perimeters, 100% rectilinear infill, 12 top and bottom
layers with monotonic fill, 215 C, 20 mm/s outer walls, aligned seam, no
supports. The solid fill keeps the part evenly translucent; the fine layers
keep edges crisp.

## Notes

- Cavity 59 x 25 x 15 mm. Lid snaps over the tray with four hooked tabs.
- The slab slides in from the -X end and stops against the +X wall; a
  0.3 mm detent under each lip holds it. 0.15 mm side and 0.3 mm top
  clearance.
- The rails used to be part of the lid, which printed the star roof as a
  27 mm bridge in mid-air and failed. Now the lid prints roof-down flat on
  the bed and the rails print lip-side down; neither has any bridging.
  Glue the rails on with the stop wall at the +X end (away from the entry),
  outer edges flush with the lid.
