#!/usr/bin/env python3
"""
Liveness checker for Extended-BP-Framework circuit output files. v3.

v3 adds: correct handling of duplicate-labeled gates. Previously (v2), if a
label like t[59] was emitted twice in a file (a real phenomenon caused by
make_Circuit's per-index emission loop paired with a per-value B_match dict),
the liveness graph tracked reachability by label *string*, so both physical
occurrences got waved through as "live" together, hiding the fact that only
the LAST occurrence is the one any downstream reference actually resolves to
(dict/variable overwrite semantics - last write wins). v3 tracks every
occurrence of every label separately and reports two independent categories
of dead gate:

  SHADOWED     - not the last-written definition of its label; permanently
                 overwritten and unreachable by construction, independent of
                 any graph analysis.
  UNREACHABLE  - is the last (authoritative) definition of its label, but
                 that label is never consumed, directly or transitively, by
                 any y[...] circuit output.

Pure static check: does not import or execute the target file, cannot alter
its behaviour. It only reads text and reports findings.

Usage:
    python3 liveness_check.py <circuit_file.py> [<circuit_file2.py> ...]

Typical use (run against every shipped result at once):
    python3 liveness_check.py code_results/*.py
"""

import sys
import re


LINE_RE = re.compile(r'^\s*([tgry]\[\d+\])\s*=\s*(.*)$')
OPERAND_RE = re.compile(r'[xtgry]\[\d+\]')
FILENAME_RE = re.compile(r'(\d+)NLs_(\d+)XORs')


def clean_rhs(raw):
    """Strip trailing junk from list-literal serialization (quotes/commas/etc)."""
    return raw.strip().rstrip(',"\'; \t')


def extract_assignments(text):
    """
    Returns:
        occ_by_label: dict[label] -> list of occurrence dicts, in file order
        order: labels in first-seen order (stable iteration / examples)
        examples: first few (lineno,label,rhs,op,operands) tuples, for display
    """
    occ_by_label = {}
    order = []
    examples = []

    for lineno, line in enumerate(text.splitlines(), 1):
        m = LINE_RE.match(line)
        if not m:
            continue
        label, raw_rhs = m.group(1), m.group(2)
        rhs = clean_rhs(raw_rhs)
        if not rhs:
            continue

        operands = OPERAND_RE.findall(rhs)
        if '&' in rhs:
            op = 'NAND' if re.search(r'\^\s*1\s*$', rhs) else 'AND'
        elif '|' in rhs:
            op = 'NOR' if re.search(r'\^\s*1\s*$', rhs) else 'OR'
        elif len(operands) == 2:
            op = 'XOR'
        elif len(operands) == 1:
            op = 'ALIAS'
        else:
            op = 'UNKNOWN'

        rec = {'lineno': lineno, 'rhs': rhs, 'op': op, 'operands': operands}
        if label not in occ_by_label:
            occ_by_label[label] = []
            order.append(label)
        occ_by_label[label].append(rec)

        if len(examples) < 8:
            examples.append((lineno, label, rhs, op, operands))

    return occ_by_label, order, examples


def is_real_gate(op):
    return op in ('XOR', 'AND', 'OR', 'NAND', 'NOR')


def check_liveness(occ_by_label):
    """Reachability using only the LAST occurrence of each label - this is
    the one any later reference actually resolves to, matching make_Circuit's
    dict-overwrite (last write wins) behaviour."""
    last = {label: occs[-1] for label, occs in occ_by_label.items()}
    roots = [label for label in last if label.startswith('y[')]

    live = set()
    stack = list(roots)
    while stack:
        lbl = stack.pop()
        if lbl in live:
            continue
        live.add(lbl)
        row = last.get(lbl)
        if row is None:
            continue
        for opd in row['operands']:
            if opd not in live:
                stack.append(opd)

    return roots, live


def summarize(path):
    print(f'\n=== {path} ===')
    try:
        with open(path) as f:
            text = f.read()
    except OSError as e:
        print(f'  [!] Could not open file: {e}')
        return

    occ_by_label, order, examples = extract_assignments(text)
    if not occ_by_label:
        print('  [!] No assignment lines matched at all. Paste the first '
              '~40 lines of this file so the parser can be fixed.')
        return

    print('  First few parsed lines (verify these look right):')
    for lineno, label, rhs, op, operands in examples:
        print(f'    L{lineno}: {label} = {rhs}   -> op={op}, operands={operands}')

    roots, live = check_liveness(occ_by_label)

    total_xor = 0
    total_nl = 0
    shadowed = []      # non-last occurrence of a duplicated label
    unreachable = []   # last occurrence, but label never live
    live_real = 0

    for label in order:
        occs = occ_by_label[label]
        for idx, rec in enumerate(occs):
            is_last = (idx == len(occs) - 1)
            if not is_real_gate(rec['op']):
                continue
            if rec['op'] == 'XOR':
                total_xor += 1
            else:
                total_nl += 1
            if not is_last:
                shadowed.append((label, rec))
            elif label not in live:
                unreachable.append((label, rec))
            else:
                live_real += 1

    total_real_gates = total_xor + total_nl
    dead_total = shadowed + unreachable

    print(f'\n  Total assignment lines parsed            : '
          f'{sum(len(v) for v in occ_by_label.values())}')
    print(f'  Circuit outputs (y[...] roots)            : {len(roots)}')
    print(f'  Classified as XOR                         : {total_xor}')
    print(f'  Classified as AND/OR/NAND/NOR              : {total_nl}')

    m = FILENAME_RE.search(path)
    if m:
        fn_nl, fn_xor = int(m.group(1)), int(m.group(2))
        ok_nl = 'OK' if fn_nl == total_nl else 'MISMATCH'
        ok_xor = 'OK' if fn_xor == total_xor else 'MISMATCH'
        print(f'  Filename cross-check: NLs={fn_nl} (parsed {total_nl}, {ok_nl}), '
              f'XORs={fn_xor} (parsed {total_xor}, {ok_xor})')

    print(f'  Live real gates (truly usable)             : {live_real}')
    print(f'  DEAD - shadowed by duplicate label          : {len(shadowed)}')
    print(f'  DEAD - unreachable from any output          : {len(unreachable)}')
    print(f'  DEAD - TOTAL                                : {len(dead_total)}')

    if shadowed:
        print('\n  --- Shadowed (label reused - earlier definition permanently overwritten) ---')
        seen_labels = set()
        for label, rec in shadowed:
            if label in seen_labels:
                continue
            seen_labels.add(label)
            all_occs = occ_by_label[label]
            print(f'    {label}: {len(all_occs)} definitions found in this file:')
            for i, o in enumerate(all_occs):
                marker = '(FINAL - kept)' if i == len(all_occs) - 1 else '(SHADOWED - dead)'
                print(f'      L{o["lineno"]}: {label} = {o["rhs"]}   {marker}')
            rhs_set = {o['rhs'] for o in all_occs}
            if len(rhs_set) == 1:
                print(f'      -> All definitions identical: pure duplicate, safe to drop.')
            else:
                print(f'      -> [!] Definitions DIFFER between occurrences - '
                      f'worth double-checking this is not a correctness issue, '
                      f'not just waste.')

    if unreachable:
        print('\n  --- Unreachable (never referenced by any output) ---')
        for label, rec in unreachable:
            print(f'    L{rec["lineno"]}: {label} = {rec["rhs"]}   [{rec["op"]}]')

    if dead_total:
        print(f'\n  => Total {len(dead_total)} gate(s) removable with ZERO '
              f'change to the circuit\'s function.')
    else:
        print('\n  => No dead/shadowed gates found in this file.')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for path in sys.argv[1:]:
        summarize(path)
    print()


if __name__ == '__main__':
    main()