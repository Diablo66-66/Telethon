"""
Identity constants mirroring the official Telegram Android client
(GitHub DrKLO/Telegram, v13.0.2 build 7175, schema layer 231 generation).

Every connection made by this library sends initConnection params that match
what the official app produces in
TMessagesProj/jni/tgnet/ConnectionsManager.cpp (wrapInLayer) and
TMessagesProj/src/main/java/org/telegram/tgnet/ConnectionsManager.java:

  api_id        = 4                       (BuildVars.APP_ID)
  app_hash      = 014b35b6...             (BuildVars.APP_HASH)
  lang_pack     = "android"               (hardcoded in wrapInLayer)
  app_version   = "<versionName> (<versionCode>)"
  system_version= "SDK <Build.VERSION.SDK_INT>"
  device_model  = Build.MANUFACTURER + Build.MODEL
  params JSON   = {device_token, data, installer, package_id, tz_offset, perf_cat}

Import OFFICIAL_ANDROID_FINGERPRINT and pass **OFFICIAL_ANDROID_FINGERPRINT
to TelegramClient, or rely on TelegramClient's patched defaults.
"""
import os
import time

# org.telegram.messenger.BuildVars
APP_ID = 4
APP_HASH = "014b35b6184100b085b0d0572f9b5103"

# gradle.properties: APP_VERSION_NAME / APP_VERSION_CODE / APP_PACKAGE
VERSION_NAME = "13.0.2"
VERSION_CODE = 7175
PACKAGE_ID = "org.telegram.messenger"

# Java: appVersion = pInfo.versionName + " (" + pInfo.versionCode + ")"
APP_VERSION = f"{VERSION_NAME} ({VERSION_CODE})"

# Java: systemVersion = "SDK " + Build.VERSION.SDK_INT
# SDK 36 = Android 16, matching the official app's compileSdk/targetSdk
SYSTEM_VERSION = "SDK 36"

# TLRPC.java: public static final int LAYER = <n>;  (the schema generation layer)
# Must equal telethon.tl.alltlobjects.LAYER — the generated schema is built
# from the Android client's tlscheme/<LAYER>.json, so the two can never
# legitimately diverge. Consumers (e.g. AUTO_REGIST/check.py) assert on this.
LAYER = 231

# Java: deviceModel = Build.MANUFACTURER + Build.MODEL  (no separator)
# Representative flagship; override per-device if needed.
DEVICE_MODEL = "GooglePixel 7"

# ConnectionsManager.cpp: request->lang_pack = "android"
LANG_PACK = "android"

# LocaleController fallback values.
# lang_code = LocaleController.getLocaleStringIso639() -> translation shortName
# ("en" for the default English pack).
# system_lang_code = getSystemLocaleStringIso639() -> Android system locale in
# "language-COUNTRY" form, lowercased by ConnectionsManager.java:222-223.
LANG_CODE = "en"
SYSTEM_LANG_CODE = "en-us"

# getSystemLocaleStringIso639() reflects the phone's system locale. For this
# project every session intentionally reports the generic "en-us" system
# locale (matching lang_code "en"), instead of deriving it from the number's
# country. lang_code stays "en" (default translation pack).
SYSTEM_LANG_CODE_BY_CC = {
    # Kept for reference / easy re-enable; not used while SYSTEM_LANG_CODE_ALWAYS
    # forces the generic value below.
    "1": "en-us",    # US / Canada
    "62": "id-id",   # Indonesia
    "44": "en-gb",   # UK
    "91": "en-in",   # India
    "7": "ru-ru",    # Russia / Kazakhstan
}

# When True, system_lang_code_for() always returns SYSTEM_LANG_CODE ("en-us")
# regardless of the number's country calling code.
SYSTEM_LANG_CODE_ALWAYS = True

# Coarse timezone (seconds east of UTC) by country calling code, used to keep
# params.tz_offset coherent with the number's region when the caller does not
# provide one. Mirrors TimeZone.getDefault().getRawOffset()/1000 on a device
# set to that region (ConnectionsManager.java:258). Note DST is ignored here:
# the values are the standard-time offsets of each region's main population.
TZ_OFFSET_BY_CC = {
    "1": -5 * 3600,    # US Eastern (standard)
    "62": 7 * 3600,    # Indonesia WIB (UTC+7)
    "44": 0,           # UK (GMT)
    "91": 5 * 3600 + 1800,  # India (UTC+5:30)
    "7": 3 * 3600,     # Russia Moscow (UTC+3)
}


def _pick_by_cc(mapping: dict, phone_number: str, default):
    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())
    # Try longest prefix first so e.g. "1" does not shadow "91"/"62".
    for cc in sorted(mapping, key=len, reverse=True):
        if digits.startswith(cc):
            return mapping[cc]
    return default


def system_lang_code_for(phone_number: str) -> str:
    """Return the system_lang_code ("language-COUNTRY", lowercased).

    With SYSTEM_LANG_CODE_ALWAYS set (default), this always returns the
    generic SYSTEM_LANG_CODE ("en-us") for every number. Set the flag to
    False to fall back to deriving the locale from the calling code."""
    if SYSTEM_LANG_CODE_ALWAYS:
        return SYSTEM_LANG_CODE
    return _pick_by_cc(SYSTEM_LANG_CODE_BY_CC, phone_number, SYSTEM_LANG_CODE)


def tz_offset_for(phone_number: str) -> int:
    """Return a realistic params.tz_offset (seconds east of UTC) for the
    number's region, falling back to the machine's local offset."""
    return _pick_by_cc(TZ_OFFSET_BY_CC, phone_number, _tz_offset())

# Java: installer comes from PackageManager install source
# (ConnectionsManager.java:648-666):
#   SDK >= 30 : getInstallSourceInfo().getInitiatingPackageName()
#               (falls back to getInstallingPackageName())
#   SDK <  30 : getInstallerPackageName()
# The APK is reported as Play-Store-installed ("com.android.vending") in ALL
# modes. This is a permanent project choice: every session advertises that it
# was installed by the Play Store, so params.installer is stable and does not
# depend on the push/GMS mode.
INSTALLER = "com.android.vending"

# Backwards-compatible alias (older callers / probes referenced this name).
INSTALLER_PLAY_STORE = INSTALLER
# SharedConfig performance class: LOW=0, AVERAGE=1, HIGH=2.
# ConnectionsManager.cpp serializes this as perf_cat = class + 1.
PERFORMANCE_CLASS = 2
PERF_CAT = PERFORMANCE_CLASS + 1  # Backwards-compatible wire-value alias.

# AndroidUtilities.getCertificateSHA256Fingerprint() = uppercase hex of the
# SHA256 digest of the DER signing certificate (no separators). This is the
# official org.telegram.messenger release certificate. Sent as the "data" key
# (ConnectionsManager.cpp:3163-3171).
CERT_FINGERPRINT = "49C1522548EBACD46CE322B6FD47F6092BB745D0F88082145CAF35E14DCC38E1"

# GooglePushListenerServiceProvider.hasServices(): whether Google Play Services
# (and therefore Firebase push / Play Integrity) is available. A registration
# slot has none, so both auth.sendCode CodeSettings flags are False
# (LoginActivity.java:3082-3085).
#
# Consequence for device_token: ConnectionsManager.getRegId() returns
# SharedConfig.pushString if a real FCM token exists, otherwise falls back to
# SharedConfig.pushStringStatus. On a device WITHOUT Play Services,
# ApplicationLoader.initPushServices() sets pushStringStatus to
# "__NO_GOOGLE_PLAY_SERVICES__" (ApplicationLoader.java:398) and never
# receives an FCM token, so the official client sends
# "__NO_GOOGLE_PLAY_SERVICES__" — NOT the "__FIREBASE_GENERATING_SINCE_*__"
# placeholder (that one only appears when push services ARE being queried).
# See ConnectionsManager.java:274-284. We therefore mirror the no-services case.
HAS_GOOGLE_SERVICES = False
ALLOW_APP_HASH = HAS_GOOGLE_SERVICES
ALLOW_FIREBASE = HAS_GOOGLE_SERVICES


# ---------------------------------------------------------------------------
# Real FCM push token (optional override).
#
# A device that DOES have Google Play Services registers with FCM and sends the
# resulting token as SharedConfig.pushString (ConnectionsManager.getRegId()).
# On such a device HAS_GOOGLE_SERVICES = True and the CodeSettings flags from
# GooglePushListenerServiceProvider.hasServices() are True as well, so the two
# must be toggled together to stay coherent.
#
# A real FCM/GCM token can be obtained over plain HTTP for the official
# Telegram sender id (760348033671) via the Android check-in + c2dm/register3
# flow, using the official release certificate SHA1:
#     9723E5838612E9C7C08CA2C6573B6026D7A51F8F
# (see `fcm_token.py` helper at the repo root / AUTO_REGIST). Set it here or
# pass `device_token_value=` into init_params() per session.
FCM_TOKEN = None  # e.g. "fdDSUIGouEE:APA91bH_KTp9hGD..."

# When True, the module reports Google Play Services as available and thus
# expects a real FCM token (FCM_TOKEN or per-call override). Keep False for a
# plain registration slot.
def set_google_services(enabled: bool):
    """Toggle the Play-Services identity, keeping the dependent flags coherent.

    ``device_token`` / ``CodeSettings`` flags follow this, but ``INSTALLER``
    does NOT: it stays "com.android.vending" in every mode (permanent choice).
    """
    global HAS_GOOGLE_SERVICES, ALLOW_APP_HASH, ALLOW_FIREBASE
    HAS_GOOGLE_SERVICES = bool(enabled)
    ALLOW_APP_HASH = HAS_GOOGLE_SERVICES
    ALLOW_FIREBASE = HAS_GOOGLE_SERVICES


# Push status stamp matching the official client on a device with no Google
# Play Services (ApplicationLoader.java:398).
NO_GOOGLE_PLAY_SERVICES_TOKEN = "__NO_GOOGLE_PLAY_SERVICES__"


def device_token(has_google_services: bool = None, directive_time: bool = True,
                 fcm_token: str = None):
    """ConnectionsManager.getRegId() equivalent.

    * No Play Services (default for a registration slot): the official client
      reports "__NO_GOOGLE_PLAY_SERVICES__" (ApplicationLoader.java:398 ->
      getRegId() at ConnectionsManager.java:274-284).
    * With Play Services: a real FCM token is reported
      (SharedConfig.pushString). If none is available yet, the placeholder
      "__FIREBASE_GENERATING_SINCE_<unixtime>__" is reported
      (ConnectionsManager.java:283).

    `has_google_services` overrides the module default; `directive_time`
    controls whether the FIREBASE placeholder carries the current time; and
    `fcm_token` (or the module-level FCM_TOKEN) supplies the real token when
    Play Services are present.
    """
    if has_google_services is None:
        has_google_services = HAS_GOOGLE_SERVICES
    if not has_google_services:
        return NO_GOOGLE_PLAY_SERVICES_TOKEN
    token = fcm_token if fcm_token is not None else FCM_TOKEN
    if token:
        return token
    return f"__FIREBASE_GENERATING_SINCE_{int(time.time())}__"


def init_params(device_token_value=None, tz_offset=None, perf_cat=None,
                installer=None, data=None, package_id=None,
                performance_class=None):
    """Build the TL JSONObject passed as initConnection `params`.

    ``perf_cat`` is the wire value serialized by the official native client
    (ConnectionsManager.cpp writes ``currentPerformanceClass + 1``), i.e.
    1=low, 2=average, 3=high. It is written to the params JSON unchanged.
    This matches ``DeviceInfo.perf_cat`` in consumers (already ``class + 1``)
    and this module's ``PERF_CAT``. The default is ``PERF_CAT`` (3, high).

    Callers that hold a SharedConfig performance class (0=low, 1=average,
    2=high) instead may pass ``performance_class=<0..2>``; it is converted
    with ``+ 1``. Passing both ``perf_cat`` and ``performance_class`` is an
    error.
    """
    from .tl import types

    def kv(key, value):
        return types.JsonObjectValue(key=key, value=value)

    value = []
    value.append(kv("device_token", types.JsonString(
        value=device_token_value if device_token_value is not None else device_token())))
    value.append(kv("data", types.JsonString(
        value=data if data is not None else CERT_FINGERPRINT)))
    value.append(kv("installer", types.JsonString(
        value=installer if installer is not None else INSTALLER)))
    value.append(kv("package_id", types.JsonString(
        value=package_id if package_id is not None else PACKAGE_ID)))
    value.append(kv("tz_offset", types.JsonNumber(
        value=_tz_offset() if tz_offset is None else int(tz_offset))))
    if perf_cat is not None and performance_class is not None:
        raise ValueError(
            "pass only one of perf_cat (wire 1..3) and performance_class "
            "(class 0..2), got perf_cat=%r and performance_class=%r"
            % (perf_cat, performance_class))
    if performance_class is not None:
        if (not isinstance(performance_class, int)
                or isinstance(performance_class, bool)
                or not 0 <= performance_class <= 2):
            raise ValueError(
                "performance_class must be 0, 1 or 2, got %r"
                % (performance_class,))
        perf_cat = performance_class + 1
    if perf_cat is None:
        perf_cat = PERF_CAT
    if (not isinstance(perf_cat, int) or isinstance(perf_cat, bool)
            or not 1 <= perf_cat <= 3):
        raise ValueError("perf_cat must be 1, 2 or 3 (wire value), got %r" % (perf_cat,))
    value.append(kv("perf_cat", types.JsonNumber(value=perf_cat)))
    return types.JsonObject(value=value)


def _tz_offset():
    # native side stores seconds east of UTC; POSIX timezone is inverted
    if time.daylight and time.localtime().tm_isdst > 0:
        return -time.altzone
    return -time.timezone


OFFICIAL_ANDROID_FINGERPRINT = dict(
    api_id=APP_ID,
    device_model=DEVICE_MODEL,
    system_version=SYSTEM_VERSION,
    app_version=APP_VERSION,
    lang_code=LANG_CODE,
    system_lang_code=SYSTEM_LANG_CODE,
)


def get_push_token(cache_path: str = None, use_env: bool = True):
    """Return a real FCM token for the Telegram sender, or None.

    Resolution order:
      1. ``TELEGRAM_FCM_TOKEN`` environment variable (or ``FCM_TOKEN``).
      2. A cached token file (``cache_path`` / ``TELEGRAM_FCM_TOKEN_FILE`` /
         ``~/.telegram_fcm_token``), containing just the token.
      3. A fresh token minted over HTTP by ``telethon.fcm_token`` (Android
         check-in + c2dm/register3) — only when ``mint_if_missing`` is desired,
         i.e. there is no cached value and env lookup failed.

    The token has the form ``<id>:APA91b...``. It corresponds to an app
    instance that HAS Google Play Services, so callers that use it must also
    advertise Play Services (see ``set_google_services(True)``).
    """
    if use_env:
        for key in ("TELEGRAM_FCM_TOKEN", "FCM_TOKEN"):
            value = os.environ.get(key)
            if value:
                return value.strip()

    candidates = []
    if cache_path:
        candidates.append(cache_path)
    env_path = os.environ.get("TELEGRAM_FCM_TOKEN_FILE")
    if env_path:
        candidates.append(env_path)
    candidates.append(os.path.join(os.path.expanduser("~"), ".telegram_fcm_token"))
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
            if value:
                return value
        except OSError:
            continue
    return None


def get_or_create_push_token(cache_path: str = None, proxy=None,
                             proxy_provider=None):
    """Like :func:`get_push_token` but mints and caches one if absent.

    ``proxy`` / ``proxy_provider`` are forwarded to
    :func:`telethon.fcm_token.get_fcm_token`; a ``proxy_provider`` rotates the
    exit IP on each retry (e.g. ``src.proxy.get_random_proxy``).
    """
    token = get_push_token(cache_path=cache_path)
    if token:
        return token
    from . import fcm_token as _fcm
    result = _fcm.get_fcm_token(proxy=proxy, proxy_provider=proxy_provider)
    token = result["token"]
    path = cache_path or os.environ.get("TELEGRAM_FCM_TOKEN_FILE") or \
        os.path.join(os.path.expanduser("~"), ".telegram_fcm_token")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(token)
    except OSError:
        pass
    return token


def apply_push_mode(enabled: bool, cache_path: str = None,
                    mint: bool = True, proxy=None,
                    proxy_provider=None) -> str:
    """Switch the module to/from the "device with Play Services" identity.

    When ``enabled`` is true:
      * ``HAS_GOOGLE_SERVICES`` (and thus ``ALLOW_APP_HASH`` / ``ALLOW_FIREBASE``)
        are set True, so ``CodeSettings`` advertises Firebase SMS support.
      * ``FCM_TOKEN`` is set to a real token (cached/env, or freshly minted when
        ``mint`` is true), so ``device_token()`` returns it instead of a
        placeholder. Minting goes through ``proxy`` / ``proxy_provider`` when
        given, so the Google check-in/register traffic does not leak the host
        IP (see ``telethon.fcm_token``).

    When false, the module reverts to the no-Play-Services identity and
    ``device_token()`` returns ``"__NO_GOOGLE_PLAY_SERVICES__"``.

    Returns the token in use (empty string when disabled).
    """
    global FCM_TOKEN
    if not enabled:
        FCM_TOKEN = None
        set_google_services(False)
        return ""
    token = get_push_token(cache_path=cache_path)
    if not token and mint:
        try:
            token = get_or_create_push_token(
                cache_path=cache_path, proxy=proxy,
                proxy_provider=proxy_provider)
        except Exception:
            # GCM endpoint is deprecated/flaky. Never let a mint failure crash
            # the caller: fall back to the no-Play-Services identity so the
            # session stays coherent (token placeholder + GMS-off flags).
            FCM_TOKEN = None
            set_google_services(False)
            return ""
    FCM_TOKEN = token
    set_google_services(True)
    return token or ""
