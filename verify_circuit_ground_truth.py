#!/usr/bin/env python3
"""
Definitive AES S-box circuit verification. Executes the circuit's gate-level
code EXACTLY as Python would (so AND/OR/NAND/NOR/XOR/NOT and operator
precedence are all handled correctly), for all 256 inputs, and compares to the
mathematically-defined AES S-box (inverse in GF(2^8) + affine transform).

Usage:
    python3 verify_circuit_ground_truth.py code_results/<file>.py

CONTROL FIRST: run on the authors' known-good file. It MUST say PASS,
otherwise this script itself is broken and its verdicts mean nothing.
"""
import sys
import textwrap

MARKER = '################### Here is your code !! ###################'

def build_true_aes_sbox():
    def gf_mult(a, b):
        p = 0
        for _ in range(8):
            if b & 1:
                p ^= a
            hi = a & 0x80
            a = (a << 1) & 0xff
            if hi:
                a ^= 0x1b
            b >>= 1
        return p
    def gf_pow(a, e):
        r, base = 1, a
        while e:
            if e & 1:
                r = gf_mult(r, base)
            base = gf_mult(base, base)
            e >>= 1
        return r
    def gf_inv(a):
        return 0 if a == 0 else gf_pow(a, 254)   # a^254 = a^-1 in GF(2^8)
    def affine(b):
        c = 0x63
        out = 0
        for i in range(8):
            bit = 0
            for rot in (0, 4, 5, 6, 7):
                bit ^= (b >> ((i + rot) % 8)) & 1
            bit ^= (c >> i) & 1
            out |= bit << i
        return out
    return [affine(gf_inv(x)) for x in range(256)]

def load_circuit_body(path):
    with open(path) as f:
        content = f.read()
    parts = content.split(MARKER)
    if len(parts) < 3:
        raise ValueError('circuit markers not found in file')
    return textwrap.dedent(parts[1])

def simulate(body, input_byte, in_lsb, out_lsb):
    x = [0] * 8
    for i in range(8):
        x[i] = (input_byte >> (i if in_lsb else 7 - i)) & 1
    ns = {'x': x, 'y': [0] * 8, 'g': [0] * 64}
    exec(body, ns)
    y = ns['y']
    out = 0
    for i in range(8):
        out |= (y[i] & 1) << (i if out_lsb else 7 - i)
    return out

def main():
    path = sys.argv[1]
    true_sbox = build_true_aes_sbox()
    assert true_sbox[0] == 0x63 and true_sbox[1] == 0x7C and true_sbox[255] == 0x16, \
        'internal AES S-box self-check failed'
    body = load_circuit_body(path)

    try:
        for in_lsb in (True, False):
            for out_lsb in (True, False):
                bad = None
                for inp in range(256):
                    got = simulate(body, inp, in_lsb, out_lsb)
                    if got != true_sbox[inp]:
                        bad = (inp, got, true_sbox[inp])
                        break
                if bad is None:
                    print(f'PASS: {path}')
                    print(f'      implements AES S-box exactly (256/256) '
                          f'[input {"LSB" if in_lsb else "MSB"}-first, '
                          f'output {"LSB" if out_lsb else "MSB"}-first]')
                    return
        print(f'FAIL: {path} does NOT match the AES S-box under any bit ordering')
        print(f'      example mismatch: input={bad[0]}, '
              f'got={bad[1]:#04x}, expected={bad[2]:#04x}')
        sys.exit(1)
    except Exception as e:
        print(f'ERROR during simulation: {type(e).__name__}: {e}')
        sys.exit(2)

if __name__ == '__main__':
    main()