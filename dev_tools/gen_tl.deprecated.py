"""DEPRECATED — superseded by /root/scripts/tg-layer-upgrade/.

Kept for reference. This tool hardcoded layer 229 and has been replaced by the
layer-agnostic pipeline documented in /root/scripts/tg-layer-upgrade/README.md:

    python3 json_to_api_tl.py <tlscheme.json> <out.tl> --layer <N>
    cd /root/Telegram_Android && /usr/bin/python3 setup.py gen tl errors

Do NOT use this file to regenerate the schema; its hardcoded LAYER will ship a
stale layer. Use the pipeline above instead.
"""
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
