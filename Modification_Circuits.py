import math
import random
import copy
import time


def _xor_count(XORs):
    """Estimated XOR gate count = sum over every XOR expression of
    (number of operands - 1). This is the metric the paper's targeted
    transformation selection minimizes (Section 3.2)."""
    return sum([len(XORs[r]) - 1 for r in XORs])


def _applicable_transforms(gate_type):
    """Transformation functions valid for a gate of the given CURRENT type.
    Each has signature (XORs, NLs, NOTs, i) -> (new_XORs, new_NLs, new_NOTs).
    Matching transform to current type is essential: e.g. AND_to_OR assumes
    the gate is currently AND."""
    if gate_type == '&':
        return [AND_to_NAND, AND_to_OR, AND_to_NOR, AND_NAND_ver2, AND_NAND_ver3]
    elif gate_type == '!&':
        return [NAND_to_AND, NAND_to_OR, NAND_to_NOR, AND_NAND_ver2, AND_NAND_ver3]
    elif gate_type == '|':
        return [OR_to_AND, OR_to_NAND, OR_to_NOR, OR_NOR_ver2, OR_NOR_ver3]
    elif gate_type == '!|':
        return [NOR_to_AND, NOR_to_NAND, NOR_to_OR, OR_NOR_ver2, OR_NOR_ver3]
    return []


def Modify_circuits(n, m, origin_XORs, origin_NLs, origin_NOTs, mode='modified'):
    """Pre-processing circuit transformation (paper Section 3.2).

    REPLACES the previous unbounded random rejection-sampling loop, which
    could run for hours / effectively never terminate on 32-gate circuits
    like AES10 (the chance of a random modification satisfying both
    depth<=origin_depth and XORnum<=1.15*origin is ~0 at that scale).

    This version implements the paper's TARGETED strategy:
      "we selected the transformation for each nonlinear gate that results
       in the greatest reduction of XOR gates. If transformations have equal
       rankings, we choose one at random ... This process is repeated until
       no more transformations reduce the number of XOR gates."

    Termination guarantee: each accepted step strictly decreases the
    non-negative integer XOR estimate, so at most (initial estimate)
    iterations occur; in practice it converges in a few passes (seconds).
    """
    origin_depth = estimate_depth(n, m, origin_XORs, origin_NLs, origin_NOTs)
    XORs = copy.deepcopy(origin_XORs)
    NLs = origin_NLs[:]
    NOTs = origin_NOTs[:]

    if mode == 'modified':
        current_XORnum = _xor_count(XORs)
        while True:
            # best_XORnum starts at the current count; a candidate must be
            # STRICTLY lower to be accepted (guarantees monotone progress).
            best_XORnum = current_XORnum
            best_candidates = []  # all transforms tied at best_XORnum
            for i in range(len(NLs)):
                for transform in _applicable_transforms(NLs[i]):
                    try:
                        cand_XORs, cand_NLs, cand_NOTs = transform(XORs, NLs, NOTs, i)
                        cand_depth = estimate_depth(n, m, cand_XORs, cand_NLs, cand_NOTs)
                    except Exception:
                        # Skip any transformation producing a degenerate/invalid
                        # structure (e.g. an emptied XOR expression -> log2(0)).
                        continue
                    # Depth guard (same intent as the original code): do not
                    # accept a transformation that worsens the depth situation.
                    if cand_depth > origin_depth:
                        continue
                    cand_XORnum = _xor_count(cand_XORs)
                    if cand_XORnum < current_XORnum:      # only real improvements
                        if cand_XORnum < best_XORnum:
                            best_XORnum = cand_XORnum
                            best_candidates = [(cand_XORs, cand_NLs, cand_NOTs)]
                        elif cand_XORnum == best_XORnum:
                            best_candidates.append((cand_XORs, cand_NLs, cand_NOTs))
            if not best_candidates:
                break  # no transformation reduces the XOR count -> converged
            # Paper: "If transformations have equal rankings, we choose one
            # at random". Random tie-break also gives per-core diversity.
            XORs, NLs, NOTs = random.choice(best_candidates)
            current_XORnum = best_XORnum
        depth = estimate_depth(n, m, XORs, NLs, NOTs)
    else:
        depth = origin_depth

    return XORs, NLs, NOTs, depth


def estimate_depth(n, m, XORs, NLs, NOTs):
    D = {f'x[{_}]': 0 for _ in range(n)}
    k = len(NLs)
    for i in range(k):
        D[f'r[{2*i}]'] = math.ceil(math.log2(sum([1 << D[X]
                                                  for X in XORs[f'r[{2*i}]']])))
        D[f'r[{2*i+1}]'] = math.ceil(math.log2(sum([1 << D[X]
                                                    for X in XORs[f'r[{2*i+1}]']])))
        D[f'g[{i}]'] = max(D[f'r[{2*i}]'], D[f'r[{2*i+1}]']) + 1
    for i in range(m):
        D[f'y[{i}]'] = math.ceil(
            math.log2(sum([1 << D[X] for X in XORs[f'y[{i}]']]))
        )
    d = max([D[f'y[{i}]'] for i in range(m)])
    return d


def AND_to_OR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    new_NLs[i] = '|'
    return new_XORs, new_NLs, new_NOTs


def AND_to_NAND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '!&'
    return new_XORs, new_NLs, new_NOTs


def AND_to_NOR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '!|'
    return new_XORs, new_NLs, new_NOTs


def OR_to_AND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    new_NLs[i] = '&'
    return new_XORs, new_NLs, new_NOTs


def OR_to_NAND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '!&'
    return new_XORs, new_NLs, new_NOTs


def OR_to_NOR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '!|'
    return new_XORs, new_NLs, new_NOTs


def NAND_to_AND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '&'
    return new_XORs, new_NLs, new_NOTs


def NAND_to_OR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '|'
    return new_XORs, new_NLs, new_NOTs


def NAND_to_NOR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    new_NLs[i] = '!|'
    return new_XORs, new_NLs, new_NOTs


def NOR_to_AND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '&'
    return new_XORs, new_NLs, new_NOTs


def NOR_to_NAND(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if (f'r[{2*i}]' in new_NOTs) ^ (f'r[{2*i+1}]' in new_NOTs):
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    new_NLs[i] = '!&'
    return new_XORs, new_NLs, new_NOTs


def NOR_to_OR(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            if r in new_NOTs:
                new_NOTs.remove(r)
            else:
                new_NOTs.append(r)
    new_NLs[i] = '|'
    return new_XORs, new_NLs, new_NOTs


def AND_NAND_ver2(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for x in new_XORs[f'r[{2*i}]']:
        if x in new_XORs[f'r[{2*i+1}]']:
            new_XORs[f'r[{2*i+1}]'].remove(x)
        else:
            new_XORs[f'r[{2*i+1}]'].append(x)
    if f'r[{2*i}]' in new_NOTs:
        if f'r[{2*i+1}]' in new_NOTs:
            new_NOTs.remove(f'r[{2*i+1}]')
        else:
            new_NOTs.append(f'r[{2*i+1}]')
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if f'r[{2*i}]' in new_NOTs:
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    return new_XORs, new_NLs, new_NOTs


def AND_NAND_ver3(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for x in new_XORs[f'r[{2*i+1}]']:
        if x in new_XORs[f'r[{2*i}]']:
            new_XORs[f'r[{2*i}]'].remove(x)
        else:
            new_XORs[f'r[{2*i}]'].append(x)
    if f'r[{2*i+1}]' in new_NOTs:
        if f'r[{2*i}]' in new_NOTs:
            new_NOTs.remove(f'r[{2*i}]')
        else:
            new_NOTs.append(f'r[{2*i}]')
    for r in new_XORs:
        if f'g[{i}]' in new_XORs[r]:
            for x in new_XORs[f'r[{2*i+1}]']:
                if x in new_XORs[r]:
                    new_XORs[r].remove(x)
                else:
                    new_XORs[r].append(x)
            if f'r[{2*i+1}]' in new_NOTs:
                if r in new_NOTs:
                    new_NOTs.remove(r)
                else:
                    new_NOTs.append(r)
    return new_XORs, new_NLs, new_NOTs


def OR_NOR_ver2(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for x in new_XORs[f'r[{2*i}]']:
        if x in new_XORs[f'r[{2*i+1}]']:
            new_XORs[f'r[{2*i+1}]'].remove(x)
        else:
            new_XORs[f'r[{2*i+1}]'].append(x)
    return new_XORs, new_NLs, new_NOTs


def OR_NOR_ver3(XORs, NLs, NOTs, i):
    new_XORs = copy.deepcopy(XORs)
    new_NLs = NLs[:]
    new_NOTs = NOTs[:]
    for x in new_XORs[f'r[{2*i+1}]']:
        if x in new_XORs[f'r[{2*i}]']:
            new_XORs[f'r[{2*i}]'].remove(x)
        else:
            new_XORs[f'r[{2*i}]'].append(x)
    return new_XORs, new_NLs, new_NOTs