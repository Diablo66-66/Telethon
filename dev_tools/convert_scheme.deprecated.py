"""DEPRECATED — superseded by /root/scripts/tg-layer-upgrade/.

Kept for reference. This tool hardcoded layer 229 and has been replaced by the
layer-agnostic pipeline documented in /root/scripts/tg-layer-upgrade/README.md:

    python3 json_to_api_tl.py <tlscheme.json> <out.tl> --layer <N>
    cd /root/Telegram_Android && /usr/bin/python3 setup.py gen tl errors

Do NOT use this file to regenerate the schema; its hardcoded LAYER will ship a
stale layer. Use the pipeline above instead.
"""
"""Convert official Telegram-Android tlscheme dump (layer 229) into
Telethon api.tl format, keeping generic wrappers the dump omits."""
import json
import re

DUMP = '/tmp/Telegram-Android/TMessagesProj_AppTests/tlscheme/229.json'
OLD = '/root/Telegram_Android/telethon_generator/data/api.tl'
OUT = '/root/Telegram_Android/telethon_generator/data/api.tl'

GENERIC_RE = re.compile(r'\{X:Type\}|!X|= X;')

HEADER = [
    'boolFalse#bc799737 = Bool;',
    'boolTrue#997275b5 = Bool;',
    'true#3fedd339 = True;',
    'vector#1cb5c415 {t:Type} # [ t ] = Vector t;',
    'error#c4b9f9bb code:int text:string = Error;',
    'null#56730bcc = Null;',
]

def fmt_param(p):
    name, t = p['name'], p['type']
    if t == '#':
        return f'{name}:#'
    return f'{name}:{t}'

def fmt_obj(e, is_method):
    name = e['method'] if is_method else e['predicate']
    oid = '%08x' % (int(e['id']) & 0xffffffff)
    params = ''.join(' ' + fmt_param(p) for p in e.get('params', []))
    generic = ' {X:Type}' if e['type'] == 'X' else ''
    return f'{name}#{oid}{generic}{params} = {e["type"]};'

dump = json.load(open(DUMP))
types = [fmt_obj(c, False) for c in dump['constructors']]
funcs = [fmt_obj(m, True) for m in dump['methods']]
dump_names = {c['predicate'] for c in dump['constructors']} | \
             {m['method'] for m in dump['methods']}

kept = []
seen = set()
for ln in open(OLD):
    ln = ln.split('//')[0].strip()
    m = re.match(r'(\S+)#', ln)
    if not m or m.group(1) in seen:
        continue
    seen.add(m.group(1))
    if m.group(1) not in dump_names and GENERIC_RE.search(ln):
        kept.append(ln)

kept_t = [ln for ln in kept if not re.match(r'^(invoke|initConnection|req)', ln)]
kept_f = [ln for ln in kept if ln not in kept_t]

with open(OUT, 'w') as f:
    f.write('\n'.join(HEADER + kept_t) + '\n')
    f.write('---types---\n' + '\n'.join(types) + '\n')
    f.write('---functions---\n' + '\n'.join(funcs + kept_f) + '\n')

print('types', len(types), 'funcs', len(funcs) + len(kept_f),
      'kept-generic', len(kept))
for probe in ('invokeWithLayer', 'initConnection', 'invokeAfterMsg',
              'jsonObject', 'messages.sendMessage'):
    hit = [ln for ln in HEADER + types + funcs + kept
           if ln.startswith(probe + '#')]
    print(probe, '->', hit[:1])
