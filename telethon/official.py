"""
Identity constants mirroring the official Telegram Android client
(GitHub DrKLO/Telegram, v12.10.1 build 7038, schema layer 229 generation).

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
  params JSON   = {installer, package_id, tz_offset, perf_cat}

Import OFFICIAL_ANDROID_FINGERPRINT and pass **OFFICIAL_ANDROID_FINGERPRINT
to TelegramClient, or rely on TelegramClient's patched defaults.
"""
import time

# org.telegram.messenger.BuildVars
APP_ID = 4
APP_HASH = "014b35b6184100b085b0d0572f9b5103"

# gradle.properties: APP_VERSION_NAME / APP_VERSION_CODE / APP_PACKAGE
VERSION_NAME = "12.10.1"
VERSION_CODE = 7038
PACKAGE_ID = "org.telegram.messenger"

# Java: appVersion = pInfo.versionName + " (" + pInfo.versionCode + ")"
APP_VERSION = f"{VERSION_NAME} ({VERSION_CODE})"

# Java: systemVersion = "SDK " + Build.VERSION.SDK_INT
# SDK 36 = Android 16, matching the official app's compileSdk/targetSdk
SYSTEM_VERSION = "SDK 36"

# Java: deviceModel = Build.MANUFACTURER + Build.MODEL  (no separator)
# Representative flagship; override per-device if needed.
DEVICE_MODEL = "GooglePixel 7"

# ConnectionsManager.cpp: request->lang_pack = "android"
LANG_PACK = "android"

# LocaleController fallback values
LANG_CODE = "en"
SYSTEM_LANG_CODE = "en"

# Java: installer comes from getInstallerPackageName() (Play) ;
# perf_cat is currentPerformanceClass + 1 (1=low ... 4=high-end tier).
INSTALLER = "com.android.vending"
PERF_CAT = 4


def init_params():
    """Build the TL JSONObject passed as initConnection `params`,
    identical in shape to the official native client."""
    from .tl import types

    def kv(key, value):
        return types.JsonObjectValue(key=key, value=value)

    value = []
    value.append(kv("installer", types.JsonString(value=INSTALLER)))
    value.append(kv("package_id", types.JsonString(value=PACKAGE_ID)))
    value.append(kv("tz_offset", types.JsonNumber(value=_tz_offset())))
    value.append(kv("perf_cat", types.JsonNumber(value=PERF_CAT)))
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
