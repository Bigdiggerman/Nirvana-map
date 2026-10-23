"""v14 - Stand stand register on the CROP tab and stocking rows in the stand popup.

Run once from the map folder, after copying stand_nirvana.geojson into data/:

    python scripts/apply_v14_stands.py
    python scripts/release.py --note "Stand stand boundaries and register (22 Oct 2026)"

Safe to re-run: each change is skipped if it is already there.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else (HERE if (HERE / 'property.json').exists() else HERE.parent)

REGISTER = 'Stand register (22 Oct 2026)'

# In-sale stands from Stand's stand register / Geomaster stand map, 22 Oct 2026,
# summed by block and establishment year (register stocked areas).
AGE_CLASSES = [
    {'block': 'Back Farm', 'year': 2022, 'ha': 315.97, 'species': 'P. radiata'},
    {'block': 'Back Farm', 'year': 2023, 'ha': 419.03, 'species': 'P. radiata'},
    {'block': 'Back Farm', 'year': 2026, 'ha': 38.75, 'species': 'P. radiata (2026 stand)'},
    {'block': 'Longreach', 'year': 2024, 'ha': 764.99, 'species': 'P. radiata'},
    {'block': 'Longreach', 'year': 2026, 'ha': 4.38, 'species': 'P. radiata (2026 stand)'},
    {'block': 'Whangamomona', 'year': 2024, 'ha': 284.51, 'species': 'P. radiata'},
    {'block': 'Whangamomona', 'year': 2026, 'ha': 32.0, 'species': 'P. radiata (2026 stand)'},
    {'block': 'Front Farm', 'year': 2023, 'ha': 219.42, 'species': 'P. radiata'},
    {'block': 'Front Farm', 'year': 2026, 'ha': 11.46, 'species': 'P. radiata (2026 stand)'},
    {'block': 'Eastern Block', 'year': 2023, 'ha': 20.4, 'species': 'P. radiata'},
    {'block': 'Eastern Block', 'year': 2024, 'ha': 100.19, 'species': 'P. radiata'},
    {'block': 'Eastern Block', 'year': 2026, 'ha': 15.63, 'species': 'P. radiata (2026 stand)'},
    {'block': 'Puau Road', 'year': 2024, 'ha': 48.44, 'species': 'P. radiata'},
    {'block': 'Staghaven', 'year': 2024, 'ha': 82.7, 'species': 'P. radiata (plus older exotic)'},
    {'block': 'Soldiers Road (crop only)', 'year': 2023, 'ha': 88.4, 'species': 'P. radiata'},
    {'block': 'Soldiers Road (crop only)', 'year': 2026, 'ha': 21.12, 'species': 'P. radiata (2026 stand)'},
]
for r in AGE_CLASSES:
    r['age'] = 2026 - r['year']

AGE_NOTE = ("Stands, establishment years and areas from Stand's stand register and Geomaster stand map "
            "(22 Oct 2026): 37 stands, 2,467.4 ha – 2,357.9 ha on the sale titles plus the Soldiers Road crop "
            "(109.5 ha), which is sold under NFL's forestry right without the land (Land & Bee's Limited). "
            "2026 rows are new stands created for this season's replanting. Staghaven also carries ~49 ha of "
            "older exotic forest (including 2011 ETS stands) that is not in the register. The register also "
            "lists Kowhata (KWTA-1-01, 74.5 ha, 2024) on Wood Country Limited land (WN22B/23, WN53B/171); it "
            "is not in the agency agreements and is excluded here pending confirmation. The initial planted "
            "area above is Stand's April 2026 survey figure. Stand boundaries are on the map under Forest & carbon.")

SUMMARY_ROW = {'k': REGISTER,
               'v': "37 stands, 2,467 ha (2,358 ha on the sale titles + 109.5 ha Soldiers Road crop); established 2022–2026"}

# Stand labels in data/stand_nirvana.geojson for the register forests off the sale titles.
STAND_STATUS = {
    'SLDR': ('Soldiers Road (crop only)',
             "Crop in the sale under NFL's forestry right; the land (Land & Bee's Limited) is not included"),
    'KWTA': (None,
             'Outside the sale titles – on Wood Country Limited land (WN22B/23, WN53B/171); '
             'whether this crop is in the sale is to be confirmed'),
}
SOURCE_ADD = 'Stand stand register and stand map (22 Oct 2026)'

POPUP_OLD = "        p.status ? kv('Status', p.status) : '',\n"
POPUP_NEW = ("        p.esqc ? kv('Establishment QC', p.esqc) : '',\n"
             "        p.blanking ? kv('Blanking survey', p.blanking) : '',\n" + POPUP_OLD)


def update_crop(crop):
    crop['age_classes'] = AGE_CLASSES
    crop['age_note'] = AGE_NOTE
    summary = crop.setdefault('summary', [])
    rows = [i for i, r in enumerate(summary) if r.get('k') == REGISTER]
    if rows:
        summary[rows[0]] = SUMMARY_ROW
    else:
        summary.insert(1, SUMMARY_ROW)
    if SOURCE_ADD not in crop.get('source', ''):
        crop['source'] = '; '.join(filter(None, [crop.get('source'), SOURCE_ADD]))


def main():
    prop_path = ROOT / 'property.json'
    prop = json.loads(prop_path.read_text(encoding='utf-8'))
    update_crop(prop['crop'])
    prop_path.write_text(json.dumps(prop, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('property.json: CROP age classes, note, summary and source updated')

    tpl_path = ROOT / 'scripts' / 'template.html'
    with open(tpl_path, encoding='utf-8', newline='') as f:
        tpl = f.read()
    eol = '\r\n' if '\r\n' in tpl else '\n'
    old, new = POPUP_OLD.replace('\n', eol), POPUP_NEW.replace('\n', eol)
    if "kv('Establishment QC'" in tpl:
        print('template.html: stocking rows already present')
    elif tpl.count(old) != 1:
        sys.exit('template.html: stand popup not found - add the Establishment QC / Blanking survey rows by hand')
    else:
        with open(tpl_path, 'w', encoding='utf-8', newline='') as f:
            f.write(tpl.replace(old, new))
        print('template.html: stocking rows added to the stand popup')

    stands_path = ROOT / 'data' / 'stand_nirvana.geojson'
    if not stands_path.exists():
        sys.exit('data/stand_nirvana.geojson is missing - copy it in, then run this again')
    stands = json.loads(stands_path.read_text(encoding='utf-8'))
    for f in stands['features']:
        p = f['properties']
        if p.get('stand', '')[:4] in STAND_STATUS:
            p['block'], p['status'] = STAND_STATUS[p['stand'][:4]]
    stands_path.write_text(json.dumps(stands, ensure_ascii=False), encoding='utf-8')
    print('stand_nirvana.geojson: Soldiers Road (crop only) and Kowhata labels set')


if __name__ == '__main__':
    main()
