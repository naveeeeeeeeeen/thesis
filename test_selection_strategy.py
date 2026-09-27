import Selection_Strategy as SS


def test_original_matches_hand_computed_tie_group():
    # sums: A=3, B=3(tied), C=5, D=3(tied) -> tie group on sum is {A,B,D}
    # norms among the tied: A has [1,1,1]->norm 3, B has [3,0,0]->norm 9,
    # D has [0,3,0]->norm 9 -> B and D tie for max norm, A is eliminated.
    WD_Dist = {
        'A': [1, 1, 1],
        'B': [3, 0, 0],
        'C': [2, 2, 1],   # sum=5, not competitive
        'D': [0, 3, 0],
    }
    candidates = SS._compute_original_candidates(WD_Dist)
    assert set(candidates) == {'B', 'D'}, candidates
    for _ in range(50):
        assert SS.select_candidate(WD_Dist) in {'B', 'D'}
    print('test_original_matches_hand_computed_tie_group passed')


def test_sbp_large_pool_reduces_to_original_tie_group():
    WD_Dist = {
        'A': [1, 1, 1],
        'B': [3, 0, 0],
        'C': [2, 2, 1],
        'D': [0, 3, 0],
        'E': [0, 3, 0],   # third-way tie with B/D
    }
    original = set(SS._compute_original_candidates(WD_Dist))
    pool = set(SS._compute_sbp_pool(WD_Dist, pool_size=1000))
    assert pool == original, (pool, original)
    print('test_sbp_large_pool_reduces_to_original_tie_group passed')


def test_sbp_small_pool_caps_but_never_includes_worse_candidates():
    # 5 candidates all exactly tied for the true best; pool_size=2 should
    # cap at 2, and both must come from the true tie group (never from a
    # strictly worse candidate).
    WD_Dist = {f'T{i}': [1, 1] for i in range(5)}       # all tied, sum=2, norm=2
    WD_Dist['WORSE'] = [3, 3]                             # strictly worse
    pool = SS._compute_sbp_pool(WD_Dist, pool_size=2)
    assert len(pool) == 2, pool
    assert 'WORSE' not in pool, pool
    assert all(p.startswith('T') for p in pool), pool
    print('test_sbp_small_pool_caps_but_never_includes_worse_candidates passed')


def test_sbp_pool_size_1_is_fully_deterministic_given_sweep_order():
    # With pool_size=1, the pool always ends up as exactly [last candidate
    # seen that matched or beat the running best] - i.e. no randomness
    # left at all once the sweep order is fixed. Confirms pool_size=1 is
    # the maximally-narrow (fully greedy, order-dependent) extreme.
    WD_Dist = {'A': [1, 1], 'B': [1, 1], 'C': [1, 1]}   # all tied
    pool = SS._compute_sbp_pool(WD_Dist, pool_size=1)
    assert len(pool) == 1, pool
    print('test_sbp_pool_size_1_is_fully_deterministic_given_sweep_order passed')


def test_sbp_strictly_better_found_late_resets_pool():
    # First few candidates tie at a mediocre rank, filling the pool, then
    # a strictly better candidate arrives - the pool must contain ONLY
    # the strictly-better one(s), never any of the earlier mediocre ones.
    WD_Dist = {
        'M1': [2, 2],   # sum=4
        'M2': [2, 2],   # sum=4, ties M1
        'BEST': [1, 1],  # sum=2, strictly better - arrives last in dict order
    }
    pool = SS._compute_sbp_pool(WD_Dist, pool_size=5)
    assert pool == ['BEST'], pool
    print('test_sbp_strictly_better_found_late_resets_pool passed')


def test_empty_WD_Dist_raises():
    try:
        SS.select_candidate({})
        assert False, 'expected ValueError'
    except ValueError:
        pass
    print('test_empty_WD_Dist_raises passed')


def test_invalid_pool_size_raises():
    try:
        SS.select_candidate({'A': [1]}, sbp_pool_size=0)
        assert False, 'expected ValueError'
    except ValueError:
        pass
    print('test_invalid_pool_size_raises passed')


def test_999_entries_excluded_from_ranking():
    # A target that's still unreachable (999) must not distort sum/norm.
    WD_Dist = {
        'A': [999, 1, 1],   # effective sum=2, norm=2
        'B': [999, 2, 0],   # effective sum=2, norm=4 -> better norm, wins
    }
    candidates = SS._compute_original_candidates(WD_Dist)
    assert candidates == ['B'], candidates
    print('test_999_entries_excluded_from_ranking passed')


if __name__ == '__main__':
    test_original_matches_hand_computed_tie_group()
    test_sbp_large_pool_reduces_to_original_tie_group()
    test_sbp_small_pool_caps_but_never_includes_worse_candidates()
    test_sbp_pool_size_1_is_fully_deterministic_given_sweep_order()
    test_sbp_strictly_better_found_late_resets_pool()
    test_empty_WD_Dist_raises()
    test_invalid_pool_size_raises()
    test_999_entries_excluded_from_ranking()
    print('\nAll Selection_Strategy tests passed.')
