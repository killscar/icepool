__docformat__ = 'google'

import hdroller
from hdroller.collections import FrozenSortedWeights

from abc import ABC, abstractmethod
import bisect
from collections import defaultdict
from functools import cache, cached_property
import itertools
import math
import operator
import random

class BaseDie():
    """ Abstract base die class for a die.
    
    A die is a discrete probability distribution with `int` weights.
    The outcomes can be any hashable, comparable values.
    
    The weights should be strictly positive for public dice.
    Some private calculations may use temporary dice with zero weights,
    however, this is not recommended for public use.
    
    Subclasses implement the operations that make sense only for a particular number of dimensions.
    """
    
    # Abstract methods.
    
    @abstractmethod
    def unary_op(self, op, *args, **kwargs):
        """ Returns a die representing the effect of performing the operation on the outcomes.
        
        This is used for the operators `-, +, abs, ~, round, trunc, floor, ceil`.
        """
    
    @abstractmethod
    def binary_op(self, other, op, *args, **kwargs):
        """ Returns a die representing the effect of performing the operation on pairs of outcomes from the two dice.
        
        The other operand is cast to a die (using `hdroller.die`) before performing the operation.
        
        This is used for the operators `+, -, *, /, //, %, **, <, <=, >=, >`.
        
        This is used for the logical operators `&, |, ^` on `bool()` of the outcome.
        
        Special operators:
            * The `@` operator rolls the left die, then rolls the right die that many times and sums the outcomes.
            * The `==` operator returns `True` iff the two dice have identical outcomes, weights, and `ndim`.
                To get the chance of the two dice rolling the same outcome, use the `eq` method.
            * The `!=` operator returns `True` iff the two dice do not have identical outcomes, weights, and `ndim`.
                To get the chance of the two dice rolling the same outcome, use the `ne` method.
        
        The operators `<<, >>` are not implemented.
        """
        
    # Construction.

    def __init__(self, data, ndim):
        """ Constructor, shared by subclasses.
        
        Users should usually not construct dice directly;
        instead they should use one of the methods defined in `hdroller.dice.func` 
        (which are imported into the top-level `hdroller` module).
        
        Args:
            data: A `FrozenSortedWeights` mapping outcomes to weights.
            ndim: The number of dimensions of the outcomes.
        """
        self._data = data
        self._ndim = ndim
        
    # Basic access.
    
    def ndim(self):
        return self._ndim
        
    def _check_ndim(*dice):
        """ Checks that `ndim` matches between the dice, and returns it. 
        
        Args:
            *dice: The dice to be checked.
        
        Returns:
            The common `ndim` of the dice.
        
        Raises:
            ValueError if a mismatch in `ndim` is found.
        """
        ndim = None
        for die in dice:
            if ndim is None:
                ndim = die.ndim()
            elif die.ndim() != ndim:
                raise ValueError('Dice have mismatched ndim.')
        return ndim
    
    def outcomes(self):
        """ Returns an iterable into the sorted outcomes of the die. """
        return self._data.keys()
    
    def weights(self):
        """ Returns an iterable into the weights of the die in outcome order. """
        return self._data.values()
        
    def __contains__(self, outcome):
        return outcome in self._data
    
    def weight(self, outcome):
        """ Returns the weight of a single outcome, or 0 if not present. """
        return self._data[outcome]
    
    def weight_le(self, outcome):
        """ Returns the weight <= a single outcome. """
        index = bisect.bisect_right(self.outcomes(), outcome)
        if index >= len(self): return self.total_weight()
        return self.cweights()[index]
        
    def weight_lt(self, outcome):
        """ Returns the weight < a single outcome. """
        index = bisect.bisect_left(self.outcomes(), outcome)
        if index >= len(self): return self.total_weight()
        return self.cweights()[index]
        
    def weight_ge(self, outcome):
        """ Returns the weight >= a single outcome. """
        index = bisect.bisect_left(self.outcomes(), outcome)
        if index >= len(self): return self.total_weight()
        return self.sweights()[index]
        
    def weight_gt(self, outcome):
        """ Returns the weight > a single outcome. """
        index = bisect.bisect_right(self.outcomes(), outcome)
        if index >= len(self): return self.total_weight()
        return self.sweights()[index]
    
    def probability(self, outcome):
        """ Returns the probability of a single outcome. """
        return self.weight(outcome) / self.total_weight()
    
    def items(self):
        """ Returns all outcome, weight pairs. """
        return self._data.items()
    
    def __len__(self):
        """ Returns the number of outcomes. """
        return len(self._data)
    
    # Unary operators.
    
    def __neg__(self):
        return self.unary_op(operator.neg)
    
    def __pos__(self):
        return self.unary_op(operator.pos)
    
    def __abs__(self):
        return self.unary_op(operator.abs)
    
    abs = __abs__
    
    @staticmethod
    def _invert(x):
        return not bool(x)
    
    def __invert__(self):
        """ This negates `bool(outcome)`. """
        return self.unary_op(self._invert)
    
    def __round__(self, ndigits=None):
        return self.unary_op(round, ndigits)
    
    def __trunc__(self):
        return self.unary_op(trunc)
    
    def __floor__(self):
        return self.unary_op(floor)
    
    def __ceil__(self):
        return self.unary_op(ceil)
    
    @staticmethod
    def _zero(x):
        return type(x)()
    
    def zero(self):
        """ Zeros all outcomes of this die. 
        
        This is done by calling the constructor for each outcome's type with no arguments.
        
        The result will have a single outcome with weight 1.
        
        Raises:
            `ValueError` if the zeros did not resolve to a single outcome.
        """
        result = self.unary_op(BaseDie._zero)
        if len(result) != 1:
            raise ValueError('zero() did not resolve to a single outcome.')
        return result.reduce()
    
    # Binary operators.
    
    def __add__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.add)
    
    def __radd__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.add)
    
    def __sub__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.sub)
    
    def __rsub__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.sub)
    
    def __mul__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.mul)
    
    def __rmul__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.mul)
        
    def __truediv__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.truediv)
    
    def __rtruediv__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.truediv)
    
    def __floordiv__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.floordiv)
    
    def __rfloordiv__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.floordiv)
    
    def __pow__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.pow)
    
    def __rpow__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.pow)
    
    def __mod__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.mod)
    
    def __rmod__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, operator.mod)
    
    # Comparators.
    
    def __lt__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.lt)
        
    def __le__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.le)
    
    def __ge__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.ge)
        
    def __gt__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, operator.gt)
    
    def eq(self, other):
        """ The chance that the two dice will roll equal to each other.
        
        Note that `__eq__` is taken up by the dice being equal, as opposed to the chance of their outcomes being equal.
        """
        other = hdroller.die(other)
        return self.binary_op(other, operator.eq)
    
    def ne(self, other):
        """ The chance that the two dice will roll not equal to each other.
        
        Note that `__ne__` is taken up by the dice being equal, as opposed to the chance of their outcomes being not equal.
        """
        other = hdroller.die(other)
        return self.binary_op(other, operator.ne)
    
    @staticmethod
    def _sign(x):
        z = BaseDie._zero(x)
        if x > z:
            return 1
        elif x < z:
            return -1
        else:
            return 0
    
    def sign(self):
        """ Outcomes become 1 if greater than `zero()`, -1 if less than `zero()`, and 0 otherwise.
        
        Note that for `float`s, +0.0, -0.0, and nan all become 0.
        """
        return self.unary_op(BaseDie._sign)
    
    @staticmethod
    def _cmp(x, y):
        return BaseDie._sign(x - y)
    
    def cmp(self, other):
        """ Returns a die with possible outcomes 1, -1, and 0.
        
        The weights are equal to the positive outcome of `self > other`, `self < other`, and the remainder respectively.
        """
        return self.binary_op(other, BaseDie._cmp)
    
    # Logical operators.
    # These operate on bool(outcome).
    
    @staticmethod
    def _and(x, y):
        return bool(x) and bool(y)
    
    def __and__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, self._and)
    
    def __rand__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, self._and)
    
    @staticmethod
    def _or(x, y):
        return bool(x) or bool(y)
        
    def __or__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, self._or)
    
    def __ror__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, self._or)
    
    @staticmethod
    def _xor(x, y):
        return bool(x) + bool(y) == 1
    
    def __xor__(self, other):
        other = hdroller.die(other)
        return self.binary_op(other, self._xor)
    
    def __rxor__(self, other):
        other = hdroller.die(other)
        return other.binary_op(self, self._xor)
    
    # Special operators.
    
    def __rmatmul__(self, other):
        """ Roll the left die, then roll the right die that many times and sum the outcomes. 
        
        Note that this differs from d() in that an `int` on the right side is treated as a constant
        rather than as a standard die.
        """
        other = hdroller.die(other)
        return other @ self
    
    # Mixtures.

    def relabel(self, relabeling):
        """ Changes outcomes of the die to other outcomes.
        
        Args:
            relabeling: One of the following:
                * An array-like containing relabelings, one for each outcome in order.
                * A map from old outcomes to new outcomes.
                    Unmapped old outcomes stay the same.
                * A function mapping old outcomes to new outcomes.
                A die may be provided instead of a single new outcome.
        
        Returns:
            The relabeled die.
        """
        if hasattr(relabeling, 'items'):
            relabeling = [(relabeling[outcome] if outcome in relabeling else outcome) for outcome in self.outcomes()]
        elif callable(relabeling):
            relabeling = [relabeling(outcome) for outcome in self.outcomes()]

        return hdroller.mix(*relabeling, mix_weights=self.weights())
    
    def explode(self, max_depth, outcomes=None):
        """ Causes outcomes to be rolled again and added to the total.
        
        Args:
            max_depth: The maximum number of additional dice to roll.
            outcomes: Which outcomes to explode. Options:
                * An iterable containing outcomes to explode.
                * If not supplied, the top single outcome will explode with full probability.
        """
        if max_depth < 0:
            raise ValueError('max_depth cannot be negative.')
        if max_depth == 0:
            return self
        
        if outcomes is None:
            outcomes = set([self.max_outcome()])
        
        explode = {}
        non_explode = {}
        
        for outcome, weight in self.items():
            if outcome in outcomes:
                explode[outcome] = weight
            else:
                non_explode[outcome] = weight
        
        non_explode_die = hdroller.dice.func.die(non_explode, ndim=self.ndim())
        tail_die = self.explode(max_depth-1, outcomes=outcomes)
        explode_die = hdroller.dice.func.die(explode, ndim=self.ndim()) + tail_die
        
        non_explode_die, explode_die = _align(non_explode_die, explode_die)
        data = { outcome : n_weight * tail_die.total_weight() + x_weight for (outcome, n_weight), x_weight in zip(non_explode_die.items(), explode_die.weights()) }
        
        return hdroller.dice.func.die(data, ndim=self.ndim())
    
    def reroll(self, *outcomes, max_depth=None):
        """ Rerolls the given outcomes.
        
        Args:
            *outcomes: Selects which outcomes to reroll. Options:
                * A set of outcomes to reroll.
            max_depth: The maximum number of times to reroll.
                If omitted, rerolls an unlimited number of times.
        
        Returns:
            A die representing the reroll.
            If the reroll would never terminate, the result is `None`.
        """
        if outcomes is None:
            raise TypeError('outcomes to reroll must be provided.')
        
        if max_depth is None:
            data = { outcome : weight for outcome, weight in self.items() if outcome not in outcomes }
            if len(data) == 0:
                return None
        else:
            total_reroll_weight = sum(weight for outcome, weight in self.items() if outcome in outcomes )
            rerollable_factor = total_reroll_weight ** max_depth
            stop_factor = self.total_weight() ** max_depth + total_reroll_weight ** max_depth
            data = { outcome : (rerollable_factor * weight if outcome in outcomes else stop_factor * weight) for outcome, weight in self.items() }
        return hdroller.dice.func.die(data, ndim=self.ndim())
    
    # Repeat, keep, and sum.
    
    def max(*dice):
        """ Roll all the dice and take the highest. """
        dice = _align(dice)
        ndim = BaseDie._check_ndim(*dice)
        cweights = tuple(math.prod(t) for t in zip(*(die.cweights() for die in dice)))
        return hdroller.from_cweights(dice[0].outcomes(), cweights, ndim=ndim)
    
    def min(*dice):
        """ Roll all the dice and take the lowest. """
        dice = _align(dice)
        ndim = BaseDie._check_ndim(*dice)
        sweights = tuple(math.prod(t) for t in zip(*(die.sweights() for die in dice)))
        return hdroller.from_sweights(dice[0].outcomes(), sweights, ndim=ndim)
    
    def repeat_and_sum(self, num_dice):
        """ Roll this die `num_dice` times and sum the results. """
        if num_dice < 0:
            return (-self).repeat_and_sum(-num_dice)
        elif num_dice == 0:
            return self.zero()
        elif num_dice == 1:
            return self
        
        half_result = self.repeat_and_sum(num_dice // 2)
        result = half_result + half_result
        if num_dice % 2: result += self
        return result
    
    def keep(self, num_dice, select_dice=None, *, min_outcomes=None, max_outcomes=None):
        """ Roll this die several times, possibly capping the maximum outcomes, and sum some or all of the sorted results.
        
        Args:
            max_outcomes: Either:
                * An iterable indicating the maximum outcome for each die in the pool.
                * An integer indicating the number of dice in the pool; all dice will have max outcome equal to `die.max_outcome()`.
            mask:
                The pool will be sorted from lowest to highest; only dice selected by mask will be counted.
                If omitted, all dice will be counted.
                
        Returns:
            A Die representing the probability distribution of the sum.
        """
        pool = hdroller.dice_pool.pool(self, num_dice, select_dice, min_outcomes=min_outcomes, max_outcomes=max_outcomes)
        return hdroller.pool_eval.pool_sum.eval(pool)
        
    def keep_highest(self, num_dice, num_keep=1, num_drop=0, *, min_outcomes=None, max_outcomes=None):
        """ Roll this die several times, possibly capping the maximum outcomes, and sum the sorted results from the highest.
        
        Args:
            num_dice: The number of dice to roll.
            num_keep: The number of dice to keep.
            num_drop: If provided, this many highest dice will be dropped before keeping.
                
        Returns:
            A die representing the probability distribution of the sum.
        """
        start = -(num_keep + (num_drop or 0))
        stop = -num_drop if num_drop > 0 else None
        select_dice = slice(start, stop)
        return self.keep(num_dice, select_dice, min_outcomes=min_outcomes, max_outcomes=max_outcomes)
        
    def keep_lowest(self, num_dice, num_keep=1, num_drop=0, *, min_outcomes=None, max_outcomes=None):
        """ Roll this die several times, possibly capping the maximum outcomes, and sum the sorted results from the lowest.
        
        Args:
            num_dice: The number of dice to roll.
            num_keep: The number of dice to keep.
            num_drop: If provided, this many lowest dice will be dropped before keeping.
                
        Returns:
            A die representing the probability distribution of the sum.
        """
        start = num_drop if num_drop > 0 else None
        stop = num_keep + (num_drop or 0)
        select_dice = slice(start, stop)
        return self.keep(num_dice, select_dice, min_outcomes=min_outcomes, max_outcomes=max_outcomes)
    
    # Modifying outcomes.
    
    def _set_outcomes(self, outcomes):
        """ Returns a die whose outcomes are set to the argument, including zero weights.
        
        This may remove outcomes or add zero-weight outcomes.
        
        Note that public methods are intended to have no zero-weight outcomes.
        This should therefore not be used externally for any Die that you want to do anything with afterwards.
        """
        data = {x : self.weight(x) for x in outcomes}
        return hdroller.dice.func.die(data, ndim=self.ndim(), remove_zero_weights=False)
    
    @cached_property
    def _pop_min(self):
        if len(self) > 1:
            d = { k : v for k, v in zip(self.outcomes()[1:], self.weights()[1:]) }
            die = hdroller.dice.func.die(d, ndim=self.ndim())
            return die, self.outcomes()[0], self.weights()[0]
        else:
            return None, self.outcomes()[0], self.weights()[0]
    
    def pop_min(self):
        """ Remove the min outcome and return the result, along with the popped outcome, and the popped weight.
        
        If the last outcome is removed, the returned die is `None`.
        """
        return self._pop_min
    
    @cached_property
    def _pop_max(self):
        if len(self) > 1:
            d = { k : v for k, v in zip(self.outcomes()[:-1], self.weights()[:-1]) }
            die = hdroller.dice.func.die(d, ndim=self.ndim())
            return die, self.outcomes()[-1], self.weights()[-1]
        else:
            return None, self.outcomes()[-1], self.weights()[-1]
    
    def pop_max(self):
        """ Remove the max outcome and return the result, along with the popped outcome, and the popped weight.
        
        If the last outcome is removed, the returned die is `None`.
        """
        return self._pop_max
    
    def reduce(self):
        """ Divides all weights by their greatest common denominator. """
        gcd = math.gcd(*self.weights())
        if gcd <= 1:
            return self
        data = { outcome : weight // gcd for outcome, weight in self.items() }
        return hdroller.dice.func.die(data, ndim=self.ndim())
    
    # Scalar(-ish) statistics.
    
    def min_outcome(*dice):
        """ Returns the minimum possible outcome among the dice. """
        return min(die.outcomes()[0] for die in dice)
    
    def max_outcome(*dice):
        """ Returns the maximum possible outcome among the dice. """
        return max(die.outcomes()[-1] for die in dice)
    
    @cached_property
    def _total_weight(self):
        return sum(self._data.values())
    
    def total_weight(self):
        """ The total weight of all outcomes. """
        return self._total_weight
        
    def mode(self):
        """ Returns a tuple containing the most common outcome(s) of the die.
        
        These are sorted from lowest to highest.
        """
        return tuple(outcome for outcome, weight in self.items() if weight == self.modal_weight())
    
    def modal_weight(self):
        """ The highest weight of any single outcome. """
        return max(self.weights())
    
    def ks_stat(self, other):
        """ Kolmogorov–Smirnov stat. The maximum absolute difference between CDFs. """
        a, b = _align(self, other)
        return max(abs(a - b) for a, b in zip(a.cdf(), b.cdf()))
    
    def cvm_stat(self, other):
        """ Cramér-von Mises stat. The sum-of-squares difference between CDFs. """
        a, b = _align(self, other)
        return sum((a - b) ** 2 for a, b in zip(a.cdf(), b.cdf()))
    
    # Iterable statistics.
    
    @cached_property
    def _pmf(self):
        return tuple(weight / self.total_weight() for weight in self.weights())
    
    def pmf(self):
        """ Probability mass function. The probability of rolling each outcome in order. """
        return self._pmf
    
    @cached_property
    def _cweights(self):
        return tuple(itertools.accumulate(self.weights()))
    
    def cweights(self):
        """ Cumulative weights. The weight <= each outcome in order. """
        return self._cweights
    
    @cached_property
    def _sweights(self):
        return tuple(itertools.accumulate(self.weights()[:-1], operator.sub, initial=self.total_weight()))
    
    def sweights(self):
        """ Survival weights. The weight >= each outcome in order. """
        return self._sweights
        
    @cached_property
    def _cdf(self):
        return tuple(weight / self.total_weight() for weight in self.cweights())
    
    def cdf(self):
        """ Cumulative distribution function. The chance of rolling <= each outcome in order. """
        return self._cdf
        
    @cached_property
    def _sf(self):
        return tuple(weight / self.total_weight() for weight in self.sweights())
    
    def sf(self):
        """ Survival function. The chance of rolling >= each outcome in order. """
        return self._sf
    
    # Rolling.
    
    def sample(self):
        """ Returns a random roll of this die. 
        
        Do not use for security purposes.
        """
        # We don't use random.choices since that is based on floats rather than ints.
        r = random.randrange(self.total_weight())
        index = bisect.bisect_right(self.cweights(), r)
        return self.outcomes()[index]
    
    # Type conversions out.
    
    def __bool__(self):
        """ Dice are not considered to have truth values. 
        
        The result of a comparator operation is a die, which if considered to have a truth value,
        would imply that dice are sortable.
        """
        raise TypeError('Dice do not have truth values.')
    
    # Strings.
    
    def __str__(self):
        """ Formats the die as a Markdown table. """
        weight_header = f'Weight (out of {self.total_weight()})'
        w = len(weight_header)
        o = max(len(str(outcome)) for outcome in self.outcomes())
        o = max(o, 7)
        result =  '| ' + ' ' * (o-7) + f'Outcome | {weight_header} | Probability |\n'
        result += '|-' + '-' *  o +            ':|-' + '-' * w + ':|------------:|\n'
        for outcome, weight, p in zip(self.outcomes(), self.weights(), self.pmf()):
            result += f'| {str(outcome):>{o}} | {weight:>{w}} | {p:11.6%} |\n'
        return result
    
    def __repr__(self):
        return type(self).__qualname__ + f'({self._data.__repr__()}, ndim={self.ndim()})'
    
    # Hashing and equality.
    
    @cached_property
    def _key_tuple(self):
        return self.ndim(), tuple(self.items())
        
    def __eq__(self, other):
        """ Returns `True` iff this die has the same outcomes, weights, and `ndim` as the other die.
        
        Note that fractions are NOT reduced for this comparison.
        For example, a 1:1 coin flip is NOT considered == to a 2:2 coin flip.
        """
        if not isinstance(other, BaseDie): return False
        return self._key_tuple == other._key_tuple
    
    @cached_property
    def _hash(self):
        return hash(self._key_tuple)
        
    def __hash__(self):
        return self._hash

def _align(*dice):
    """Pads all the dice with zero weights so that all have the same set of outcomes.
    
    Note that public methods are intended to have no zero-weight outcomes.
    This should therefore not be used externally for any die that you want to do anything with afterwards.
    
    Args:
        *dice: Multiple dice or a single iterable of dice.
    
    Returns:
        A tuple of aligned dice.
    
    Raises:
        `ValueError` if the dice are of mixed ndims.
    """
    dice = [hdroller.die(d) for d in dice]
    BaseDie._check_ndim(*dice)
    union_outcomes = set(itertools.chain.from_iterable(die.outcomes() for die in dice))
    return tuple(die._set_outcomes(union_outcomes) for die in dice)
    