"""Fork identity constants vs the official Telegram Android client.

Source of truth: /root/telegram-android-official at commit f32ffee
(version 13.0.2 build 7175). This suite re-reads the official Java/Kotlin
sources at test time, so an upstream bump fails loudly instead of silently
drifting.
"""
import re
from pathlib import Path

import pytest

FORK = Path("/root/Telegram_Android")
OFFICIAL = Path("/root/telegram-android-official")

# Import through the package so relative imports inside official.py work.
import sys

sys.path.insert(0, str(FORK))
from telethon import official as ta_o  # fork telethon, layer 231


def _read(rel):
    return (OFFICIAL / rel).read_text()


def _official_constants():
    gp = _read("gradle.properties")
    bv = _read("TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java")
    tlrpc = _read("TMessagesProj/src/main/java/org/telegram/tgnet/TLRPC.java")
    return {
        "VERSION_NAME": re.search(r"APP_VERSION_NAME=(.+)", gp).group(1).strip(),
        "VERSION_CODE": int(re.search(r"APP_VERSION_CODE=(\d+)", gp).group(1)),
        "LAYER": int(re.search(r"int LAYER\s*=\s*(\d+)", tlrpc).group(1)),
        "APP_ID": int(re.search(r"APP_ID\s*=\s*(\d+)", bv).group(1)),
        "APP_HASH": re.search(r'APP_HASH\s*=\s*"([^"]+)"', bv).group(1),
    }


OFFICIAL_CONSTANTS = _official_constants()


class TestIdentityConstants:
    def test_app_version_composed_from_official(self):
        want = (
            f"{OFFICIAL_CONSTANTS['VERSION_NAME']} ({OFFICIAL_CONSTANTS['VERSION_CODE']})"
        )
        assert ta_o.VERSION_NAME == OFFICIAL_CONSTANTS["VERSION_NAME"]
        assert ta_o.VERSION_CODE == OFFICIAL_CONSTANTS["VERSION_CODE"]
        assert ta_o.APP_VERSION == want

    def test_layer_matches_official(self):
        assert ta_o.LAYER == OFFICIAL_CONSTANTS["LAYER"] == 231

    def test_api_credentials(self):
        assert ta_o.APP_ID == OFFICIAL_CONSTANTS["APP_ID"] == 4
        assert ta_o.APP_HASH == OFFICIAL_CONSTANTS["APP_HASH"]

    def test_static_identity_strings(self):
        assert ta_o.SYSTEM_VERSION == "SDK 36"
        assert ta_o.LANG_PACK == "android"
        assert ta_o.LANG_CODE == "en"
        assert ta_o.SYSTEM_LANG_CODE == "en-us"
        assert ta_o.PACKAGE_ID == "org.telegram.messenger"
        assert ta_o.INSTALLER == "com.android.vending"

    def test_perf_cat_is_performance_class_plus_one(self):
        # official ConnectionsManager.cpp: jsonNumber->value = currentPerformanceClass + 1
        # HIGH = 2 in SharedConfig.java, so the wire value must be 3.
        assert ta_o.PERFORMANCE_CLASS == 2
        assert ta_o.PERF_CAT == 3

    def test_certificate_fingerprint(self):
        # SHA-256 of the release signing certificate, extracted from the
        # official telegram.org APK (subject CN=Nikolay Kudashov, O=VK).
        assert (
            ta_o.CERT_FINGERPRINT
            == "49C1522548EBACD46CE322B6FD47F6092BB745D0F88082145CAF35E14DCC38E1"
        )


class TestInitParams:
    EXPECTED_ORDER = ["device_token", "data", "installer", "package_id", "tz_offset", "perf_cat"]

    def _json_dict(self):
        params = ta_o.init_params(device_token_value="TESTTOKEN", tz_offset=25200)
        assert params is not None
        return params.value

    def test_six_params_in_official_order(self):
        pairs = self._json_dict()
        assert isinstance(pairs, list)
        keys = [p.key for p in pairs]
        assert keys == self.EXPECTED_ORDER

    def test_value_types(self):
        from telethon.tl import types as t

        pairs = {p.key: p for p in self._json_dict()}
        assert isinstance(pairs["device_token"].value, t.JsonString)
        assert pairs["device_token"].value.value == "TESTTOKEN"
        assert isinstance(pairs["data"].value, t.JsonString)
        assert isinstance(pairs["installer"].value, t.JsonString)
        assert isinstance(pairs["package_id"].value, t.JsonString)
        assert isinstance(pairs["tz_offset"].value, t.JsonNumber)
        assert isinstance(pairs["perf_cat"].value, t.JsonNumber)

    def test_param_values(self):
        pairs = {p.key: p for p in self._json_dict()}
        assert pairs["installer"].value.value == "com.android.vending"
        assert pairs["package_id"].value.value == "org.telegram.messenger"
        assert pairs["tz_offset"].value.value == 25200
        assert pairs["perf_cat"].value.value == 3

    @pytest.mark.parametrize("wire", [1, 2, 3])
    def test_perf_cat_wire_value_written_unchanged(self, wire):
        # perf_cat is the wire value (class + 1, as DeviceInfo.perf_cat and
        # PERF_CAT already are); init_params must not convert it again.
        params = ta_o.init_params(
            device_token_value="TESTTOKEN", tz_offset=25200,
            perf_cat=wire)
        pairs = {p.key: p for p in params.value}
        assert pairs["perf_cat"].value.value == wire

    @pytest.mark.parametrize("invalid", [-1, 0, 4, "3", "2", True, False, 3.0, 2.0])
    def test_perf_cat_rejects_invalid_wire_values(self, invalid):
        with pytest.raises(ValueError, match="must be 1, 2 or 3"):
            ta_o.init_params(device_token_value="TESTTOKEN", tz_offset=25200,
                             perf_cat=invalid)

    @pytest.mark.parametrize("performance_class,wire", [(0, 1), (1, 2), (2, 3)])
    def test_performance_class_helper_serializes_class_plus_one(
            self, performance_class, wire):
        params = ta_o.init_params(
            device_token_value="TESTTOKEN", tz_offset=25200,
            performance_class=performance_class)
        pairs = {p.key: p for p in params.value}
        assert pairs["perf_cat"].value.value == wire

    @pytest.mark.parametrize("invalid", [-1, 3, "2", True, 2.0])
    def test_performance_class_rejects_invalid_classes(self, invalid):
        with pytest.raises(ValueError, match="performance_class must be 0, 1 or 2"):
            ta_o.init_params(device_token_value="TESTTOKEN", tz_offset=25200,
                             performance_class=invalid)

    def test_perf_cat_and_performance_class_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="only one of"):
            ta_o.init_params(device_token_value="TESTTOKEN", tz_offset=25200,
                             perf_cat=3, performance_class=2)

    def test_tz_offset_for_returns_int(self):
        off = ta_o.tz_offset_for("6281234567890")
        assert isinstance(off, int)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
