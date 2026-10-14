"""The canonical Android device pool must contain real modern devices."""
import csv
import importlib.util
from pathlib import Path

import pytest

POOL_PATH = Path("/root/AUTO_REGIST/devices.py")
CSV_PATH = Path("/root/device-sources/play_supported_devices.csv")


def _load_pool():
    spec = importlib.util.spec_from_file_location("auto_devices", POOL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.AndroidDevice.__gen__()
    return mod.AndroidDevice


class TestDevicePool:
    def test_pool_has_200_plus_unique_pairs(self):
        cls = _load_pool()
        assert len(cls.device_pairs) >= 200
        assert len({(p[0], p[1]) for p in cls.device_pairs}) == len(cls.device_pairs)

    def test_perf_classes_are_valid(self):
        cls = _load_pool()
        assert {p[2] for p in cls.device_pairs} <= {0, 1, 2}

    def test_every_model_exists_in_google_play_dump(self):
        cls = _load_pool()
        csv_models = set()
        with CSV_PATH.open(encoding="utf-16", newline="") as f:
            for row in csv.DictReader(f):
                brand = (row.get("Retail Branding") or "").strip()
                model = (row.get("Model") or "").strip()
                if brand and model:
                    csv_models.add((brand, model))

        # Pool casing intentionally normalizes Build.MANUFACTURER, so compare
        # by case-insensitive brand/model while retaining exact model strings.
        normalized = {(b.casefold(), m) for b, m in csv_models}
        missing = [
            pair for pair in cls.device_pairs
            if (pair[0].casefold(), pair[1]) not in normalized
        ]
        assert missing == []

    def test_random_device_is_deterministic(self):
        cls = _load_pool()
        first = cls.RandomDevice("6281234567890")
        for _ in range(10):
            again = cls.RandomDevice("6281234567890")
            assert (again.model, again.version, again.perf_class) == (
                first.model,
                first.version,
                first.perf_class,
            )

    @pytest.mark.parametrize("key", ["6281234567890", "6285135511224", "6281119999999"])
    def test_device_has_expected_shape(self, key):
        device = _load_pool().RandomDevice(key)
        assert device.model
        assert device.version in {"SDK 34", "SDK 35", "SDK 36"}
        assert device.perf_class in {0, 1, 2}
