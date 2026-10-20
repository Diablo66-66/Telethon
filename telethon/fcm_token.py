"""Obtain a real FCM/GCM push token for the official Telegram Android sender.

This reproduces, over plain HTTP, what the official client does on a device
that has Google Play Services:

  1. Android check-in  (https://android.clients.google.com/checkin)
         -> android_id + security_token + deviceCheckinConsistencyToken
  2. GCM registration  (https://android.clients.google.com/c2dm/register3)
         -> a real token of the form "<id>:APA91b..."

The token is then reported as ``params.device_token`` (the native client's
``SharedConfig.pushString`` via ``ConnectionsManager.getRegId()``), which is
exactly what the official app sends when Play Services are present.

Sender id / cert are the official Telegram Android values:
  * sender   = 760348033671        (= Firebase project number, tmessages2)
  * app      = org.telegram.messenger
  * cert     = release certificate SHA1 (AndroidUtilities fingerprint)

Note: a token is only *valid* (deliverable) if it is kept alive with a periodic
check-in/register on the same GCM identity; this helper is meant to mint the
token used in the MTProto initConnection params, matching an app instance that
has push registration.

Proxy: the two HTTP calls can be tunnelled through the shared proxy pool
(``proxy`` = STOR dict / PySocks tuple / raw URL, ``proxy_provider`` = callable
returning a fresh proxy per attempt). SOCKS5 works with or without PySocks: an
in-module manual SOCKS5 client is used when PySocks is unavailable, so every
project can route the Google traffic through its exit IP. If a proxied attempt
fails, the final attempt falls back to a direct connection so a dead proxy can
never block registration.
"""
from __future__ import annotations

import os
import random
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request

# Official Telegram Android identity.
SENDER = "760348033671"
PACKAGE_ID = "org.telegram.messenger"
CERT_SHA1 = "9723E5838612E9C7C08CA2C6573B6026D7A51F8F"

# The GCM register call reports the app version of the instance being emulated.
# Keep it derived from telethon.official so a client bump cannot leave this
# stale (a mismatched version here is a fingerprint inconsistency).
try:
    from .official import VERSION_CODE as _APP_VERSION_CODE, VERSION_NAME as _APP_VERSION_NAME
except Exception:  # pragma: no cover - official.py ships with the fork
    _APP_VERSION_CODE, _APP_VERSION_NAME = 7183, "13.0.3"

CHECKIN_URL = "https://android.clients.google.com/checkin"
REGISTER_URL = "https://android.clients.google.com/c2dm/register3"

# A representative build fingerprint the check-in endpoint accepts.
_BUILD_FINGERPRINT = (
    "google/sdk_gphone64_x86_64/emu64x:16/BP22/1671234:user/release-keys"
)


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field(num: int, wire: int, payload: bytes) -> bytes:
    return _varint((num << 3) | wire) + payload


def _str_field(num: int, value: str) -> bytes:
    data = value.encode()
    return _field(num, 2, _varint(len(data)) + data)


def _msg_field(num: int, payload: bytes) -> bytes:
    return _field(num, 2, _varint(len(payload)) + payload)


def _int_field(num: int, value: int) -> bytes:
    return _field(num, 0, _varint(value))


def _read_varint(data: bytes, i: int):
    shift = 0
    result = 0
    while True:
        b = data[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _luhn_imei() -> str:
    base = ("35" + "%012d" % random.getrandbits(40))[:14]
    total = 0
    for idx, ch in enumerate(reversed(base)):
        d = int(ch)
        if idx % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return base + str((10 - (total % 10)) % 10)


def _build_checkin() -> bytes:
    # AndroidBuildProto
    build = b""
    build += _str_field(1, _BUILD_FINGERPRINT)   # id
    build += _str_field(2, "emu64x")             # product
    build += _str_field(6, "android-google")     # client
    build += _int_field(7, 1671234000)           # timestamp
    build += _int_field(8, 36)                   # googleServices
    build += _str_field(9, "emu64x")             # device
    build += _int_field(10, 36)                  # sdkVersion
    build += _str_field(11, "Pixel 7")           # model
    build += _str_field(12, "Google")            # manufacturer
    build += _str_field(13, "emu64x")            # buildProduct

    # AndroidCheckinProto
    checkin = _msg_field(1, build)               # build
    checkin += _str_field(6, "")                 # cellOperator
    checkin += _str_field(7, "")                 # simOperator
    checkin += _str_field(8, "")                 # roaming

    # AndroidCheckinRequest
    req = b""
    req += _str_field(1, _luhn_imei())           # imei
    req += _int_field(2, 0)                      # id (0 = new)
    req += _msg_field(4, checkin)                # checkin
    req += _str_field(6, "en-US")                # locale
    req += _int_field(7, random.getrandbits(63)) # loggingId
    req += _int_field(13, 0)                     # securityToken
    req += _int_field(14, 3)                     # version
    return req


_PYSOCKS_TYPE_NAMES = {1: "socks4", 2: "socks5", 3: "http"}


def _proxy_url(proxy) -> str | None:
    """Build a canonical ``scheme://[user:pass@]host:port`` proxy URL.

    Accepts any of the shapes used across the projects:
      * a raw URL string ``socks5://user:pass@host:port``;
      * a STOR dict ``{proxy_type, addr, port, username, password}``;
      * a PySocks/Telethon tuple ``(type, host, port[, rdns, user, pass])``
        where type is ``socks.PROXY_TYPE_{SOCKS4=1,SOCKS5=2,HTTP=3}``.
    """
    if not proxy:
        return None
    if isinstance(proxy, str):
        return proxy

    # PySocks / Telethon tuple form.
    if isinstance(proxy, (tuple, list)) and proxy and isinstance(proxy[0], int):
        ptype = _PYSOCKS_TYPE_NAMES.get(proxy[0], "socks5")
        addr, port = proxy[1], proxy[2]
        user = proxy[4] if len(proxy) > 4 else None
        pw = proxy[5] if len(proxy) > 5 else None
        if user is not None and pw is not None:
            return (f"{ptype}://{urllib.parse.quote(str(user))}:"
                    f"{urllib.parse.quote(str(pw))}@{addr}:{port}")
        return f"{ptype}://{addr}:{port}"

    # STOR dict form.
    if isinstance(proxy, dict):
        ptype = proxy.get("proxy_type", "http")
        addr = proxy.get("addr")
        port = proxy.get("port")
        if not addr or not port:
            return None
        user = proxy.get("username")
        pw = proxy.get("password")
        if user is not None and pw is not None:
            return (f"{ptype}://{urllib.parse.quote(str(user))}:"
                    f"{urllib.parse.quote(str(pw))}@{addr}:{port}")
        return f"{ptype}://{addr}:{port}"
    return None


def _socks5_connect(proxy_url: str, dest_host: str, dest_port: int,
                    timeout: float):
    """Open a socket to ``dest_host:dest_port`` through a SOCKS5 proxy.

    Uses PySocks when available; otherwise speaks SOCKS5 directly over a raw
    socket (no username/password method support in the manual path, which is
    all we need since the pool requires auth only via the PySocks path).
    Returns a connected ``socket.socket`` or raises.
    """
    parts = urllib.parse.urlsplit(proxy_url)
    p_host, p_port = parts.hostname, parts.port
    p_user = urllib.parse.unquote(parts.username) if parts.username else None
    p_pass = urllib.parse.unquote(parts.password) if parts.password else None
    if not p_host or not p_port:
        raise ValueError(f"invalid socks5 proxy: {proxy_url!r}")

    try:  # preferred: PySocks handles auth + IPv6 + rdns
        import socks  # type: ignore

        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, p_host, p_port, rdns=True,
                    username=p_user, password=p_pass)
        s.settimeout(timeout)
        s.connect((dest_host, dest_port))
        return s
    except ImportError:
        pass

    # Manual SOCKS5 (no-auth only).
    s = socket.create_connection((p_host, p_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        if p_user is not None:
            s.sendall(b"\x05\x02\x00\x02")
        else:
            s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if len(resp) < 2 or resp[0] != 0x05 or resp[1] == 0xFF:
            raise OSError(f"socks5 handshake failed: {resp!r}")
        if resp[1] == 0x02:  # username/password auth
            u = p_user.encode()
            p = (p_pass or "").encode()
            s.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            ar = s.recv(2)
            if len(ar) < 2 or ar[1] != 0x00:
                raise OSError("socks5 auth failed")
        # CONNECT with a domain-name address (rdns handled by the proxy).
        host_b = dest_host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b +
                  struct.pack(">H", dest_port))
        rep = s.recv(4)
        if len(rep) < 4 or rep[1] != 0x00:
            raise OSError(f"socks5 connect failed: {rep!r}")
        atyp = rep[3]
        if atyp == 0x01:
            s.recv(4)
        elif atyp == 0x03:
            n = s.recv(1)[0]
            s.recv(n)
        elif atyp == 0x04:
            s.recv(16)
        s.recv(2)  # bound port
        return s
    except Exception:
        s.close()
        raise


def _socks5_urlopen(req: urllib.request.Request, proxy_url: str,
                    timeout: float):
    """Send ``req`` over an HTTPS connection tunneled through a SOCKS5 proxy."""
    import http.client

    url = urllib.parse.urlsplit(req.full_url)
    host = url.hostname
    port = url.port or (443 if url.scheme == "https" else 80)
    raw = _socks5_connect(proxy_url, host, port, timeout)
    if url.scheme == "https":
        import ssl

        ctx = ssl.create_default_context()
        raw = ctx.wrap_socket(raw, server_hostname=host)
        conn = http.client.HTTPSConnection(host, port, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
    # Inject the already-connected tunneled socket.
    conn.sock = raw
    path = url.path or "/"
    if url.query:
        path += "?" + url.query
    conn.putrequest(req.get_method(), path)
    for key, value in req.header_items():
        conn.putheader(key, value)
    conn.putheader("Host", host)
    if req.data is not None:
        conn.putheader("Content-Length", str(len(req.data)))
    conn.endheaders()
    if req.data is not None:
        conn.send(req.data)
    return conn.getresponse()


def _post(url: str, data: bytes, headers: dict, proxy=None) -> tuple[int, bytes]:
    proxy_url = _proxy_url(proxy)
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    scheme = urllib.parse.urlsplit(proxy_url).scheme if proxy_url else None
    try:
        if proxy_url and scheme in ("socks5", "socks5h", "socks4"):
            with _socks5_urlopen(req, proxy_url, timeout=25) as resp:
                return resp.status, resp.read()
        handlers = []
        if proxy_url and scheme in ("http", "https"):
            handlers.append(urllib.request.ProxyHandler(
                {"http": proxy_url, "https": proxy_url}))
        opener = urllib.request.build_opener(*handlers)
        with opener.open(req, timeout=25) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check_in(proxy=None) -> dict:
    """Perform an Android check-in; returns androidId/securityToken."""
    status, body = _post(
        CHECKIN_URL,
        _build_checkin(),
        {"Content-Type": "application/x-protobuf",
         "User-Agent": "Android-Checkin/3.0"},
        proxy=proxy,
    )
    if status != 200:
        raise RuntimeError(f"checkin failed: HTTP {status} {body[:200]!r}")
    fields: dict[int, list] = {}
    i = 0
    while i < len(body):
        tag, i = _read_varint(body, i)
        num, wire = tag >> 3, tag & 7
        if wire == 0:
            value, i = _read_varint(body, i)
            fields.setdefault(num, []).append(value)
        elif wire == 1:
            value = struct.unpack("<Q", body[i:i + 8])[0]
            i += 8
            fields.setdefault(num, []).append(value)
        elif wire == 2:
            length, i = _read_varint(body, i)
            fields.setdefault(num, []).append(("bytes", body[i:i + length]))
            i += length
        elif wire == 5:
            fields.setdefault(num, []).append(("f32",))
            i += 4
        else:
            break
    if 7 not in fields or 8 not in fields:
        raise RuntimeError(f"checkin response missing creds: {fields}")
    android_id = fields[7][0]
    security_token = fields[8][0]
    token = None
    if 12 in fields and isinstance(fields[12][0], tuple):
        token = fields[12][0][1].decode(errors="replace")
    return {"androidId": android_id, "securityToken": security_token,
            "consistencyToken": token}


def gcm_register(android_id, security_token, *,
                 app: str = PACKAGE_ID, sender: str = SENDER,
                 cert: str = CERT_SHA1, subtype: str = None,
                 proxy=None) -> str:
    """Register the instance with GCM; returns the real "<id>:APA91b..." token."""
    body = urllib.parse.urlencode({
        "app": app,
        "X-subtype": subtype or sender,
        "sender": sender,
        "device": str(android_id),
        "cert": cert,
        "app_ver": str(_APP_VERSION_CODE),
        "app_ver_name": _APP_VERSION_NAME,
        "gcm_ver": "240000000",
    })
    status, raw = _post(
        REGISTER_URL,
        body.encode(),
        {"Authorization": f"AidLogin {android_id}:{security_token}",
         "Content-Type": "application/x-www-form-urlencoded",
         "User-Agent": "android-gcm/1.5 (Pixel 7)"},
        proxy=proxy,
    )
    text = raw.decode(errors="replace")
    if status != 200 or "token=" not in text:
        raise RuntimeError(f"gcm register failed: HTTP {status} {text[:200]!r}")
    return text.split("token=", 1)[1].strip()


def get_fcm_token(retries: int = 5, proxy=None,
                  proxy_provider=None) -> dict:
    """Full flow: check-in then register. Returns token + credentials.

    GCM ``register3`` intermittently answers ``PHONE_REGISTRATION_ERROR`` even
    with valid credentials; each retry performs a fresh check-in on a new GCM
    identity, which clears the transient rejection.

    ``proxy`` is a STOR/auto-regist proxy dict
    (``{proxy_type, addr, port, username, password}``) or a raw URL string.
    When ``proxy_provider`` is given it is called on each attempt to obtain a
    *fresh* proxy (e.g. ``proxy.get_random_proxy``), so retries rotate the exit
    IP; ``proxy`` is then used only as the initial/fallback value. If a proxied
    attempt fails hard, the next attempt falls back to a direct connection so a
    broken/expired proxy can never block registration entirely.
    """
    last: Exception | None = None
    current = proxy
    for attempt in range(retries):
        if proxy_provider is not None:
            try:
                current = proxy_provider() or current
            except Exception:  # noqa: BLE001 - provider must never be fatal
                pass
        # After the first failed attempt, stop forcing the (possibly dead)
        # proxy: the last attempt always goes direct.
        use_proxy = current if attempt < retries - 1 else None
        try:
            creds = check_in(proxy=use_proxy)
            token = gcm_register(creds["androidId"], creds["securityToken"],
                                 proxy=use_proxy)
            creds["token"] = token
            return creds
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last = exc
    raise RuntimeError(f"unable to obtain FCM token after {retries} tries: {last}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Mint a real FCM token")
    ap.add_argument("--proxy", help="proxy URL, e.g. http://user:pass@host:port")
    ap.add_argument("--retries", type=int, default=5)
    args = ap.parse_args()
    result = get_fcm_token(retries=args.retries, proxy=args.proxy)
    print("device_token:", result["token"])
    print("android_id:", result["androidId"])
    print("security_token:", result["securityToken"])
