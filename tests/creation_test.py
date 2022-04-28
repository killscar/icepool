import _context

import icepool
import pytest

def test_d_syntax():
    assert icepool.d6.weights() == (1,) * 6
    assert icepool.d6.probability(0) == 0.0
    assert icepool.d6.probability(1) == pytest.approx(1.0 / 6.0)
    assert icepool.d6.probability(6) == pytest.approx(1.0 / 6.0)
    assert icepool.d6.probability(7) == 0.0

def test_coin():
    b = icepool.bernoulli(1, 2)
    c = icepool.coin(1, 2)

    assert b.pmf() == pytest.approx([0.5, 0.5])
    assert c.pmf() == pytest.approx([0.5, 0.5])

def test_list_no_min_outcome():
    result = icepool.Die(2, 3, 3, 4, 4, 4, 5, 5, 6)
    expected = 2 @ icepool.d3
    assert result.equals(expected)

def test_zero_outcomes():
    die = icepool.Die(weights=[0, 1, 1, 1, 1, 1, 1], min_outcome=0)
    other = icepool.d6
    assert die.has_zero_weights()
    assert not die.equals(other)

def test_d6s():
    d6 = icepool.d6
    assert d6.equals(icepool.d(6))
    assert d6.equals(icepool.Die(d6))
    assert d6.equals(icepool.Die(icepool.d3, icepool.d3+3))
    assert d6.equals(icepool.Die({1:1, 2:1, 3:1, 4:1, 5:1, 6:1}))
    assert d6.equals(icepool.Die(1, 2, 3, 4, 5, 6))

def test_return_self():
    die = icepool.d6
    assert icepool.Die(die) is die

denominator_method_test_args = [
    ((), None),
    ((icepool.d5, icepool.d7), None),
    ((icepool.d6, icepool.d8), None),
    ((icepool.d6, icepool.d8, icepool.d10), None),
    ((icepool.d6, icepool.d8, icepool.d10, icepool.d12), (4, 3, 2, 1)),
    ((icepool.d6, icepool.d8, icepool.d10, icepool.d12), (3, 4, 5, 6)),
]

@pytest.mark.parametrize('args,weights', denominator_method_test_args)
def test_denominator_method(args, weights):
    prod = icepool.Die(*args, weights=weights, denominator_method='prod')
    lcm = icepool.Die(*args, weights=weights, denominator_method='lcm')
    lcm_weighted = icepool.Die(*args, weights=weights, denominator_method='lcm_weighted')
    assert prod.reduce().equals(lcm.reduce())
    assert prod.reduce().equals(lcm_weighted.reduce())
    assert prod.denominator() >= lcm.denominator()
    assert lcm.denominator() >= lcm_weighted.denominator()

def test_denominator_lcm_weighted():
    result = icepool.Die(icepool.d6, icepool.d8, icepool.d10, icepool.d12, weights=(3, 4, 5, 6), denominator_method='lcm_weighted')
    assert result.denominator() == 36

def test_scalar_vector():
    assert icepool.Die({}, ndim=icepool.Scalar).ndim() == icepool.Empty
    assert icepool.Die({}, ndim=3).ndim() == icepool.Empty
    assert icepool.Die({icepool.Reroll : 1}, ndim=icepool.Scalar).ndim() == icepool.Empty
    assert icepool.Die((1, 2, 3)).ndim() == 3
    assert icepool.Die((1, 2, 3), ndim=icepool.Scalar).ndim() == icepool.Scalar
    assert icepool.Die('test').ndim() == icepool.Scalar
    