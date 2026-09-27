#!/usr/bin/env python3
"""Independently verify a code_results/*.py circuit computes the official AES S-box.
Usage:  python3 verify_aes_sbox.py code_results/AES10_26H_82XORs_core01_sbp2_XXXXs.py
SELF-TEST: also run it on the authors' known-good 81-XOR file first. If it reports
that file as WRONG, this script has a bug; if RIGHT, the script is trustworthy."""
import sys, re

# ---------- official AES S-box, computed from FIPS-197 definition ----------
def gf_mult(a, b):
    p = 0
    for _ in range(8):
        if b & 1: p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi: a ^= 0x1b
        b >>= 1
    return p

def gf_inv(a):
    if a == 0: return 0
    r, base, e = 1, a, 254          # a^254 = a^-1 in GF(2^8)
    while e:
        if e & 1: r = gf_mult(r, base)
        base = gf_mult(base, base); e >>= 1
    return r

def affine(b):
    c = 0x63; out = 0
    for i in range(8):
        bit = 0
        for j in (i, (i+4)%8, (i+5)%8, (i+6)%8, (i+7)%8):
            bit ^= (b >> j) & 1
        bit ^= (c >> i) & 1
        out |= bit << i
    return out

AES_SBOX = [affine(gf_inv(x)) for x in range(256)]
assert AES_SBOX[0] == 0x63 and AES_SBOX[1] == 0x7C and AES_SBOX[2] == 0x77, "S-box self-check failed"

# ---------- simulate the circuit for one input ----------
def extract_gate_lines(filepath):
    content = open(filepath).read()
    marker = '################### Here is your code !! ###################'
    body = content.split(marker)[1]
    lines = []
    for ln in body.split('\n'):
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            lines.append(ln)
    return lines

def simulate(lines, input_byte, in_lsb, out_lsb):
    sizes = {'t': 0, 'r': 0, 'g': 0, 'y': 0}
    for ln in lines:
        m = re.match(r'([tryg])\[(\d+)\]', ln.split('=')[0].strip())
        if m and m.group(1) in sizes:
            sizes[m.group(1)] = max(sizes[m.group(1)], int(m.group(2)) + 1)
    ns = {'x': [0]*8, 't': [0]*sizes['t'], 'r': [0]*sizes['r'],
          'g': [0]*sizes['g'], 'y': [0]*sizes['y']}
    for i in range(8):
        ns['x'][i] = (input_byte >> (i if in_lsb else 7-i)) & 1
    for ln in lines:
        if re.match(r'^[a-z]+\s*=\s*\[', ln):      # skip array-init lines
            continue
        exec(ln, ns)
    out = 0
    for i in range(8):
        out |= (ns['y'][i] & 1) << (i if out_lsb else 7-i)
    return out

def main():
    filepath = sys.argv[1]
    lines = extract_gate_lines(filepath)
    # try all 4 bit-ordering conventions; a correct AES circuit matches one exactly
    for in_lsb in (True, False):
        for out_lsb in (True, False):
            ok = 0
            for inp in range(256):
                if simulate(lines, inp, in_lsb, out_lsb) == AES_SBOX[inp]:
                    ok += 1
                else:
                    break
            if ok == 256:
                print(f"PASS: {filepath}")
                print(f"      implements the AES S-box exactly (256/256) "
                      f"[input {'LSB' if in_lsb else 'MSB'}-first, output {'LSB' if out_lsb else 'MSB'}-first]")
                return
    print(f"FAIL: {filepath} does NOT match the AES S-box under any bit ordering")
    sys.exit(1)

if __name__ == '__main__':
    main()