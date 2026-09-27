import sys, re

MARKER = '################### Here is your code !! ###################'

def extract_body(path):
    with open(path) as f:
        content = f.read()
    parts = content.split(MARKER)
    return parts[1]

def parse_lines(body):
    out = []
    for ln in body.split('\n'):
        ln = ln.strip()
        if not ln or '=' not in ln:
            continue
        if re.match(r'^[tr]\s*=\s*\[0\]', ln):   # skip array-sizing lines
            continue
        label, rhs = ln.split('=', 1)
        out.append((label.strip(), rhs.strip()))
    return out

def main():
    path = sys.argv[1]
    body = extract_body(path)
    lines = parse_lines(body)

    # 1) duplicate label definitions
    first_def = {}
    dups = []
    for i, (label, rhs) in enumerate(lines):
        if label in first_def:
            dups.append((label, first_def[label], i))
        else:
            first_def[label] = i
    print(f"Total gate lines: {len(lines)}")
    if dups:
        print(f"\n!! {len(dups)} DUPLICATE label definitions (same label assigned twice):")
        for label, a, b in dups:
            print(f"   {label}: line {a} and line {b}")
    else:
        print("\nNo duplicate label definitions.")

    # 2) forward references: a t[] used before it is defined
    defined = set()
    fwd = []
    for i, (label, rhs) in enumerate(lines):
        for ref in re.findall(r't\[\d+\]', rhs):
            if ref not in defined and ref in first_def and first_def[ref] > i:
                fwd.append((i, label, ref, first_def[ref]))
        defined.add(label)
    if fwd:
        print(f"\n!! {len(fwd)} FORWARD references (t[] used BEFORE it is defined):")
        for i, label, ref, defidx in fwd[:25]:
            print(f"   line {i} ({label}) reads {ref}, but {ref} is only defined later at line {defidx}")
    else:
        print("\nNo forward references among t[] labels.")

    # 3) simulate and compare against the authors' known-good 81-XOR circuit
    ref = sys.argv[2] if len(sys.argv) > 2 else 'code_results/AES10_BPD_26D_6AD_32NLs_81XORs.py'
    ref_body = extract_body(ref)
    def sim(bd, xv):
        ns = {'x': [(xv >> i) & 1 for i in range(8)], 'y': [0]*8, 'g': [0]*64}
        exec(bd, ns)
        v = 0
        for i in range(8):
            v |= (ns['y'][i] & 1) << i
        return v
    mism = []
    for xv in range(256):
        a, b = sim(body, xv), sim(ref_body, xv)
        if a != b:
            mism.append((xv, a, b))
    if mism:
        print(f"\n!! Circuit differs from the known-good reference on {len(mism)}/256 inputs.")
        for xv, a, b in mism[:5]:
            print(f"   input={xv:#04x}: this circuit gives {a:#04x}, correct is {b:#04x}")
    else:
        print("\nCircuit MATCHES the known-good reference on all 256 inputs "
              "(verify_aes_sbox.py may itself be at fault).")

if __name__ == '__main__':
    main()