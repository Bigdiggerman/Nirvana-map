"""Add Stand's stand boundaries (Geomaster Patches export) to the map as one
per-block stand layer, `stand_nirvana`, using the template's existing
`stand_*` mechanism (coloured by planting year, one toggle).

Inputs (Dataroom/1. Forestry):
  GISData/Patches.shp (+ .dbf/.shx/.prj)    stand polygons, NZTM2000 (EPSG:2193)
  StandRecords/StandsListing.xlsx -> .tsv    stand register (stocked area, YOE)
  StandRecords/Export Assessment Data.csv    ESQC / blanking survey stocking

Usage:
  python scripts/add_stands.py --shp Patches.shp --listing StandsListing.tsv \
      --assess "Export Assessment Data.csv" [--layers assets/layers.js] [--geojson out.geojson]
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime

import shapely
import shapefile
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

SOURCE = 'Stand Geomaster stand boundaries (exported 22 Oct 2026); stand register 22 Oct 2026'

# Forests in the register whose land is not in the sale titles: block label and
# popup status. A status containing "outside" gets the red dashed outline.
OFF_TITLE = {
    'SLDR': ('Soldiers Road (crop only)',
             "Crop in the sale under NFL's forestry right; the land (Land & Bee's Limited) is not included"),
    'KWTA': (None,
             'Outside the sale titles – on Wood Country Limited land (WN22B/23, WN53B/171); '
             'whether this crop is in the sale is to be confirmed'),
}
TO_WGS84 = Transformer.from_crs(2193, 4326, always_xy=True).transform


def read_listing(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return {r['StandName']: r for r in csv.DictReader(f, delimiter='\t')}


def read_assessments(path):
    """Latest establishment (ESQC) and blanking (BLNK) survey per stand."""
    out = defaultdict(dict)
    with open(path, newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            key = f"{r['Forest']}-{int(r['Compartment'])}-{r['Stand'].zfill(2)}"
            when = datetime.strptime(r['AssessDate'], '%d/%m/%Y')
            prev = out[key].get(r['Class'])
            if prev is None or when >= prev['when']:
                out[key][r['Class']] = {'when': when, 'sph': float(r['SPH_All']),
                                        'ple': float(r['SPH_All_PLE']) if r['SPH_All_PLE'] else None}
    return out


def survey(a):
    if not a:
        return None
    s = f"{a['sph']:,.0f} sph ({a['when'].strftime('%b %Y')})"
    return s + (f", ±{a['ple']:.1f}% PLE" if a['ple'] is not None else '')


def block_index(layers):
    """Sale blocks from the title boundary, for in-sale tagging."""
    polys = defaultdict(list)
    for f in layers['title_boundary']['features']:
        polys[f['properties'].get('block')].append(shape(f['geometry']))
    return {b: unary_union(g) for b, g in polys.items() if b}


def build(args, layers):
    listing = read_listing(args.listing)
    assess = read_assessments(args.assess)
    blocks = block_index(layers) if layers else {}

    parts = defaultdict(list)
    attrs = {}
    rdr = shapefile.Reader(args.shp)
    for sr in rdr.iterShapeRecords():
        p = sr.record.as_dict()
        name = (p.get('StandName') or '').strip()
        if not name or sr.shape.shapeType == shapefile.NULL:
            continue
        parts[name].append(shape(sr.shape.__geo_interface__))
        attrs.setdefault(name, p)

    feats = []
    for name, geoms in sorted(parts.items()):
        nztm = unary_union(geoms).buffer(0)
        g = shapely.transform(nztm.simplify(args.simplify, preserve_topology=True),
                              lambda xy: list(zip(*TO_WGS84(*xy.T))))
        p, reg = attrs[name], listing.get(name, {})
        a = assess.get(name, {})
        year = int(reg.get('YOE') or p.get('EstabYear') or 0) or None
        area = float(reg.get('StockedArea') or p.get('StandNSA') or 0)
        hits = [b for b, poly in blocks.items() if poly.intersection(g).area > 0.5 * g.area]
        props = {
            'layer_label': 'Stands (Stand, Oct 2026)',
            'label': f"{name} – {reg.get('ForestName') or p.get('ForestName') or ''}".strip(' –'),
            'stand': name,
            'forest': reg.get('ForestName') or p.get('ForestName'),
            'year': year,
            'species': reg.get('SpeciesName') or p.get('Species'),
            'area_ha': round(area, 2),
            'map_ha': round(nztm.area / 1e4, 1),
            'esqc': survey(a.get('ESQC')),
            'blanking': survey(a.get('BLNK')),
            'block': hits[0] if hits else None,
            'source': SOURCE,
        }
        if blocks and not hits:
            props['block'], props['status'] = OFF_TITLE.get(
                name[:4], (None, 'Outside the sale titles'))
        feats.append({'type': 'Feature', 'properties': props,
                      'geometry': json.loads(json.dumps(mapping(g)),
                                             parse_float=lambda x: round(float(x), 6))})
    missing = sorted(set(listing) - set(parts))
    return {'type': 'FeatureCollection', 'features': feats}, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shp', required=True)
    ap.add_argument('--listing', required=True)
    ap.add_argument('--assess', required=True)
    ap.add_argument('--layers', default='assets/layers.js')
    ap.add_argument('--geojson')
    ap.add_argument('--simplify', type=float, default=0.5, help='outline tolerance in metres')
    args = ap.parse_args()

    raw = open(args.layers, encoding='utf-8').read()
    prefix = raw[:raw.index('{')]
    layers = json.loads(raw[len(prefix):].rstrip().rstrip(';'))

    fc, missing = build(args, layers)
    layers['stand_nirvana'] = fc
    with open(args.layers, 'w', encoding='utf-8') as f:
        f.write(prefix + json.dumps(layers, separators=(',', ':'), ensure_ascii=False) + ';\n')
    if args.geojson:
        with open(args.geojson, 'w', encoding='utf-8') as f:
            json.dump(fc, f, ensure_ascii=False)

    out = [p['properties'] for p in fc['features']]
    print(f"{len(out)} stands, {sum(p['area_ha'] for p in out):,.1f} ha "
          f"({sum(1 for p in out if 'outside' in (p.get('status') or '').lower())} outside the sale)")
    if missing:
        print('In the register but not mapped:', ', '.join(missing))


if __name__ == '__main__':
    main()
