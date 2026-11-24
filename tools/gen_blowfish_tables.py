"""Generate Blowfish initial tables (hex digits of pi) for the C# installer and verify them
against pycryptodome with a pure-Python Blowfish."""
import os
import struct
import sys

from Crypto.Cipher import Blowfish as BF

N_WORDS = 18 + 4 * 256
BITS = N_WORDS * 32 + 64


def arctan_inv(x, one):
    total = term = one // x
    x2 = x * x
    n = 1
    sign = -1
    while term:
        term //= x2
        n += 2
        total += sign * (term // n)
        sign = -sign
    return total


def pi_words():
    one = 1 << (BITS + 32)
    pi = 4 * (4 * arctan_inv(5, one) - arctan_inv(239, one))
    frac = pi - (3 << (BITS + 32))
    frac >>= 32 + 64 - 64  # keep guard bits
    words = []
    total_bits = BITS + 32 - 32
    for i in range(N_WORDS):
        shift = BITS - 32 * (i + 1)
        words.append((frac >> (shift)) & 0xFFFFFFFF)
    return words


class PyBF:
    def __init__(self, key, P, S):
        self.P = list(P)
        self.S = [list(S[i * 256:(i + 1) * 256]) for i in range(4)]
        j = 0
        for i in range(18):
            d = 0
            for _ in range(4):
                d = (d << 8) | key[j % len(key)]
                j += 1
            self.P[i] ^= d
        l = r = 0
        for i in range(0, 18, 2):
            l, r = self.enc(l, r)
            self.P[i], self.P[i + 1] = l, r
        for s in range(4):
            for i in range(0, 256, 2):
                l, r = self.enc(l, r)
                self.S[s][i], self.S[s][i + 1] = l, r

    def F(self, x):
        S = self.S
        return ((((S[0][x >> 24] + S[1][(x >> 16) & 255]) & 0xFFFFFFFF) ^ S[2][(x >> 8) & 255]) + S[3][x & 255]) & 0xFFFFFFFF

    def enc(self, l, r):
        for i in range(16):
            l ^= self.P[i]
            r ^= self.F(l)
            l, r = r, l
        l, r = r, l
        r ^= self.P[16]
        l ^= self.P[17]
        return l, r


def main():
    w = pi_words()
    assert w[0] == 0x243F6A88 and w[1] == 0x85A308D3, hex(w[0])
    P, S = w[:18], w[18:]
    for key in (b"windmill", b"\x01\x02\x03\x04", b"ISLAND-test-key!"):
        ref = BF.new(key, BF.MODE_ECB).encrypt(b"\x01\x23\x45\x67\x89\xab\xcd\xef")
        b = PyBF(key, P, S)
        l, r = b.enc(0x01234567, 0x89ABCDEF)
        assert struct.pack(">II", l, r) == ref, key
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer", "BlowfishTables.cs")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("// Blowfish initial P-array and S-boxes (hexadecimal digits of pi), generated and\n")
        f.write("// verified against pycryptodome by tools/gen_blowfish_tables.py\n")
        f.write("namespace IslandKo {\ninternal static class BlowfishTables {\n")
        f.write("internal static readonly uint[] P = {\n" + ",".join("0x%08X" % x for x in P) + "};\n")
        f.write("internal static readonly uint[] S = {\n")
        for i in range(0, len(S), 8):
            f.write(",".join("0x%08X" % x for x in S[i:i + 8]) + ",\n")
        f.write("};\n}\n}\n")
    print("ok", out, len(P), len(S))


if __name__ == "__main__":
    main()
