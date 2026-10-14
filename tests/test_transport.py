"""Transport fidelity: the fork's obfuscated2 header and Abridged framing must
behave exactly like the official Android client's tgnet implementation.

Official reference: TMessagesProj/jni/tgnet/Connection.cpp (~line 527).
"""
import os
import sys
from pathlib import Path

import pytest

FORK = Path("/root/Telegram_Android")
sys.path.insert(0, str(FORK))

from telethon.crypto import AESModeCTR
from telethon.network.connection.connection import ObfuscatedConnection
from telethon.network.connection.tcpabridged import AbridgedPacketCodec
from telethon.network.connection.tcpobfuscated import ObfuscatedIO

REJECTED_PREFIXES = (
    b"HEAD", b"POST", b"GET ", b"OPTI",
    b"\xee\xee\xee\xee", b"\xdd\xdd\xdd\xdd", b"\x16\x03\x01\x02",
)


class FakeRW:
    def __init__(self):
        self.buf = b""

    async def readexactly(self, n):
        d, self.buf = self.buf[:n], self.buf[n:]
        return d

    def write(self, d):
        self.buf += d


def make_io():
    conn = ObfuscatedConnection.__new__(ObfuscatedConnection)
    conn.packet_codec = AbridgedPacketCodec
    conn._reader, conn._writer = FakeRW(), FakeRW()
    oio = ObfuscatedIO(conn)
    return conn, oio


class TestHeaderRejectList:
    def test_100_headers_conform(self):
        for _ in range(100):
            _, oio = make_io()
            h = bytes(oio.header)
            assert h[0] != 0xEF, "byte0 == 0xef"
            assert h[:4] not in REJECTED_PREFIXES, f"rejected prefix {h[:4]!r}"
            assert h[4:8] != b"\x00\x00\x00\x00", "val2 == 0"


class TestTagPlacement:
    def test_tag_recovers_as_efefefef_server_side(self):
        # Server derivation, mirroring Connection.cpp:527:
        # key = bytes[8:40], iv = bytes[40:56]; the server rebuilds the
        # keystream from the plaintext prefix and XORs wire[56:64].
        _, oio = make_io()
        header = bytes(oio.header)

        ks = AESModeCTR(bytes(header[8:40]), bytes(header[40:56]))
        ks64 = bytes(ks.encrypt(b"\x00" * 64))
        plain_56_64 = bytes(a ^ b for a, b in zip(header[56:64], ks64[56:64]))

        # Telegram writes the 4-byte protocol tag, then 4 bytes that stay
        # random unless a media/secret connection pins the dc id.
        assert plain_56_64[:4] == b"\xef\xef\xef\xef"

    def test_decrypt_direction_uses_reversed_material(self):
        _, oio = make_io()
        header = bytes(oio.header)
        # reversed slice derivation, as in tcpobfuscated.py init_header
        reversed_slice = header[55:7:-1]
        assert len(reversed_slice) == 48
        # decrypt material is the first 32+16 bytes of it - just structurally
        # assert oio._decrypt exists and differs from _encrypt state
        assert oio._decrypt is not oio._encrypt


class TestPayloadRoundtrip:
    def test_client_to_server_decode(self):
        conn, oio = make_io()
        header = bytes(oio.header)

        # rebuild the plaintext the encryptor consumed (tag already in place)
        ks = AESModeCTR(bytes(header[8:40]), bytes(header[40:56]))
        ks64 = bytes(ks.encrypt(b"\x00" * 64))
        plain_56_64 = bytes(a ^ b for a, b in zip(header[56:64], ks64[56:64]))
        plaintext_prefix = bytes(header[:56]) + plain_56_64

        payload = os.urandom(512)
        cipher = bytes(oio._encrypt.encrypt(payload))

        server = AESModeCTR(bytes(header[8:40]), bytes(header[40:56]))
        server.encrypt(plaintext_prefix)
        got = bytes(server.encrypt(cipher))
        assert got == payload

    def test_server_to_client_decode(self):
        _, oio = make_io()
        header = bytes(oio.header)
        # the server writes with the reversed material == the fork's _decrypt
        srv = AESModeCTR(bytes(header[55:23:-1]), bytes(header[23:7:-1]))
        payload = os.urandom(512)
        srv_ct = bytes(srv.encrypt(payload))
        assert bytes(oio._decrypt.decrypt(srv_ct)) == payload


class TestAbridgedFraming:
    def test_tag_is_ef(self):
        assert AbridgedPacketCodec.tag == b"\xef"
        assert AbridgedPacketCodec.obfuscate_tag == b"\xef\xef\xef\xef"

    def test_encode_adds_length_prefix(self):
        payload = b"\x00" * 16
        out = AbridgedPacketCodec.__new__(AbridgedPacketCodec).encode_packet(payload)
        assert len(out) == len(payload) + 1
        assert out[0] == len(payload) // 4


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
