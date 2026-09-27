"""Build stars.3mf: tray and lid side by side on the Mega S bed, with the print settings embedded."""
import os, zipfile
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read_stl(p):
    verts, idx, tris, cur = [], {}, [], []
    for ln in open(p, errors="ignore"):
        ln = ln.strip()
        if ln.startswith("vertex"):
            v = tuple(round(float(c), 5) for c in ln.split()[1:4])
            if v not in idx: idx[v] = len(verts); verts.append(v)
            cur.append(idx[v])
            if len(cur) == 3: tris.append(cur); cur = []
    return verts, tris
objs, items = [], []
for i, (f, name, y) in enumerate([("bottom.stl", "tray (bottom)", 105 - 18.5), ("top.stl", "lid with slab rails", 105 + 18.5)], 1):
    v, t = read_stl(os.path.join(D, f)); zmin = min(p[2] for p in v)
    objs.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>' + "".join(f'<vertex x="{a}" y="{b}" z="{c}"/>' for a, b, c in v)
                + '</vertices><triangles>' + "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t) + '</triangles></mesh></object>')
    items.append(f'<item objectid="{i}" transform="1 0 0 0 1 0 0 0 1 105 {y} {-zmin}"/>')
g = open(os.path.join(D, "gcode", "case_both_clear.gcode"), errors="ignore").read()
cfg = g[g.index("; prusaslicer_config = begin"):g.index("; prusaslicer_config = end")]
cfg = "\n".join(l for l in cfg.splitlines() if "prusaslicer_config" not in l) + "\n"
with zipfile.ZipFile(os.path.join(D, "stars.3mf"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    z.writestr("3D/3dmodel.model", '<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources>' + "".join(objs) + '</resources><build>' + "".join(items) + '</build></model>')
    z.writestr("Metadata/Slic3r_PE.config", cfg)
print("wrote stars.3mf")
