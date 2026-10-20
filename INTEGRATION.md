# Telegram_Android — Identity & Integration Contract

> **Kalau kamu (AI/agent) disuruh "baca .md ini dan sesuaikan semuanya seperti
> sekarang":** file ini adalah **sumber kebenaran tunggal (single source of
> truth)**. Baca seluruhnya, lalu jadikan setiap project yang mengonsumsi
> build ini **identik** dengan tabel di bawah. Jangan menebak — verifikasi
> dengan perintah di bagian **Verifikasi** sebelum menyatakan selesai.

Build ini adalah Telethon yang sudah **discramble ulang agar identitas &
perilakunya sama dengan Telegram Android resmi** (DrKLO/Telegram). Semua
project yang memakai client Android **WAJIB** memuat build ini, bukan wheel
`telethon` dari PyPI.

- **Path build:** `/root/Telegram_Android/telethon`
- **Referensi identitas:** `/root/Telegram_Android/telethon/official.py`
- **Schema layer:** **231**
- **Basis versi:** Telethon (fork), `__version__ = 1.42.0`
- **Acuan resmi:** Telegram Android **v13.0.3 build 7183** (DrKLO/Telegram, commit `0aae9598`)

---

## 1. Identitas resmi (jangan diubah kecuali mengikuti perilisan client resmi)

Sumber: `telethon/official.py` → cocok dengan **Telegram Android v13.0.3
build 7183, schema layer 231**.

| Konstanta | Nilai | Catatan |
|---|---|---|
| `APP_ID` | `4` | `BuildVars.APP_ID` resmi (dipakai semua project) |
| `APP_HASH` | `014b35b6184100b085b0d0572f9b5103` | `BuildVars.APP_HASH` resmi |
| `APP_VERSION` | `13.0.3 (7183)` | `versionName (versionCode)` |
| `SYSTEM_VERSION` | `SDK 36` | Android 16 = compileSdk/targetSdk resmi |
| `DEVICE_MODEL` | `GooglePixel 7` | Default; project pakai device acak |
| `LANG_PACK` | `android` | hardcoded di native `wrapInLayer` |
| `LANG_CODE` | `en` | |
| `SYSTEM_LANG_CODE` | `en-us` | lowercase, **BUKAN `en-US`** |
| `PACKAGE_ID` | `org.telegram.messenger` | masuk `params.package_id` |
| `INSTALLER` | `com.android.vending` | **selalu** (semua mode); Play-Store-installed; masuk `params.installer` |
| `PERF_CAT` | `1-3` per device | `getDevicePerformanceClass() + 1`; dihitung per device, bukan konstanta tetap |
| `LAYER` | `231` | `telethon/tl/alltlobjects.py` + `telethon/official.py` |

`params` JSON yang dikirim di `initConnection`:
`{device_token, data, installer, package_id, tz_offset, perf_cat}` —
lihat `official.init_params()`.

---

## 1b. Client Android vs client Desktop — JANGAN dicampur

Kontrak di file ini berlaku **hanya untuk jalur client Android**. Jalur desktop
punya identitasnya sendiri dan **tidak boleh** disamakan dengan tabel di atas.

| Aspek | Jalur **Android** | Jalur **Desktop** |
|---|---|---|
| Build library | `/root/Telegram_Android/telethon` (fork, layer **231**) | wheel `telethon` PyPI (layer **227**) |
| Factory | `make_android_client()` | `Inti.teleton.TelegramClient` + `api=API.TelegramDesktop` |
| Konstanta | `api_id=4`, `app_version="13.0.3 (7183)"` | `api_id=2040`, `app_version="7.0.4 x64"` |
| Transport | `ConnectionTcpObfuscated` (obfuscated2) | `ConnectionTcpFull` / default |
| Namespace request | `AndroidFunctions` / `AndroidTypes` | `telethon.functions` / `telethon.types` |

**Aturan namespace request (WAJIB).** Karena ada **dua** salinan Telethon di
mesin ini, `from telethon import functions` selalu mengambil **wheel**.
Kelas request wheel **bukan** instance `TLRequest` milik fork, sehingga
memanggilnya pada client Android gagal:

```
TypeError: You can only invoke requests, not types!
```

Ambil namespace milik client itu sendiri:

```python
# STOR_OTOMATIS/modules/android_client.py  &  BOT_PRIBADI/session_bot/android_client.py
functions, types = tl_for(client)
await client(functions.auth.ResetAuthorizationsRequest())
```

`tl_for(client)` mengembalikan namespace **fork** untuk client Android dan
namespace **wheel** untuk semua client lain, jadi jalur Desktop tidak berubah.

**DILARANG** memakai `from telethon import functions` (atau
`from telethon.tl.functions.* import ...`) untuk membangun request yang akan
dikirim ke client Android — walau `CONSTRUCTOR_ID`-nya identik, kelasnya
berbeda dan akan ditolak.

---

## 2. Kontrak koneksi (transport) — WAJIB

Telegram Android membungkus tiap koneksi MTProto dalam **obfuscated2**
(header acak 64 byte + AES-CTR, codec **abridged**). Di Telethon ini =
**`ConnectionTcpObfuscated`** (codec default-nya `AbridgedPacketCodec`, jadi
sama dengan client asli).

```python
from telethon.network.connection.tcpobfuscated import ConnectionTcpObfuscated
```

**DILARANG** memakai `ConnectionTcpAbridged` (plain, tanpa obfuscation) atau
`ConnectionTcpFull`/`ConnectionTcpIntermediate` untuk jalur Android — itu
membuat transport mudah dibedakan dari app Android asli.

> Catatan: `ConnectionTcpFull` masih boleh dipakai di jalur **Telethon
> Desktop** (bukan Android) pada project yang punya mode desktop, mis.
> `Inti/teleton/*` dan `Inti/td/*`. Yang harus obfuscated adalah **jalur
> Android** (factory `make_android_client`).

---

## 3. Aturan `api_id` / `api_hash`

Semua project memakai **satu identitas** — identitas resmi Telegram Android:

- `api_id = 4`
- `api_hash = "014b35b6184100b085b0d0572f9b5103"`

`api_id` mengidentifikasi **aplikasi**, jadi seluruh project harus konsisten
memakai pasangan **4 / 014b35b6…**. Selain api_id/api_hash, yang juga wajib
diselaraskan: `app_version`, `layer`, `lang_code`, `system_lang_code` (`en-us`),
`lang_pack`, transport (obfuscated), device (`SDK 34/35/36`), dan `perf_cat`
(per device).

---

## 4. Status integrasi tiap project (kondisi SAAT INI — target untuk disamakan)

Semua di bawah ini **sudah benar**; jadikan acuan bila ada project baru/berubah.

### 4.1 `/root/AUTO_REGIST/` (referensi device pool ada di sini)
- Device pool: `/root/AUTO_REGIST/devices.py` → `AndroidDevice.RandomDevice(key)`,
  `system_versions = ["SDK 34", "SDK 35", "SDK 36"]`, `perf_cat` per device (1-3).
- **260 device** (780 kombinasi device x SDK), 24 brand, dari daftar resmi Google
  Play supported devices (lihat §4.1a). BOT_PRIBADI dan STOR_OTOMATIS **memuat
  pool ini langsung** dari `/root/AUTO_REGIST/devices.py`, jadi tidak ada salinan
  yang bisa drift.
- `LOGIN/devices.py` hanya me-re-export pool yang sama (dulu punya 10 device
  sendiri + `random.choice()` yang tidak deterministik).

### 4.1a Sumber device pool & cara regenerate

Sumber: **Google Play supported devices** — daftar resmi Google, upstream dari
semua dataset device Android publik lain:

```
https://storage.googleapis.com/play_public/supported_devices.csv
```

Format: CSV UTF-16, kolom `Retail Branding, Marketing Name, Device, Model`.
`Build.MODEL` = kolom `Model` (string yang benar-benar dikirim device).

Regenerate (script di `/root/scripts/android-device-pool/`):

```bash
curl -sL -o /root/device-sources/play_supported_devices.csv \
  https://storage.googleapis.com/play_public/supported_devices.csv

python3 /root/scripts/android-device-pool/build_android_devices.py \
  --csv /root/device-sources/play_supported_devices.csv \
  --target 260 \
  --out-json /root/device-sources/android_device_pool.json \
  --out-py   /root/device-sources/device_pairs.py
```

Lalu tempel isi `device_pairs.py` ke blok `device_pairs` di
`/root/AUTO_REGIST/devices.py`.

Aturan seleksi (whitelist, bukan blacklist):
- hanya model **modern (2022+)** yang lolos pola per brand — daftar Google memuat
  hardware 15 tahun, jadi blacklist cenderung menghapus keluarga baru sekaligus;
- hanya bentuk **telepon** (TV/tablet/jam/Walkman dikecualikan);
- distribusi **performance class** dijaga 20% LOW / 55% AVERAGE / 25% HIGH agar
  mencerminkan pasar nyata, bukan parade flagship;
- brand dengan kehadiran besar di Indonesia/SEA disertakan (Infinix, TECNO, itel,
  iQOO, POCO, Redmi) — pool yang hanya berisi flagship barat justru anomali untuk
  nomor Indonesia.

**PENTING — efek samping menambah device:** `RandomDevice` memakai
`hash(key) % len(deviceList)`, jadi **setiap perubahan jumlah device mengubah
device untuk SEMUA nomor** yang sudah terdaftar. Nomor lama akan tampak "pindah
HP" dan berisiko freeze. Tambahkan device hanya saat tidak ada akun lama yang
masih dipakai, atau tambahkan mekanisme pin per-nomor lebih dulu.
- `config.ini` (`[config_api]`): `api_id=4`, `api_hash=014b35b6…`,
  `app_version="13.0.3 (7183)"`, `layer=231`, `lang_code="en"`,
  `system_lang_code="en-us"`, `lang_pack="android"`.
- Transport: `src/session_manager.py` → `connection = ConnectionTcpObfuscated`.
- `src/telegram_register.py`, `find_version.py`, `LOGIN/login.py`, dan
  `LOGIN/find_version.py` membangun `params` lewat `telethon.official.init_params()`.
- Self-check: `./venv/bin/python check.py` harus **semua LULUS**.

### 4.2 `/root/STOR_OTOMATIS/` (service: `stor-otomatis.service`)
- Loader Android: `modules/android_client.py`
  - memuat `/root/Telegram_Android/telethon` sebagai modul terisolasi
    `telegram_android` (tidak bentrok dgn `telethon` system),
  - memuat device pool dari `/root/AUTO_REGIST/devices.py`,
  - memilih device acak + `SDK 34/35/36`.
- Konstanta: `ANDROID_API_ID=4`, `ANDROID_API_HASH="014b35b6…"`,
  `ANDROID_APP_VERSION="13.0.3 (7183)"`, `ANDROID_LANG_CODE="en"`,
  `ANDROID_SYSTEM_LANG_CODE="en-us"`.
- Guard `_assert_android_source()`: gagal keras bila `ta.__file__` tidak di
  `/root/Telegram_Android` atau layer ≠ `official.LAYER` (= 231).
- Dipakai oleh `modules/client.py` → `make_stor_client()` → `make_android_client()`.
- `config.json` aktif: `"api_stor": "TelegramAndroid"`.
- `Inti/devices.py` `AndroidDevice.system_versions` mencakup `SDK 34/35/36`.
- `Inti/api.py` `API.TelegramAndroid`: `api_id=4`, hash `014b35b6…`,
  `system_lang_code = "en-us"`.
- **venv** memasang telethon sebagai **editable** ke `/root/Telegram_Android`
  (`.pth` → `MAPPING {'telethon': '/root/Telegram_Android/telethon'}`).
  `requirements.txt` **tidak** boleh memuat baris `telethon==…`.

### 4.3 `/root/BOT_PRIBADI/` (service: `session-bot.service`, python3 system)
- Loader Android: `session_bot/android_client.py` — sama polanya dgn STOR
  (isolasi `telegram_android`, device dari `/root/AUTO_REGIST/devices.py`,
  guard `_assert_android_source()`).
- Konstanta Android: `api_id=4`, hash `014b35b6…`, `app_version=13.0.3
  (7183)`, `lang_code="en"`, `ANDROID_SYSTEM_LANG_CODE="en-us"`.
- Transport Android: `ConnectionTcpObfuscated`.
- **Catatan penting:** service ini jalan di **`/usr/bin/python3`** yang juga
  memasang wheel `telethon 1.44.0` (layer 227). Jalur Android **tetap** harus
  ambil dari `/root/Telegram_Android` (layer 231) lewat loader terisolasi —
  jangan pernah `import telethon` langsung untuk client Android.
  Request TL untuk client Android **wajib** diambil dari namespace client itu
  sendiri (`tl_for(client)` di `android_client.py`, atau `_get_tl(client)` di
  `session_bot/processor.py`). Kelas request dari wheel bukan instance
  `TLRequest` milik fork, jadi `client(wheel_request)` gagal dengan
  `TypeError: You can only invoke requests, not types!`.
- Jalur Desktop (`session_bot/utils.py::make_client` dgn
  `API.TelegramDesktop.Generate(system="windows")`) memang desktop — boleh
  memakai telethon system.
- `Inti/devices.py` `AndroidDevice.system_versions` mencakup `SDK 34/35/36`;
  `Inti/api.py` `API.TelegramAndroid.system_lang_code="en-us"`.

### 4.4 Konsistensi identitas PER-NOMOR (anti-freeze) — WAJIB

Akun Telegram di-freeze bila identitas client **berubah antar koneksi**.
Aturan: untuk satu nomor, `device_model` / `system_version` / `perf_cat` /
`tz_offset` **harus identik** setiap kali sesi dibuka, di **semua** project.

Sumber tunggal device = `AndroidDevice.RandomDevice(<kunci>)`, deterministik
dari string kunci. Karena itu semua pemanggil **harus menormalkan kunci** ke
bentuk yang sama (digit saja) sebelum memanggilnya:

```python
def _normalize_device_id(v):           # STOR modules/android_client.py,
    s = str(v)                         # BOT session_bot/android_client.py
    if s.endswith(".session"): s = s[:-8]
    digits = "".join(c for c in s if c.isdigit())
    return digits or s
```

Riwayat bug (penyebab freeze): kunci berbeda antar jalur untuk nomor yang sama —
- AUTO_REGIST `register_telegram` → `phone.lstrip("+")` → `6281234567890`
- AUTO_REGIST `_create_telegram_client` → `phone.lstrip("+")`
- STOR `open_client_bott` → nama file `+6281234567890.session`
- BOT `process_single` → `parse_phone` → `+6281234567890`
Akibatnya akun lahir sebagai device X, lalu dibuka sebagai device Y/Z →
"pindah HP" → **frozen**. Setelah normalisasi, keempatnya → `6281234567890`.

Aturan tambahan yang sudah diterapkan:
- `tz_offset` selalu dari `official.tz_offset_for(phone)` (bukan timezone acak),
  agar sama antara registrasi dan login berikutnya.
- `device_token`/`perf_cat` di **pin** pada client (`_android_device_token`,
  `_android_perf_cat`) dan dipakai ulang oleh initConnection manual — klien
  resmi menyimpan `pushString` stabil sepanjang sesi.
- `_create_telegram_client(..., phone=phone)` kini meneruskan device+params ke
  `_init_request` client, bukan default `GooglePixel 7`.

### 4.5 Sistem proxy (WAJIB seragam — STOR sebagai acuan)

Ketiga project memakai **mesin proxy yang sama** (pool besar + cooldown +
fallback), hanya lokasi modul yang berbeda:

| Project | File mekanisme | Pool | Fallback |
|---|---|---|---|
| STOR_OTOMATIS | `modules/proxy.py` | `proxy/proxy.txt` (8000) | `proxy/default_proxy.txt` |
| AUTO_REGIST | `src/proxy.py` | `proxy.txt` (8000) | `default_proxy.txt` |
| BOT_PRIBADI | `session_bot/proxy_pool.py` (+ `session_bot/utils.py::resolve_proxy`) | `proxy/proxy.txt` (8000) | `proxy/default_proxy.txt` |

Mesin (identik di ketiganya):
- pilih **acak** dari pool yang tidak sedang cooldown,
- `COOLDOWN_OK = 300 s` setelah dipakai normal, `COOLDOWN_FAIL = 1800 s`
  setelah gagal connect,
- `load_proxies()` **hot-reload** berdasarkan mtime file,
- fallback ke `default_proxy.txt` bila pool kosong / semua cooldown,
- panggil `report_proxy_failure(proxy)` saat connect/gagal, dan
  `report_proxy_success(proxy)` saat sukses.

Rewriting `_cr.<iso>` (khas DataImpulse) dipertahankan di AUTO_REGIST
(`_cr.us`/`_cr.id`) dan BOT_PRIBADI (tabel calling-code lengkap, `_cr.\w+$`);
STOR memakai token apa adanya.

Catatan: proxy **tidak** wajib di AUTO_REGIST & BOT_PRIBADI (koneksi langsung
masih boleh); hanya STOR yang memaksa (`require_stor_proxy`).

### 4.6 Dua anomali identitas yang WAJIB dijaga

1. **DC session harus valid (bukan `dc_id=0`).**
   Klien native menyimpan `currentDatacenterId` di session; bila 0 ia default
   ke DC 2 (`ConnectionsManager.cpp:435-440`). `dc_id=0` di session hasil
   registrasi adalah anomali. Jalur connect utama
   (`src/telegram_register.py`, setelah `client.session.auth_key = ...`)
   **wajib** memanggil `client.session.set_dc(dc_id, DATACENTERS[dc_id], 443)`
   sebelum `save()`. STOR & BOT_PRIBADI sudah melakukannya di jalur connect
   masing-masing; AUTO_REGIST diperbaiki agar setara.

2. **`device_token` untuk device tanpa Google Play Services.**
   `ConnectionsManager.getRegId()` mengirim `SharedConfig.pushString` bila ada
   FCM token, jika tidak → `pushStringStatus`. Di device tanpa Play Services,
   `ApplicationLoader.initPushServices()` men-set
   `pushStringStatus = "__NO_GOOGLE_PLAY_SERVICES__"` (`ApplicationLoader.java:398`)
   dan tidak pernah dapat FCM token. Karena `HAS_GOOGLE_SERVICES = False`,
   `official.device_token()` **harus** mengembalikan
   `"__NO_GOOGLE_PLAY_SERVICES__"` — BUKAN
   `"__FIREBASE_GENERATING_SINCE_*__"` (placeholder itu hanya muncul saat push
   services sedang di-query). Lihat `ConnectionsManager.java:274-284`.

### 4.7 Mode `device_token` FCM asli (opsional)

Selain mode tanpa Play Services (§4.6.2), tersedia **mode token FCM asli**:
token `<id>:APA91b...` yang benar-benar diterbitkan Google untuk sender
Telegram (`760348033671`), diperoleh lewat HTTP (Android check-in +
`c2dm/register3`) dengan cert rilis resmi
(`9723E5838612E9C7C08CA2C6573B6026D7A51F8F`). Modul:
`telethon/fcm_token.py` (`get_fcm_token()`).

Saat mode ini aktif, device **punya** Play Services, jadi kedua hal WAJIB
berubah bersamaan (kalau tidak, jadi anomali):
- `params.device_token` = token asli (bukan `__NO_GOOGLE_PLAY_SERVICES__`),
- `CodeSettings.allow_firebase = allow_app_hash = True`.

Kontrol terpusat ada di `official.py`:
```python
official.apply_push_mode(True)   # set HAS_GOOGLE_SERVICES=True + FCM_TOKEN
official.apply_push_mode(False)  # kembali ke mode tanpa Play Services (default)
official.device_token()          # otomatis ikut mode
```
Token diambil dari env `TELEGRAM_FCM_TOKEN` / cache `~/.telegram_fcm_token`,
atau di-mint saat itu juga. Di AUTO_REGIST, aktifkan lewat
`config.ini` → `[config_api] fcm_device_token = on` (**default sekarang: on**).

**Installer.** `params.installer` = `"com.android.vending"` (Play Store)
**selalu**, di semua mode — termasuk saat `fcm_device_token = off`. Ini pilihan
permanen project: `official.INSTALLER` konstan dan **tidak** ikut berubah saat
`apply_push_mode()` / `set_google_services()` dipanggil, jadi installer stabil
lintas mode. (Dasar kode asli: `ConnectionsManager.java:648-666` —
`getInstallSourceInfo().getInitiatingPackageName()`.)

Catatan: token ini "device dengan GMS"; ia hanya bertahan hidup bila identitas
GCM-nya di-check-in ulang berkala. Untuk registrasi Telegram, token ini hanya
mengubah `params.device_token` + flag CodeSettings — **tidak** mengubah
jaringan SMS. Verifikasi bahwa server menerima identitas: probe
`AUTO_REGIST/test_fcm_device_token.py` (mode `default` vs `fcm`).

**Proxy.** Kedua panggilan Google (check-in + `c2dm/register3`) **wajib
dilewatkan proxy pool** agar IP host tidak bocor dan tidak kena rate-limit
per-IP. API:
`get_fcm_token(proxy=..., proxy_provider=...)`,
`official.apply_push_mode(..., proxy=..., proxy_provider=...)`,
`official.get_or_create_push_token(..., proxy=..., proxy_provider=...)`.
`proxy` menerima:
- tuple PySocks/Telethon `(type, host, port[, rdns, user, pass])`
  (format `src/proxy.py` AUTO_REGIST),
- dict STOR `{proxy_type, addr, port, username, password}`,
- string mentah `scheme://user:pass@host:port` (format `proxy_pool` BOT).

`proxy_provider` (mis. `src.proxy.get_random_proxy` /
`proxy_pool.get_random_proxy_line`) dipanggil **per attempt** sehingga tiap
retry memakai exit IP baru. SOCKS5 didukung **dengan atau tanpa PySocks**:
bila PySocks tidak ada (mis. venv STOR), dipakai klien SOCKS5 manual bawaan
modul. Bila attempt ber-proxy gagal, attempt **terakhir** otomatis fallback ke
koneksi langsung sehingga proxy mati tidak pernah memblokir registrasi.
AUTO_REGIST sudah menyambungkannya di `src/session_manager.py` &
`src/telegram_register.py`.

---

## 5. Verifikasi (WAJIB dijalankan setelah perubahan)

**A. Build ini sendiri**
```bash
/root/AUTO_REGIST/venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "/root/Telegram_Android")
from telethon import official
from telethon.tl.alltlobjects import LAYER
assert LAYER == 231, LAYER
assert LAYER == official.LAYER, (LAYER, official.LAYER)
assert official.APP_VERSION == "13.0.3 (7183)"
assert official.SYSTEM_VERSION == "SDK 36"
assert official.LANG_PACK == "android"
assert official.SYSTEM_LANG_CODE == "en-us"
print("Telegram_Android OK: layer", LAYER, official.APP_VERSION, official.SYSTEM_VERSION)
PY
```

**A2. Identitas anti-anomali (§4.6)**
```bash
/root/AUTO_REGIST/venv/bin/python - <<'PY'
import sys, tempfile, os
sys.path.insert(0, "/root/Telegram_Android")
from telethon.sessions import SQLiteSession
from telethon import official
assert official.device_token() == "__NO_GOOGLE_PLAY_SERVICES__", official.device_token()
assert official.init_params().value[0].value.value == "__NO_GOOGLE_PLAY_SERVICES__"
p = tempfile.mktemp(suffix=".session")
s = SQLiteSession(p); s.set_dc(5, "91.108.56.130", 443); s.save()
assert SQLiteSession(p).dc_id == 5
os.remove(p)
print("identitas anti-anomali OK (device_token + set_dc)")
PY
```

**B. AUTO_REGIST**
```bash
cd /root/AUTO_REGIST && ./venv/bin/python check.py   # harus: semua LULUS
```

**C. STOR_OTOMATIS**
```bash
cd /root/STOR_OTOMATIS && ./venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from modules.android_client import ta, ANDROID_LAYER, AndroidConnectionTcpObfuscated
official = ta.official
assert ta.__file__.startswith("/root/Telegram_Android"), ta.__file__
assert ANDROID_LAYER == 231, ANDROID_LAYER
assert ANDROID_LAYER == official.LAYER, (ANDROID_LAYER, official.LAYER)
assert AndroidConnectionTcpObfuscated.__name__ == "ConnectionTcpObfuscated"
print("STOR Android OK:", ta.__file__)
PY
```

**D. BOT_PRIBADI**
```bash
cd /root/BOT_PRIBADI/session_bot && python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from android_client import ta, ANDROID_LAYER, AndroidConnectionTcpObfuscated
official = ta.official
assert ta.__file__.startswith("/root/Telegram_Android"), ta.__file__
assert ANDROID_LAYER == 231, ANDROID_LAYER
assert ANDROID_LAYER == official.LAYER, (ANDROID_LAYER, official.LAYER)
assert AndroidConnectionTcpObfuscated.__name__ == "ConnectionTcpObfuscated"
import telethon  # system wheel tetap tak tercampur
assert not telethon.__file__.startswith("/root/Telegram_Android")
print("BOT_PRIBADI Android OK:", ta.__file__)
PY
```

**E. Restart service setelah perubahan**
```bash
sudo systemctl restart stor-otomatis session-bot
sleep 10
systemctl is-active stor-otomatis session-bot        # dua-duanya "active"
journalctl -u session-bot --since "1 min ago" --no-pager | grep -iE "Traceback|ImportError" || echo clean
tail -20 /root/STOR_OTOMATIS/logs/stor_service.log | grep -iE "Traceback|ImportError" || echo clean
```

---

## 6. Checklist "sesuaikan semuanya seperti sekarang"

Saat diminta menyamakan seluruh project dengan kontrak ini, pastikan tiap item:

- [ ] Jalur Android memuat dari `/root/Telegram_Android/telethon` (bukan wheel
      PyPI). Untuk STOR_OTOMATIS: editable install/pth. Untuk BOT_PRIBADI:
      loader terisolasi `telegram_android`.
- [ ] `from telethon.network.connection.tcpobfuscated import ConnectionTcpObfuscated`
      dipakai di **semua** factory Android.
- [ ] `app_version = "13.0.3 (7183)"`, `layer = 231` (= `official.LAYER`).
- [ ] `lang_code = "en"`, `system_lang_code = "en-us"`, `lang_pack = "android"`.
- [ ] Device acak dari `/root/AUTO_REGIST/devices.py`, pool mencakup `SDK 36`.
- [ ] Kunci device **dinormalisasi ke digit** (`_normalize_device_id`) di STOR &
      BOT agar device/tz untuk satu nomor **sama** dengan AUTO_REGIST (§4.4).
- [ ] `tz_offset` dari `official.tz_offset_for(phone)` (bukan timezone acak),
      agar konsisten antara registrasi dan login berikutnya.
- [ ] `perf_cat` konsisten dengan device (1-3) di `params` initConnection.
- [ ] Sistem proxy mengikuti STOR (§4.5): pool besar + cooldown 300/1800 +
      fallback `default_proxy.txt` + `report_proxy_failure/success` ter-wire.
- [ ] Session disimpan dengan DC valid (§4.6): `set_dc(dc_id, addr, 443)`
      sebelum `save()` — tidak boleh `dc_id=0`.
- [ ] `official.device_token()` == `"__NO_GOOGLE_PLAY_SERVICES__"` (§4.6)
      selama `HAS_GOOGLE_SERVICES = False`. Bila memakai mode FCM asli (§4.7),
      `fcm_device_token = on` dan `apply_push_mode(True)` membuat
      `device_token()` mengembalikan token asli + `ALLOW_FIREBASE=True`.
- [ ] `api_id = 4` / `api_hash = 014b35b6184100b085b0d0572f9b5103` dipakai
      di semua project.
- [ ] **Jalur Android saja** yang disamakan dengan tabel §1. Jalur Desktop
      (`Inti/api.py` → `API.TelegramDesktop`, `Inti/teleton/*`, `Inti/td/*`)
      tetap memakai identitas & wheel-nya sendiri (§1b) — jangan diubah.
- [ ] Request TL untuk client Android diambil dari namespace client itu sendiri
      (`tl_for(client)`), **bukan** dari `from telethon import functions`
      (wheel) — kalau tidak, `TypeError: You can only invoke requests, not types!`
- [ ] `INTEGRATION.md` ikut diperbarui setiap layer/versi resmi naik.
- [ ] `requirements.txt` project **tidak** memuat `telethon==...`.
- [ ] Semua perintah di §5 lulus, lalu restart service di §5E.
