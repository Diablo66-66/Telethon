"""Schema surface: the fork must decode every constructor in the official
current-layer API JSON, and spot-checked method classes must exist."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

FORK = Path("/root/Telegram_Android")
OFFICIAL = Path("/root/telegram-android-official")

sys.path.insert(0, str(FORK))
import telethon  # fork telethon (layer 233)

from telethon.tl import alltlobjects, types as ftypes, functions as ffunctions


def _layer():
    """Layer of the official checkout, read from its Java source."""
    tlrpc = (OFFICIAL / "TMessagesProj/src/main/java/org/telegram/tgnet/TLRPC.java").read_text()
    return int(re.search(r"int LAYER\s*=\s*(\d+)", tlrpc).group(1))


def _scheme():
    return json.loads(
        (OFFICIAL / f"TMessagesProj_AppTests/tlscheme/{_layer()}.json").read_text()
    )


# handled by Telethon core, no registry entry by design
PRIMITIVES = {0xBC799737, 0x997275B5, 0x3FEDD339, 0x1CB5C415, 0xC4B9F9BB, 0x56730BCC}


class TestSchemaSurface:
    def test_layer(self):
        assert alltlobjects.LAYER == _layer()

    def test_registry_large_enough(self):
        assert len(alltlobjects.tlobjects) >= 2500

    def test_every_official_api_id_is_covered(self):
        scheme = _scheme()
        api_ids = {}
        for c in scheme["constructors"]:
            api_ids[int(c["id"]) & 0xFFFFFFFF] = c["predicate"]
        for m in scheme["methods"]:
            api_ids[int(m["id"]) & 0xFFFFFFFF] = m["method"]

        missing = [
            (cid, name)
            for cid, name in api_ids.items()
            if cid not in alltlobjects.tlobjects and cid not in PRIMITIVES
        ]
        assert missing == [], f"official API ids missing from fork: {missing}"

    # spot checks: (module, class name)
    METHOD_SPOTS = [
        (ffunctions.help, "GetConfigRequest"),
        (ffunctions.auth, "SendCodeRequest"),
        (ffunctions.messages, "GetMessagesRequest"),
        (ffunctions.users, "GetUsersRequest"),
        (ffunctions.updates, "GetStateRequest"),
        (ffunctions.account, "GetAuthorizationsRequest"),
        (ffunctions.auth, "ExportLoginTokenRequest"),
        (ffunctions.upload, "GetFileRequest"),
        (ffunctions.contacts, "ResolveUsernameRequest"),
        (ffunctions.channels, "GetChannelsRequest"),
    ]

    def test_method_classes_exist(self):
        for mod, cls in self.METHOD_SPOTS:
            assert hasattr(mod, cls), f"{mod.__name__}.{cls} missing"

    def test_type_classes_exist(self):
        assert hasattr(ftypes, "User")
        assert hasattr(ftypes, "Message")
        assert hasattr(ftypes, "Dialog")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
