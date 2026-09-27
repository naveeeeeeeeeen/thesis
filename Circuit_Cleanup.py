"""
Circuit_Cleanup.py - Phase 0: safe removal of redundant XOR gates.

Operates on the exact `Circuit` list-of-strings format produced by
make_Circuit() in Optimizer_BPD.py / Optimizer_RNBP.py, i.e. lines like:

    t[12]=t[5]^x[3]        (XOR gate)
    g[2]=r[4]&r[5]         (AND gate)
    g[2]=r[4]&r[5]^1       (NAND gate)
    g[2]=r[4]|r[5]         (OR gate)
    g[2]=r[4]|r[5]^1       (NOR gate)
    r[3]=t[7]               (alias / relabel)
    r[3]=t[7]^1              (alias + NOT)
    y[0]=t[9]^1               (final output, alias + NOT)

Removes two provably-safe categories of redundant t[...] (XOR) gate:

  SHADOWED     - a t[...] label whose definition is later overwritten by a
                 later line using the exact same label (the search built
                 the same value twice; only the later definition is ever
                 actually referenced downstream, since anything that reads
                 that label always resolves to whichever definition text
                 was written last).
  UNREACHABLE  - the sole/final definition of a t[...] label that no
                 y[...] output depends on, directly or transitively.

g[...] (AND/OR) lines and r[...]/y[...] alias lines are NEVER removed or
reordered, regardless of reachability - only redundant t[...] XOR gates are
ever candidates for removal. This guarantees AND gate count and AND depth
are always identical to what the search itself produced, which is required
for a fair, apples-to-apples benchmark comparison.

After removal, surviving t[...] labels are renumbered to a contiguous
0..(N-1) range (both at their definition and every place they are
referenced as an operand), so the result is a drop-in replacement for
Write_Circuit.Write_Circuit with no risk of an array-sizing mismatch.

By default, clean_circuit() automatically verifies functional equivalence
by brute-force simulation over every possible input before returning -
if verification ever fails, the ORIGINAL circuit is returned unchanged
and a warning is printed, so a bug here can never silently corrupt a
benchmark result.
"""

import re


LINE_RE = re.compile(r'^\s*([tgry]\[\d+\])\s*=\s*(.*)$')
TOKEN_RE = re.compile(r'[xtgry]\[\d+\]')
TRAILING_NOT_RE = re.compile(r'\^\s*1\s*$')


def _parse_line(line):
    """Parse one Circuit line into (label, op, operands, has_not)."""
    m = LINE_RE.match(line.strip())
    if not m:
        raise ValueError(f'Unparseable circuit line: {line!r}')
    label, rhs = m.group(1), m.group(2).strip()
    operands = TOKEN_RE.findall(rhs)
    has_not = bool(TRAILING_NOT_RE.search(rhs))
    if '&' in rhs:
        op = 'NAND' if has_not else 'AND'
    elif '|' in rhs:
        op = 'NOR' if has_not else 'OR'
    elif len(operands) == 2:
        op = 'XOR'
    elif len(operands) == 1:
        op = 'ALIAS'
    else:
        raise ValueError(f'Could not classify circuit line: {line!r}')
    return label, op, operands, has_not


def _parse_circuit(Circuit):
    """Parse every line once. Reused across many simulate calls so
    verify_equivalence doesn't re-parse on every one of the 2**n inputs."""
    return [_parse_line(line) for line in Circuit]


def _serialize_line(label, op, operands, has_not):
    if op == 'XOR':
        return f'{label}={operands[0]}^{operands[1]}'
    if op == 'AND':
        return f'{label}={operands[0]}&{operands[1]}'
    if op == 'NAND':
        return f'{label}={operands[0]}&{operands[1]}^1'
    if op == 'OR':
        return f'{label}={operands[0]}|{operands[1]}'
    if op == 'NOR':
        return f'{label}={operands[0]}|{operands[1]}^1'
    if op == 'ALIAS':
        suffix = '^1' if has_not else ''
        return f'{label}={operands[0]}{suffix}'
    raise ValueError(f'Unknown op {op!r}')


def _simulate_parsed(parsed_lines, n, m, x_bits):
    """Fast path: run an already-parsed circuit for one input assignment."""
    env = {}
    for i in range(n):
        env[f'x[{i}]'] = x_bits[i]
    for label, op, operands, has_not in parsed_lines:
        if op == 'XOR':
            val = env[operands[0]] ^ env[operands[1]]
        elif op == 'AND':
            val = env[operands[0]] & env[operands[1]]
        elif op == 'NAND':
            val = (env[operands[0]] & env[operands[1]]) ^ 1
        elif op == 'OR':
            val = env[operands[0]] | env[operands[1]]
        elif op == 'NOR':
            val = (env[operands[0]] | env[operands[1]]) ^ 1
        elif op == 'ALIAS':
            val = env[operands[0]] ^ (1 if has_not else 0)
        env[label] = val
    return [env[f'y[{i}]'] for i in range(m)]


def simulate_circuit(Circuit, n, m, x_bits):
    """Interpret a raw Circuit list for one concrete input assignment.

    Convenience wrapper for one-off use. If you need to simulate the same
    circuit for many inputs (as verify_equivalence does), parse once with
    _parse_circuit() and call _simulate_parsed() directly instead - this
    wrapper re-parses every call, which is fine for a single lookup but
    wasteful in a loop over 2**n inputs.
    """
    return _simulate_parsed(_parse_circuit(Circuit), n, m, x_bits)


def verify_equivalence(circuit_a, circuit_b, n, m):
    """Brute-force check that two Circuits compute the identical function
    over every possible n-bit input. Returns (True, None) or
    (False, failing_input).

    Each circuit is parsed exactly once, then reused across all 2**n
    inputs - parsing (regex-based) is the expensive part per line, so this
    matters a lot at n=16 (65536 inputs): re-parsing per input turned a
    ~150-350 line circuit's verification into tens of seconds; parsing
    once brings it down to a fraction of a second.
    """
    parsed_a = _parse_circuit(circuit_a)
    parsed_b = _parse_circuit(circuit_b)
    for x_int in range(1 << n):
        x_bits = [(x_int >> i) & 1 for i in range(n)]
        try:
            out_a = _simulate_parsed(parsed_a, n, m, x_bits)
            out_b = _simulate_parsed(parsed_b, n, m, x_bits)
        except (KeyError, IndexError):
            # Circuit has structural issues (forward references, missing
            # definitions). Treat as verification failure rather than crashing.
            return False, x_bits
        if out_a != out_b:
            return False, x_bits
    return True, None


def clean_circuit(Circuit, n=None, m=None, verify=True, verbose=True):
    """
    Remove shadowed and unreachable t[...] (XOR) gates from Circuit.

    n, m are required if verify=True (needed to brute-force simulate).

    Returns (new_Circuit, stats). stats always contains at least:
        original_lines, shadowed_removed, unreachable_removed,
        total_removed, final_lines, original_xor_count, final_xor_count,
        verified (True/False/None - None if verify=False).
    If verification fails, new_Circuit == Circuit (unchanged) and
    stats['verified'] is False - callers should treat this as "cleanup
    aborted, using original circuit" rather than trusting final_xor_count.
    """
    parsed = [_parse_line(line) for line in Circuit]

    # --- Pass 1: shadowed = any t[...] line whose label is defined again
    #             later in the list ---
    last_index_of_label = {}
    for idx, (label, op, operands, has_not) in enumerate(parsed):
        last_index_of_label[label] = idx

    shadowed_indices = {
        idx for idx, (label, op, operands, has_not) in enumerate(parsed)
        if op == 'XOR' and last_index_of_label[label] != idx
    }

    # --- Pass 2: backward reachability from y[...] roots, using only the
    #             authoritative (last) definition of each label ---
    authoritative = {
        label: (op, operands)
        for idx, (label, op, operands, has_not) in enumerate(parsed)
        if idx not in shadowed_indices
        for label, op, operands in [(label, op, operands)]
    }
    # (rebuild cleanly to avoid shadowing confusion in the comprehension)
    authoritative = {}
    for idx, (label, op, operands, has_not) in enumerate(parsed):
        if idx in shadowed_indices:
            continue
        authoritative[label] = (op, operands)

    live = set()
    stack = [label for label in authoritative if label.startswith('y[')]
    while stack:
        lbl = stack.pop()
        if lbl in live:
            continue
        live.add(lbl)
        row = authoritative.get(lbl)
        if row is None:
            continue
        _, operands = row
        for opd in operands:
            if opd not in live:
                stack.append(opd)

    unreachable_indices = {
        idx for idx, (label, op, operands, has_not) in enumerate(parsed)
        if idx not in shadowed_indices and op == 'XOR' and label not in live
    }

    drop = shadowed_indices | unreachable_indices
    survivors = [row for idx, row in enumerate(parsed) if idx not in drop]

    # --- Pass 3: renumber surviving t[...] labels to close any gaps ---
    rename = {}
    next_t = 0
    for label, op, operands, has_not in survivors:
        if label.startswith('t[') and label not in rename:
            rename[label] = f't[{next_t}]'
            next_t += 1

    new_Circuit = []
    for label, op, operands, has_not in survivors:
        new_label = rename.get(label, label)
        new_operands = [rename.get(o, o) for o in operands]
        new_Circuit.append(_serialize_line(new_label, op, new_operands, has_not))

    original_xor = sum(1 for _, op, _, _ in parsed if op == 'XOR')
    final_xor = sum(1 for _, op, _, _ in survivors if op == 'XOR')

    stats = {
        'original_lines': len(Circuit),
        'shadowed_removed': len(shadowed_indices),
        'unreachable_removed': len(unreachable_indices),
        'total_removed': len(drop),
        'final_lines': len(new_Circuit),
        'original_xor_count': original_xor,
        'final_xor_count': final_xor,
        'verified': None,
    }

    if verify:
        if n is None or m is None:
            raise ValueError('verify=True requires n and m to be provided')
        ok, failing_input = verify_equivalence(Circuit, new_Circuit, n, m)
        stats['verified'] = ok
        if not ok:
            if verbose:
                print(f'[Circuit_Cleanup] !! VERIFICATION FAILED on input '
                      f'{failing_input} - reverting to original circuit, '
                      f'no gates removed. This should never happen; please '
                      f'report the circuit that triggered it.')
            return Circuit, stats

    if verbose and stats['total_removed'] > 0:
        print(f"[Circuit_Cleanup] removed {stats['shadowed_removed']} shadowed + "
              f"{stats['unreachable_removed']} unreachable XOR gate(s) "
              f"({stats['original_xor_count']} -> {stats['final_xor_count']} XORs)"
              + (' [verified]' if stats['verified'] else ''))
    elif verbose:
        print(f"[Circuit_Cleanup] no dead gates found "
              f"({stats['original_xor_count']} XORs)"
              + (' [verified]' if stats['verified'] else ''))

    return new_Circuit, stats