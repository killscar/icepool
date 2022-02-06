__docformat__ = 'google'

import hdroller.math
from hdroller.functools import die_cache

import bisect
from functools import cached_property
import math

def Pool(die, num_dice=None, count_dice=None, *, min_outcomes=None, max_outcomes=None):
    """ Factory function for dice pools.
    
    This is capitalized because it is the preferred way of getting a new instance,
    and so that you can use `from hdroller import Pool` while leaving the name `pool` free.
    The name of the actual class is `DicePool`.
    
    You can use `die.pool(args...)` for the same effect as this function.
    
    All instances are cached.
    
    Args:
        die: The fundamental die of the pool.
        num_dice: An `int` that sets the number of dice in the pool.
            If no arguments are provided, this defaults to 0.
        count_dice: Determines which of the **sorted** dice will be counted, and how many times each.
            
            `count_dice` can be an `int` or a `slice`, in which case the selected dice are counted once each.
            For example, `slice(-2, None)` would count the two highest dice.
            
            Or `count_dice` can be a sequence of `int`s, one for each die in order.
            Each die is counted that many times.
            For example, `[0, 1, 1]` would count the two highest dice out of three.
            `[0, 0, 2, 0, 0]` would count the middle out of five dice twice.
            `[-1, 1]` would roll two dice, counting the higher die as a positive and the lower die as a negative.
            
            You can also use the `[]` operator to select dice from an existing pool.
            This is always an absolute selection on all `num_dice`,
            not a relative selection on already-selected dice,
            which would be ambiguous in the presence of multiple or negative counts.
            
            The `[]` operator can even change the size of the pool,
            provided that neither `min_outcomes` nor `max_outcomes` are set.
            For example, you could create a pool of 4d6 drop lowest using `hdroller.d6.pool()[0, 1, 1, 1]`.
        min_outcomes: A sequence of one outcome per die in the pool.
            That die will be limited to that minimum outcome, with all lower outcomes being removed (i.e. rerolled).
            A pool cannot limit both `min_outcomes` and `max_outcomes`.
        max_outcomes: A sequence of one outcome per die in the pool.
            That die will be limited to that maximum outcome, with all higher outcomes being removed (i.e. rerolled).
            A pool cannot limit both `min_outcomes` and `max_outcomes`.
    
    Raises:
        `ValueError` if arguments conflict with each other.
    """
    
    # Compute num_dice.
    
    for seq in (count_dice, min_outcomes, max_outcomes):
        if hasattr(seq, '__len__'):
            if num_dice is not None and num_dice != len(seq):
                raise ValueError('Conflicting values for the number of dice: ' +
                    f'num_dice={num_dice}, count_dice={count_dice}, min_outcomes={min_outcomes}, max_outcomes={max_outcomes}')
            else:
                num_dice = len(seq)
        
    if num_dice is None:
        num_dice = 0
    
    # Compute count_dice.
    
    if count_dice is None:
        count_dice = (1,) * num_dice
    else:
        count_dice = _compute_count_dice(num_dice, count_dice)
    
    # Put min/max outcomes into standard form.
    # This is either a sorted tuple, or `None` if there is no (effective) limit to the die size on that side.
    
    if num_dice == 0:
        min_outcomes = None
        max_outcomes = None
    else:
        if min_outcomes is not None:
            if max(min_outcomes) > die.min_outcome():
                min_outcomes = tuple(sorted(max(outcome, die.min_outcome()) for outcome in min_outcomes))
            else:
                # The min_outcomes don't actually do anything.
                min_outcomes = None
        
        if max_outcomes is not None:
            if min(max_outcomes) < die.max_outcome():
                max_outcomes = tuple(sorted(min(outcome, die.max_outcome()) for outcome in max_outcomes))
            else:
                # The max_outcomes don't actually do anything.
                max_outcomes = None
    
    if min_outcomes is not None and max_outcomes is not None:
        raise ValueError('A pool cannot limit both min_outcomes and max_outcomes.')
    
    return _pool_cached_unchecked(die, count_dice, min_outcomes, max_outcomes)

def _compute_count_dice(num_dice, count_dice):
    """ Returns a tuple specifying count_dice.
    
    If `count_dice` is already a sequence, this does not check its length against `num_dice`.
    """
    if isinstance(count_dice, int):
        result = [0] * num_dice
        result[count_dice] = 1
        return tuple(result)
    elif isinstance(count_dice, slice):
        result = [0] * num_dice
        result[count_dice] = [1] * len(result[count_dice])
        return tuple(result)
    else:
        if not all(isinstance(x, int) for x in count_dice):
            raise TypeError('count_dice must be a sequence of ints.')
        return tuple(count_dice)

@die_cache
def _pool_cached_unchecked(die, count_dice, min_outcomes, max_outcomes):
    """ Cached, unchecked constructor for dice pools.
    
    This should not be used directly. Use the `Pool()` factory function instead.
    """
    return DicePool(die, count_dice, min_outcomes=min_outcomes, max_outcomes=max_outcomes)

class DicePool():
    def __init__(self, die, count_dice, *, min_outcomes, max_outcomes):
        """ Unchecked constructor.
        
        This should not be used directly. Use the `Pool()` factory function instead.
        
        Args:
            die: The fundamental die of the pool.
            count_dice: At this point, this should be a tuple the length of the pool.
            min_outcomes: At this point this should be a tuple the length of the pool or `None`.
            max_outcomes: At this point this should be a tuple the length of the pool or `None`.
        """
        self._die = die
        self._count_dice = count_dice
        self._min_outcomes = min_outcomes
        self._max_outcomes = max_outcomes
        
    def die(self):
        """ The fundamental die of the pool. """
        return self._die
        
    def count_dice(self):
        """ A tuple indicating how many times each of the dice, sorted from lowest to highest, counts. """
        return self._count_dice
        
    def __getitem__(self, count_dice):
        """ Returns a pool with the selected dice counted, as the `count_dice` argument to `Pool()`.
        
            Determines which of the **sorted** dice will be counted, and how many times.
            The dice are sorted in ascending order for this purpose,
            regardless of which order the outcomes are evaluated in.
            
            This can be an `int` or a `slice`, in which case the selected dice are counted once each.
            For example, `slice(-2, None)` would count the two highest dice.
            
            Or this can be a sequence of `int`s, one for each die in order.
            Each die is counted that many times.
            For example, `[-2:]` would also count the two highest dice.
            `[0, 0, 2, 0, 0]` would count the middle out of five dice twice.
            `[-1, 1]` would roll two dice, counting the higher die as a positive and the lower die as a negative.
            This can change the size of the pool, but only if neither `min_outcomes` or `max_outcomes` are set.
            
            This is always an absolute selection on all `num_dice`,
            not a relative selection on already-selected dice,
            which would be ambiguous in the presence of multiple or negative counts.
        """
        count_dice = _compute_count_dice(self.num_dice(), count_dice)
        if len(count_dice) != self.num_dice():
            if self.min_outcomes() is not None:
                raise ValueError('The [] operator cannot change the size of a pool with min_outcomes.')
            if self.max_outcomes() is not None:
                raise ValueError('The [] operator cannot change the size of a pool with max_outcomes.')
        return Pool(self.die(), count_dice=count_dice, min_outcomes=self.min_outcomes(), max_outcomes=self.max_outcomes())
    
    def num_dice(self):
        return len(self._count_dice)
    
    __len__ = num_dice
        
    def min_outcomes(self, always_tuple=False):
        """ A tuple of sorted min outcomes, one for each die in the pool. 
        
        Args:
            * always_tuple: If `False`, this will return `None` if there are no die-specific min_outcomes.
                If `True` this will return a `tuple` even in this case.
        """
        if self._min_outcomes is None and always_tuple:
            return (self.die().min_outcome(),) * self.num_dice()
        return self._min_outcomes
    
    def max_outcomes(self, always_tuple=False):
        """ A tuple of sorted max outcomes, one for each die in the pool. 
        
        Args:
            * always_tuple: If `False`, this will return `None` if there are no die-specific max_outcomes.
                If `True` this will return a `tuple` even in this case.
        """
        if self._max_outcomes is None and always_tuple:
            return (self.die().max_outcome(),) * self.num_dice()
        return self._max_outcomes
    
    def _iter_pop_max(self):
        """
        Yields:
            From 0 to the number of dice that can roll this outcome inclusive:
            * pool: A `DicePool` resulting from removing that many dice from this `DicePool`, while also removing the max outcome.
                If there is only one outcome with weight remaining, only one result will be yielded, corresponding to all dice rolling that outcome.
                If the outcome has zero weight, only one result will be yielded, corresponding to zero dice rolling that outcome.
                If there are no outcomes remaining, this will be `None`.
            * count: An `int` indicating the number of selected dice that rolled the removed outcome.
            * weight: An `int` indicating the weight of that many dice rolling the removed outcome.
        """
        max_outcomes = self.max_outcomes(always_tuple=True)
        remaining_count = sum(self.count_dice())

        num_possible_dice = self.num_dice() - bisect.bisect_left(max_outcomes, self.die().max_outcome())
        num_unused_dice = self.num_dice() - num_possible_dice
        popped_die, outcome, single_weight = self.die().pop_max()
        
        if len(popped_die) == 0:
            # This is the last outcome. All dice must roll this outcome.
            weight = single_weight ** num_possible_dice
            yield None, remaining_count, weight
            return
        
        if popped_die.total_weight() == 0:
            # This is the last outcome with positive weight. All dice must roll this outcome.
            weight = single_weight ** num_possible_dice
            pool = Pool(popped_die, count_dice=(), max_outcomes=())
            yield pool, remaining_count, weight
            return
        
        if not any(self.count_dice()):
            # No selected dice remain. All dice must roll somewhere below, so empty all dice in one go.
            # We could follow the staircase of max_outcomes more closely but this is unlikely to be relevant in most cases.
            pool = Pool(popped_die, count_dice=(), max_outcomes=())
            weight = math.prod(self.die().weight_le(max_outcome) for max_outcome in max_outcomes)
            yield pool, 0, weight
            return
        
        popped_max_outcomes = max_outcomes[:num_unused_dice] + (popped_die.max_outcome(),) * num_possible_dice
        popped_count_dice = self.count_dice()
        
        # Zero dice rolling this outcome.
        # If there is no weight, this is the only possibility.
        pool = Pool(popped_die, count_dice=popped_count_dice, max_outcomes=popped_max_outcomes)
        weight = 1
        count = 0
        yield pool, count, weight
        
        if single_weight > 0:
            # If the outcome has nonzero weight, consider how many dice could roll this outcome.
            comb_row = hdroller.math.comb_row(num_possible_dice, single_weight)
            for weight in comb_row[1:]:
                count += popped_count_dice[-1]
                popped_max_outcomes = popped_max_outcomes[:-1]
                popped_count_dice = popped_count_dice[:-1]
                pool = Pool(popped_die, count_dice=popped_count_dice, max_outcomes=popped_max_outcomes)
                yield pool, count, weight
    
    @cached_property
    def _pop_max(self):
        if self.min_outcomes() is not None:
            raise ValueError('pop_maxs is not valid with min_outcomes.')
        return tuple(self._iter_pop_max())
    
    def pop_max(self):
        """ Returns a sequence of pool, count, weight corresponding to removing the max outcome,
        with count and weight corresponding to various numbers of dice rolling that outcome.
        """
        return self._pop_max
        
    def sum(self):
        """ Convenience method to simply sum the dice in this pool.
        
        This uses `hdroller.sum_pool`.
        
        Returns:
            A die representing the sum.
        """
        return hdroller.sum_pool(self)
    
    @cached_property
    def _key_tuple(self):
        return self.die().key_tuple(), self.count_dice(), self.min_outcomes(), self.max_outcomes()
    
    def __eq__(self, other):
        if not isinstance(other, DicePool): return False
        return self._key_tuple == other._key_tuple
    
    @cached_property
    def _hash(self):
        return hash(self._key_tuple)
        
    def __hash__(self):
        return self._hash

    def __str__(self):
        return '\n'.join([str(self.die()), str(self.count_dice()), str(self.min_outcomes()), str(self.max_outcomes())])