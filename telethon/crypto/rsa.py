"""
This module holds several utilities regarding RSA and server fingerprints.
"""
import os
import struct
import hashlib
from hashlib import sha1

from ..crypto.aes import AES
try:
    import rsa
    import rsa.core
except ImportError:
    rsa = None
    raise ImportError('Missing module "rsa", please install via pip.')

from ..tl import TLObject


# {fingerprint: (Crypto.PublicKey.RSA._RSAobj, old)} dictionary
_server_keys = {}


def get_byte_array(integer):
    """Return the variable length bytes corresponding to the given int"""
    # Operate in big endian (unlike most of Telegram API) since:
    # > "...pq is a representation of a natural number
    #    (in binary *big endian* format)..."
    # > "...current value of dh_prime equals
    #    (in *big-endian* byte order)..."
    # Reference: https://core.telegram.org/mtproto/auth_key
    return int.to_bytes(
        integer,
        (integer.bit_length() + 8 - 1) // 8,  # 8 bits per byte,
        byteorder='big',
        signed=False
    )


def _compute_fingerprint(key):
    """
    Given a RSA key, computes its fingerprint like Telegram does.

    :param key: the Crypto.RSA key.
    :return: its 8-bytes-long fingerprint.
    """
    n = TLObject.serialize_bytes(get_byte_array(key.n))
    e = TLObject.serialize_bytes(get_byte_array(key.e))
    # Telegram uses the last 8 bytes as the fingerprint
    return struct.unpack('<q', sha1(n + e).digest()[-8:])[0]


def add_key(pub, *, old):
    """Adds a new public key to be used when encrypting new data is needed"""
    global _server_keys
    key = rsa.PublicKey.load_pkcs1(pub)
    _server_keys[_compute_fingerprint(key)] = (key, old)


def encrypt(fingerprint, data, *, use_old=False):
    """
    Encrypts ``data`` with the server RSA key identified by ``fingerprint``,
    using the modern rsa_pad scheme required since the 0xd09d1d85de64fd85
    production key was introduced (mirrors official Telegram Android
    Handshake.cpp encrypt + TDesktop EncryptUtilities::rsaEncryptV2):

      buf[0:32]     = random AES-256 key
      buf[32:224]   = AES-256-IGE(data_with_padding, aes_key, iv=0)
      buf[224:256]  = sha256(buf[32:224])            (iv for the second pass)
      buf[32:224]   = AES-256-IGE(data_with_padding, aes_key, buf[224:256])
      buf[0:32]    ^= sha256(buf[32:256])
      cipher        = RSA(buf[0:256])

    data_with_padding = data followed by random bytes up to 192 total,
    reversed, so that the server-side checksum check passes with
    overwhelming probability (retry loop mirrors Handshake.cpp).
    Old keys (pre-2022) keep the legacy sha1(data) + data + random padding.

    :param fingerprint: the fingerprint of the RSA key.
    :param data: the serialized inner data (max 144 bytes).
    :param use_old: whether old (deprecated) keys should be used.
    :return: the 256-byte cipher text, or None if no key matches.
    """
    global _server_keys
    key, old = _server_keys.get(fingerprint, [None, None])
    if (not key) or (old and not use_old):
        return None

    if old:
        # Legacy rsa_pad v1: sha1(data) + data + random padding.
        to_encrypt = sha1(data).digest() + data + os.urandom(235 - len(data))
        payload = int.from_bytes(to_encrypt, 'big')
        encrypted = rsa.core.encrypt_int(payload, key.e, key.n)
        return encrypted.to_bytes(256, 'big')

    # rsa_pad v2 — exact port of Telegram Android Handshake.cpp encrypt loop.
    # Buffer layout:
    #   [0..32)      AES key (random; XORed with final digest at the end)
    #   [32..224)    padded data (reversed), AES-IGE encrypted in place
    #   [224..256)   sha256(aes_key || work_area) before encryption
    #   [256..448)   work area: inner data + random padding
    #   [448..480)   zero IV area
    #   [480..512)   final sha256 over the encrypted region
    if len(data) > 144:
        raise ValueError('Inner data too large for rsa_pad v2: {}'.format(len(data)))

    key_size = 32
    iv_size = 32
    sha_size = 32
    padded_data_size = 192
    encrypted_data_size = key_size + padded_data_size + sha_size  # 256

    while True:
        buf = bytearray(encrypted_data_size + padded_data_size + iv_size + sha_size + 256)

        # 1) inner data at [256..), random padding up to [256..448)
        buf[encrypted_data_size:encrypted_data_size + len(data)] = data
        if len(data) < padded_data_size:
            buf[encrypted_data_size + len(data):encrypted_data_size + padded_data_size] = \
                os.urandom(padded_data_size - len(data))

        # 2) reversed copy of the work area into [32..224)
        for i in range(padded_data_size):
            buf[key_size + i] = buf[encrypted_data_size + padded_data_size - i - 1]

        # 3) random AES key at [0..32)
        buf[:key_size] = os.urandom(key_size)

        # 4) sha256(aes_key || work_area[256..448)) -> [224..256)
        h1 = hashlib.sha256(
            bytes(buf[:key_size])
            + bytes(buf[encrypted_data_size:encrypted_data_size + padded_data_size])
        ).digest()
        buf[key_size + padded_data_size:key_size + padded_data_size + sha_size] = h1

        # 5) AES-256-IGE in place over [32..256) with zero IV
        enc = AES.encrypt_ige(
            bytes(buf[key_size:key_size + padded_data_size + sha_size]),
            bytes(buf[:key_size]),
            bytes(iv_size),
        )
        buf[key_size:key_size + padded_data_size + sha_size] = enc

        # 6) sha256 over the encrypted 224 bytes -> [480..512)
        tail_offset = encrypted_data_size + padded_data_size + iv_size
        h2 = hashlib.sha256(
            bytes(buf[key_size:key_size + padded_data_size + sha_size])
        ).digest()
        buf[tail_offset:tail_offset + sha_size] = h2

        # 7) XOR the AES key with h2
        for i in range(key_size):
            buf[i] ^= buf[tail_offset + i]

        # 8) retry until buf[0..256) < modulus, then RSA modexp
        candidate = int.from_bytes(bytes(buf[:encrypted_data_size]), 'big')
        if candidate < key.n:
            encrypted = rsa.core.encrypt_int(candidate, key.e, key.n)
            return encrypted.to_bytes(256, 'big')


# Add default keys
# https://github.com/DrKLO/Telegram/blob/a724d96e9c008b609fe188d122aa2922e40de5fc/TMessagesProj/jni/tgnet/Handshake.cpp#L356-L436
for pub in (
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAruw2yP/BCcsJliRoW5eBVBVle9dtjJw+OYED160Wybum9SXtBBLX
riwt4rROd9csv0t0OHCaTmRqBcQ0J8fxhN6/cpR1GWgOZRUAiQxoMnlt0R93LCX/
j1dnVa/gVbCjdSxpbrfY2g2L4frzjJvdl84Kd9ORYjDEAyFnEA7dD556OptgLQQ2
e2iVNq8NZLYTzLp5YpOdO1doK+ttrltggTCy5SrKeLoCPPbOgGsdxJxyz5KKcZnS
Lj16yE5HvJQn0CNpRdENvRUXe6tBP78O39oJ8BTHp9oIjd6XWXAsp2CvK45Ol8wF
XGF710w9lwCGNbmNxNYhtIkdqfsEcwR5JwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAvfLHfYH2r9R70w8prHblWt/nDkh+XkgpflqQVcnAfSuTtO05lNPs
pQmL8Y2XjVT4t8cT6xAkdgfmmvnvRPOOKPi0OfJXoRVylFzAQG/j83u5K3kRLbae
7fLccVhKZhY46lvsueI1hQdLgNV9n1cQ3TDS2pQOCtovG4eDl9wacrXOJTG2990V
jgnIKNA0UMoP+KF03qzryqIt3oTvZq03DyWdGK+AZjgBLaDKSnC6qD2cFY81UryR
WOab8zKkWAnhw2kFpcqhI0jdV5QaSCExvnsjVaX0Y1N0870931/5Jb9ICe4nweZ9
kSDF/gip3kWLG0o8XQpChDfyvsqB9OLV/wIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAs/ditzm+mPND6xkhzwFIz6J/968CtkcSE/7Z2qAJiXbmZ3UDJPGr
zqTDHkO30R8VeRM/Kz2f4nR05GIFiITl4bEjvpy7xqRDspJcCFIOcyXm8abVDhF+
th6knSU0yLtNKuQVP6voMrnt9MV1X92LGZQLgdHZbPQz0Z5qIpaKhdyA8DEvWWvS
Uwwc+yi1/gGaybwlzZwqXYoPOhwMebzKUk0xW14htcJrRrq+PXXQbRzTMynseCoP
Ioke0dtCodbA3qQxQovE16q9zz4Otv2k4j63cz53J+mhkVWAeWxVGI0lltJmWtEY
K6er8VqqWot3nqmWMXogrgRLggv/NbbooQIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAvmpxVY7ld/8DAjz6F6q05shjg8/4p6047bn6/m8yPy1RBsvIyvuD
uGnP/RzPEhzXQ9UJ5Ynmh2XJZgHoE9xbnfxL5BXHplJhMtADXKM9bWB11PU1Eioc
3+AXBB8QiNFBn2XI5UkO5hPhbb9mJpjA9Uhw8EdfqJP8QetVsI/xrCEbwEXe0xvi
fRLJbY08/Gp66KpQvy7g8w7VB8wlgePexW3pT13Ap6vuC+mQuJPyiHvSxjEKHgqe
Pji9NP3tJUFQjcECqcm0yV7/2d0t/pbCm+ZH1sadZspQCEPPrtbkQBlvHb4OLiIW
PGHKSMeRFvp3IWcmdJqXahxLCUS1Eh6MAQIDAQAB
-----END RSA PUBLIC KEY-----''',

        # Official Telegram Android production key (Handshake.cpp, DrKLO/Telegram):
        # fingerprint 0xd09d1d85de64fd85 — the ONLY production key used by the
        # official Android client for auth DH inner-data encryption.
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEA6LszBcC1LGzyr992NzE0ieY+BSaOW622Aa9Bd4ZHLl+TuFQ4lo4g
5nKaMBwK/BIb9xUfg0Q29/2mgIR6Zr9krM7HjuIcCzFvDtr+L0GQjae9H0pRB2OO
62cECs5HKhT5DZ98K33vmWiLowc621dQuwKWSQKjWf50XYFw42h21P2KXUGyp2y/
+aEyZ+uVgLLQbRA1dEjSDZ2iGRy12Mk5gpYc397aYp438fsJoHIgJ2lgMv5h7WY9
t6N/byY9Nw9p21Og3AoXSL2q/2IJ1WRUhebgAdGVMlV1fkuOQoEzR7EdpqtQD9Cs
5+bfo3Nhmcyvk5ftB0WkJ9z6bNZ7yxrP8wIDAQAB
-----END RSA PUBLIC KEY-----''',

):
    add_key(pub, old=False)


for pub in (
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAwVACPi9w23mF3tBkdZz+zwrzKOaaQdr01vAbU4E1pvkfj4sqDsm6
lyDONS789sVoD/xCS9Y0hkkC3gtL1tSfTlgCMOOul9lcixlEKzwKENj1Yz/s7daS
an9tqw3bfUV/nqgbhGX81v/+7RFAEd+RwFnK7a+XYl9sluzHRyVVaTTveB2GazTw
Efzk2DWgkBluml8OREmvfraX3bkHZJTKX4EQSjBbbdJ2ZXIsRrYOXfaA+xayEGB+
8hdlLmAjbCVfaigxX0CDqWeR1yFL9kwd9P0NsZRPsmoqVwMbMu7mStFai6aIhc3n
Slv8kg9qv1m6XHVQY3PnEw+QQtqSIXklHwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAxq7aeLAqJR20tkQQMfRn+ocfrtMlJsQ2Uksfs7Xcoo77jAid0bRt
ksiVmT2HEIJUlRxfABoPBV8wY9zRTUMaMA654pUX41mhyVN+XoerGxFvrs9dF1Ru
vCHbI02dM2ppPvyytvvMoefRoL5BTcpAihFgm5xCaakgsJ/tH5oVl74CdhQw8J5L
xI/K++KJBUyZ26Uba1632cOiq05JBUW0Z2vWIOk4BLysk7+U9z+SxynKiZR3/xdi
XvFKk01R3BHV+GUKM2RYazpS/P8v7eyKhAbKxOdRcFpHLlVwfjyM1VlDQrEZxsMp
NTLYXb6Sce1Uov0YtNx5wEowlREH1WOTlwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAsQZnSWVZNfClk29RcDTJQ76n8zZaiTGuUsi8sUhW8AS4PSbPKDm+
DyJgdHDWdIF3HBzl7DHeFrILuqTs0vfS7Pa2NW8nUBwiaYQmPtwEa4n7bTmBVGsB
1700/tz8wQWOLUlL2nMv+BPlDhxq4kmJCyJfgrIrHlX8sGPcPA4Y6Rwo0MSqYn3s
g1Pu5gOKlaT9HKmE6wn5Sut6IiBjWozrRQ6n5h2RXNtO7O2qCDqjgB2vBxhV7B+z
hRbLbCmW0tYMDsvPpX5M8fsO05svN+lKtCAuz1leFns8piZpptpSCFn7bWxiA9/f
x5x17D7pfah3Sy2pA+NDXyzSlGcKdaUmwQIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAwqjFW0pi4reKGbkc9pK83Eunwj/k0G8ZTioMMPbZmW99GivMibwa
xDM9RDWabEMyUtGoQC2ZcDeLWRK3W8jMP6dnEKAlvLkDLfC4fXYHzFO5KHEqF06i
qAqBdmI1iBGdQv/OQCBcbXIWCGDY2AsiqLhlGQfPOI7/vvKc188rTriocgUtoTUc
/n/sIUzkgwTqRyvWYynWARWzQg0I9olLBBC2q5RQJJlnYXZwyTL3y9tdb7zOHkks
WV9IMQmZmyZh/N7sMbGWQpt4NMchGpPGeJ2e5gHBjDnlIf2p1yZOYeUYrdbwcS0t
UiggS4UeE8TzIuXFQxw7fzEIlmhIaq3FnwIDAQAB
-----END RSA PUBLIC KEY-----''',
):
    add_key(pub, old=True)
