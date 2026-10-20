# AGENTS.md
## Overview
Telethon fork rescrambled to match official Telegram Android: v13.0.3 build
7183, TL layer 231, api_id 4 / `014b35b6184100b085b0d0572f9b5103`,
`lang_pack=android`, `system_lang_code=en-us`, SDK 36. Identity single
source: `telethon/official.py`. Consumers: `/root/AUTO_REGIST` (sys.path),
`/root/STOR_OTOMATIS` (editable install), `/root/BOT_PRIBADI` (loader as
module `telegram_android`). Full contract: `INTEGRATION.md`.
## Commands
```bash
# Regenerate TL bindings + errors (NEEDS setuptools -> system python ONLY;
# overwrites telethon/tl/ in place — commit/back up first)
cd /root/Telegram_Android && /usr/bin/python3 setup.py gen tl errors

# Test suite (pytest + pytest-asyncio live in AUTO_REGIST's venv)
/root/AUTO_REGIST/venv/bin/python -m pytest tests/telethon -q  # 35 passed

# Identity assertions (INTEGRATION.md §5A)
/root/AUTO_REGIST/venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "/root/Telegram_Android")
from telethon import official
from telethon.tl.alltlobjects import LAYER
assert LAYER == 231 == official.LAYER
print("OK: layer", LAYER, official.APP_VERSION)
PY
```
# then verify consumers + restart services: INTEGRATION.md §5 B–E
## Conventions
- Generator input `telethon_generator/data/api.tl` (header `// LAYER 231`);
  header and `official.LAYER` move together.
- Android transport is `ConnectionTcpObfuscated` (obfuscated2, abridged) —
  never plain `ConnectionTcpAbridged`/`Full` on the Android path.
- Schema features (generic wrappers `{X:Type}`, bitfields) are *detected*,
  not enumerated — new layers need no generator change.
## Boundaries
- **NEVER** edit generated code by hand: `telethon/tl/functions/*`,
  `telethon/tl/types/*`, `telethon/tl/alltlobjects.py` — regenerate instead.
- **NEVER** edit `telethon_generator/data/api.tl` directly; it is generated.
- **NEVER** run `setup.py gen` with a project venv python (no setuptools
  there); only `/usr/bin/python3` qualifies.
- Two Telethon copies exist (fork @ 231, wheel @ 227) — never mix namespaces.
## Dependencies
Generator: setuptools on `/usr/bin/python3` only. Tests: pytest, pytest-asyncio,
pyaes, rsa (see `dev-requirements.txt`).
## Config
No runtime config; identity in `telethon/official.py` must satisfy
`INTEGRATION.md §1`; layer header in `telethon_generator/data/api.tl`.
## Error Handling
Generator failures are tracebacks from `telethon_generator.parsers`, most often `AssertionError: Invalid inferred ID for <method>` — a generic wrapper
missing its `{X:Type}` block. Files are written completely or not at all, but
`tl/` is overwritten in place: back up first.
## Troubleshooting
- `ModuleNotFoundError: No module named 'setuptools'` — wrong interpreter;
  use `/usr/bin/python3`.
- `Invalid inferred ID` — fix the source scheme, not the parser.
- Layer drift — commit `api.tl` header + `official.py` together, re-run
  `INTEGRATION.md §5 B–D`.
- Consumer `TypeError: You can only invoke requests...` — wheel namespace
  leaked; consumers use `tl_for(client)`.
