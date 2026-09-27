"""
Selection_Strategy.py - Phase 1: isolated candidate-selection ("Strategy T")
logic, shared by Optimizer_BPD.py and Optimizer_RNBP.py.

This module deliberately does ONE job: given a dict of already-validated
candidates (WD_Dist: candidate_value -> resulting Dist vector if that
candidate were chosen), pick which one to actually add to the search's
base set S.

It does NOT perform any depth-budget filtering itself. By the time
WD_Dist reaches this module, the caller (Optimizer_BPD's make_WD + its
update_distance_for_new_pair filtering, or Optimizer_RNBP's equivalent)
has ALREADY excluded any candidate that would violate the depth limit
(BPD's H) or that doesn't change any target's distance. This module's
only job is choosing among candidates that are already known-valid -
this is a deliberate design choice so that "preserve depth budgeting
exactly" (per the task) is trivially true: this module cannot touch
depth budgeting because it never sees anything depth-related at all.

Two selection modes:

  sbp_pool_size=None (default):
    Exact reproduction of the original published BP/RNBP/BPD Strategy T:
    minimize the Sum of the resulting Dist vector, then among ties
    maximize the Euclidean Norm, then choose uniformly at random among
    whatever survives both filters. Byte-for-byte equivalent to the
    original inline code in both optimizers (verified by construction:
    the ranking key and tie-handling below are a direct transcription of
    the original "Minimize Sum of Dist" / "Maximize Euclidean norm of
    Dist" / "Random" blocks).

  sbp_pool_size=<int> (SBP mode):
    "Superior Boyar-Peralta" (SBP) style bounded-pool selection, from:
      Kurt Pehlivanoglu, M. & Demir, M.A. (2024). "Optimizing
      implementations of linear layers using two and higher input XOR
      gates." PeerJ Computer Science, 10:e1820. Algorithm 1 ("SBP").

    Mechanism: instead of collecting the *entire* set of candidates tied
    for best rank (as the original strategy does), maintain a pool
    capped at `sbp_pool_size` entries. A strictly-better candidate found
    while sweeping resets the pool to just that candidate; a candidate
    exactly tied with the current best is appended if there's room, or
    overwrites a slot via a circular counter once the pool is full
    (matching the paper's description of a capped `allElement` array
    with a wrapping `counter`). The final choice is uniform-random over
    whatever is in the pool once the sweep finishes.

    IMPORTANT ASSUMPTION, stated explicitly because the source material
    justifies flagging it: the paper's own Algorithm 1 pseudocode (as
    extracted from the published PDF/HTML) does not clearly show where
    `minDistance` itself gets updated, so the exact reset-vs-wrap-only
    semantics are ambiguous from the pseudocode alone. The paper's prose
    states unambiguously: "If this [pool] size equals the maximum count
    of selectable elements, SBP will yield outcomes equal to those of
    other optimization algorithms." The reset-on-strictly-better rule
    used below is the interpretation that provably satisfies this stated
    guarantee for every pool size, in every sweep order (a large enough
    sbp_pool_size makes _select_sbp's output distribution identical to
    _select_original's, since a global sweep-order-independent reset
    means only ties with the TRUE final best ever survive to the final
    pool). A "never reset, only wrap" reading is also a plausible
    transcription of the raw pseudocode, but does not satisfy the
    stated guarantee in every case (a late-arriving strictly-better
    candidate could leave stale, worse candidates in the pool if not
    enough further ties arrive afterward to cycle them out), so it was
    not used here.

    The paper's own algorithm sweeps raw index pairs (i, j) into the base
    directly. This codebase has already collapsed pairs down to unique
    resulting values (WD_Dist's keys) before selection is ever reached,
    so this implementation sweeps over those unique candidates instead -
    a direct, faithful adaptation to the existing WD_Dist structure, not
    a change in spirit from the paper's own pair sweep.
"""

import random


def _rank_key(dist_vector):
    """(sum, -norm): a single sortable key such that a SMALLER key is a
    BETTER candidate, matching the original 'minimize Sum, then among
    ties maximize Euclidean Norm' rule. 999 entries (unreachable targets)
    are excluded from both, exactly as the original inline code does."""
    s = sum(v for v in dist_vector if v != 999)
    norm = sum(v * v for v in dist_vector if v != 999)
    return (s, -norm)


def _compute_original_candidates(WD_Dist):
    """Builds the exact tie group the original Strategy T would collect.
    Split out for the same testability reason as _compute_sbp_pool."""
    best_key = None
    best_candidates = []
    for w, dist_vector in WD_Dist.items():
        key = _rank_key(dist_vector)
        if best_key is None or key < best_key:
            best_key = key
            best_candidates = [w]
        elif key == best_key:
            best_candidates.append(w)
    return best_candidates


def _select_original(WD_Dist):
    """Exact reproduction of the original Sum-then-Norm-then-random
    Strategy T used by BP/RNBP/BPD."""
    return random.choice(_compute_original_candidates(WD_Dist))


def _compute_sbp_pool(WD_Dist, pool_size):
    """Builds the SBP candidate pool (see module docstring for semantics).
    Split out from _select_sbp so tests can inspect the resulting pool
    directly without needing to mock randomness."""
    if pool_size < 1:
        raise ValueError('sbp_pool_size must be >= 1')

    pool = []
    best_key = None
    counter = 0  # next slot index to write into once pool is full, wraps mod pool_size

    for w, dist_vector in WD_Dist.items():
        key = _rank_key(dist_vector)
        if best_key is None or key < best_key:
            # Strictly better candidate found: reset the pool. This is
            # what makes a large-enough pool_size provably reduce to
            # _select_original's behavior (see module docstring).
            best_key = key
            pool = [w]
            counter = 1 % pool_size
        elif key == best_key:
            if len(pool) < pool_size:
                pool.append(w)
                counter = len(pool) % pool_size
            else:
                pool[counter] = w
                counter = (counter + 1) % pool_size
        # else: strictly worse than current best - ignored entirely.

    return pool


def _select_sbp(WD_Dist, pool_size):
    """SBP-style bounded pool selection. See module docstring for the
    exact semantics and the assumption made about reset-vs-wrap-only
    behavior."""
    pool = _compute_sbp_pool(WD_Dist, pool_size)
    return random.choice(pool)


def select_candidate(WD_Dist, sbp_pool_size=None):
    """
    WD_Dist: dict[candidate_value -> Dist_vector_if_this_candidate_chosen],
             already fully filtered for depth-validity by the caller.
    sbp_pool_size: None for original behavior, or an int >= 1 for SBP mode.

    Returns the chosen candidate value.
    """
    if not WD_Dist:
        raise ValueError(
            'select_candidate called with an empty WD_Dist - this means '
            'the caller found no valid candidates at all, which should '
            'have been handled before reaching the selection step.')

    if sbp_pool_size is None:
        return _select_original(WD_Dist)
    return _select_sbp(WD_Dist, sbp_pool_size)
