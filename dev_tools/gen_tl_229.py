"""Regenerate telethon/tl from a .tl schema using the repo's own generator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon_generator.parsers.tlobject.parser import parse_tl
from telethon_generator.generators.tlobject import (
    generate_tlobjects, clean_tlobjects)


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'telethon_generator/data/api.tl'
MTPROTO = ROOT / 'telethon_generator/data/mtproto.tl'
LAYER = 229
OUT = ROOT / 'telethon/tl'

objects = list(parse_tl(API, layer=LAYER)) + \
          list(parse_tl(MTPROTO, layer=LAYER))
print('parsed', len(objects), 'tl objects')
depth = 2  # generator writes '.' * depth; needs 3 dots for telethon/tl/<ns>

clean_tlobjects(OUT)
generate_tlobjects(objects, LAYER, depth, OUT)
print('generated layer', LAYER)
