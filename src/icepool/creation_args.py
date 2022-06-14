__docformat__ = 'google'

import icepool
from icepool.counts import Counts

import itertools
import math
from collections import defaultdict

from typing import Any, Callable
from collections.abc import Container, Mapping, MutableMapping, Sequence


def itemize(keys: Mapping[Any, int] | Sequence,
            times: Sequence[int] | int) -> tuple[Sequence, Sequence[int]]:
    """Converts the argument(s) into a sequence of keys and a sequence of counts.

    Args:
        keys: One of the following:
            * A dict mapping keys to times.
            * A sequence of keys, with one count per occurence.
        times: One of the following:
            * A sequence of `int`s of the same length as keys.
                Each count will be multiplied by the corresponding factor.
            * An `int`. All times will be multiplied by this factor.
    """
    if isinstance(times, int):
        times = (times,) * len(keys)
    else:
        if len(times) != len(keys):
            raise ValueError(
                'The number of times must equal the number of keys.')

    if is_dict(keys):
        times = tuple(
            v * x for v, x in zip(keys.values(), times))  # type: ignore
        keys = tuple(keys.keys())  # type: ignore
    else:
        keys = tuple(keys)

    if any(x < 0 for x in times):
        raise ValueError('counts cannot have negative values.')

    return keys, times


def expand_args_for_die(args, times, denominator_method: str):
    merge_func = merge_weights_funcs[denominator_method]
    subdatas = [expand(arg, merge_func) for arg in args]
    data = merge_func(subdatas, times)

    return Counts(sorted(data.items()))


def expand_args_for_deck(args, times):
    merge_func = merge_dups
    subdatas = [expand(arg, merge_func) for arg in args]
    data = merge_func(subdatas, times)

    return Counts(sorted(data.items()))


def expand(arg, merge_func: Callable):

    if hasattr(arg, 'items'):
        return expand_dict(arg, merge_func)
    elif isinstance(arg, tuple):
        return expand_tuple(arg, merge_func)
    else:
        return expand_scalar(arg)


def is_dict(arg) -> bool:
    return hasattr(arg, 'keys') and hasattr(arg, 'values') and hasattr(
        arg, 'items') and hasattr(arg, '__getitem__')


def expand_dict(arg, merge_func: Callable) -> Mapping[Any, int]:
    subdatas = [expand(k, merge_func) for k, _ in arg.items()]
    weights = [v for _, v in arg.items()]
    return merge_func(subdatas, weights)


def expand_tuple(arg, merge_func: Callable) -> Mapping[Any, int]:
    if len(arg) == 0:
        return {(): 1}
    subdatas = [expand(x, merge_func) for x in arg]
    data: MutableMapping[Any, int] = defaultdict(int)
    for t in itertools.product(*(subdata.items() for subdata in subdatas)):
        outcomes, dups = zip(*t)
        data[outcomes] += math.prod(dups)
    return data


def expand_scalar(arg) -> Mapping[Any, int]:
    if arg is icepool.Reroll:
        return {}
    else:
        return {arg: 1}


def merge_weights_prod(subdatas: Sequence[Mapping[Any, int]],
                       weights: Sequence[int]) -> Mapping[Any, int]:
    if any(x < 0 for x in weights):
        raise ValueError('weights cannot be negative.')

    subdata_denominators = [sum(subdata.values()) for subdata in subdatas]

    denominator_prod = math.prod(d for d in subdata_denominators if d > 0)

    data: MutableMapping[Any, int] = defaultdict(int)
    for subdata, subdata_denominator, w in zip(subdatas, subdata_denominators,
                                               weights):
        factor = denominator_prod * w // subdata_denominator if subdata_denominator else 0
        for outcome, weight in subdata.items():
            data[outcome] += weight * factor
    return data


def merge_weights_lcm(subdatas: Sequence[Mapping[Any, int]],
                      weights: Sequence[int]) -> Mapping[Any, int]:
    if any(x < 0 for x in weights):
        raise ValueError('weights cannot be negative.')

    subdata_denominators = [sum(subdata.values()) for subdata in subdatas]

    denominator_prod = math.lcm(*(d for d in subdata_denominators if d > 0))

    data: MutableMapping[Any, int] = defaultdict(int)
    for subdata, subdata_denominator, w in zip(subdatas, subdata_denominators,
                                               weights):
        factor = denominator_prod * w // subdata_denominator if subdata_denominator else 0
        for outcome, weight in subdata.items():
            data[outcome] += weight * factor
    return data


def merge_weights_lcm_joint(subdatas: Sequence[Mapping[Any, int]],
                            weights: Sequence[int]) -> Mapping[Any, int]:
    if any(x < 0 for x in weights):
        raise ValueError('weights cannot be negative.')

    subdata_denominators = [sum(subdata.values()) for subdata in subdatas]

    denominator_prod = math.lcm(*(d // math.gcd(d, w)
                                  for d, w in zip(subdata_denominators, weights)
                                  if d > 0))

    data: MutableMapping[Any, int] = defaultdict(int)
    for subdata, subdata_denominator, w in zip(subdatas, subdata_denominators,
                                               weights):
        factor = denominator_prod * w // subdata_denominator if subdata_denominator else 0
        for outcome, weight in subdata.items():
            data[outcome] += weight * factor
    return data


def merge_weights_reduce(subdatas: Sequence[Mapping[Any, int]],
                         weights: Sequence[int]) -> Mapping[Any, int]:
    data = merge_weights_lcm_joint(subdatas, weights)

    gcd = math.gcd(*data.values())
    if gcd > 1:
        data = {outcome: weight // gcd for outcome, weight in data.items()}

    return data


merge_weights_funcs = {
    'prod': merge_weights_prod,
    'lcm': merge_weights_lcm,
    'lcm_joint': merge_weights_lcm_joint,
    'reduce': merge_weights_reduce,
}


def merge_dups(subdatas: Sequence[Mapping[Any, int]],
               dups: Sequence[int]) -> Mapping[Any, int]:
    if any(x < 0 for x in dups):
        raise ValueError('dups cannot be negative.')

    data: MutableMapping[Any, int] = defaultdict(int)
    for subdata, subdup in zip(subdatas, dups):
        for outcome, dup in subdata.items():
            data[outcome] += dup * subdup

    return data
