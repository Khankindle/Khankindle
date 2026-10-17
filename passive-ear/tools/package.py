#!/usr/bin/env python3
"""Archive deliverables and reproducible sources; exclude caches and the archive itself."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'PEBBLE-P0-package.zip'
with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path==out or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        z.write(path,path.relative_to(ROOT.parent))
print(out)
