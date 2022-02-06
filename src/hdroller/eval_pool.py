__docformat__ = 'google'

import hdroller

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from functools import cached_property
import itertools
import math

class EvalPool(ABC):
    """ An abstract, immutable, callable class for evaulating one or more `DicePool`s.
    
    You can pretend that evaluation occurs on individual rolls of the pool as follows:
    
    1. First, specify the `initial_state()`. The state is usually some sort of running total.
    2. Then, you will be given one outcome at a time,
        along with how many dice in each pool rolled that outcome.
        Update the state using `next_state()` using that information.
        
    `final_outcome()`, `reroll_state()` provided further options for customizing behavior,
    but are not necessary.
    
    Instances cache all intermediate state distributions.
    You should therefore reuse instances when possible.
    
    Instances should not be modified after construction
    in any way that affects the return values of these methods.
    Otherwise, values in the cache may be incorrect.
    """
    
    @abstractmethod
    def initial_state(self, *pools):
        """ Generates an initial state for the evaluation.
        
        Arguments:
            *pools: One or more `DicePool`s being evaluated.
        
        Returns:
            A hashable object indicating the initial state.
        
        If you want to use information about the pool(s) being evaluated,
        you need to save that information to the state here.
        This is to avoid polluting the cache with duplicate entries
        based on irrelevant information in the key.
        """
    
    @abstractmethod
    def next_state(self, prev_state, outcome, *counts):
        """ State transition function.
        
        This should produce a state given the previous state, an outcome, and the number of dice in each pool rolling that outcome.
        Note that outcomes are not guaranteed to be consecutive, as outcomes not present in any pool will not be considered.
        
        Args:
            prev_state: A hashable object indicating the state before rolling the current outcome.
            outcome: The current outcome.
            counts: One `int`for each pool indicating how many dice in that pool rolled the current outcome.
                If there are multiple pools, it's possible that some outcomes will not appear in all pools.
                In this case, the count for the pool(s) that do not have the outcome will be `None`. 
                Zero-weight outcomes count having that outcome (with 0 count).
        
        Returns:
            A hashable object indicating the next state.
        """
    
    def reroll_state(self, prev_state, outcome, *counts):
        """ Optional function to reroll states.
        
        Given the same arguments as `next_state()`, if this returns `True`,
        the state will immediately be dropped from consideration.
        This effectively performs a reroll of the entire pool.
        """
        return False
    
    def final_outcome(self, final_state, *pools):
        """ Optional function to generate a final outcome from a final state.
        
        If not overridden, the final state is used as the final outcome.
        
        Args:
            final_state: A state after all outcomes have been processed.
            *pools: One or more `DicePool`s being evaluated.
            
        Returns:
            A final outcome that will be used as part of constructing a die.
            This should be hashable and comparable.
        """
        return final_state
    
    def ndim(self, *pools):
        """ Optional function to specify the number of dimensions of the output die.
        
        The priority to determine ndim is as follows.
        
        1. The `ndim` argument to `eval()`, if not `None`.
        2. This method, if not `None`.
        3. Automatically determined by `die()`.
        
        Args:
            *pools: One or more `DicePool`s being evaluated.
        
        Returns:
            The number of dimensions that the output die should have,
            or `None` if this should be determined automatically by `die()`.
        """
        return None
    
    @cached_property
    def _cache(self):
        return {}
    
    def eval(self, *pools, ndim=None):
        """ Evaluates pools.
        
        You can call the `EvalPool` object directly for the same effect,
        e.g. `sum_pool(pool)` is an alias for `sum_pool.eval(pool)`.
        
        Args:
            *pools: One or more `DicePool`s to evaluate.
                Most evaluators will expect a fixed number of pools.
                The outcomes of the pools must be mutually comparable.
            ndim: The number of dimensions of the resulting die.
                If omitted, this will be determined automatically.
        
        Returns:
            A die representing the distribution of the final score.
        """
        initial_state = self.initial_state(*pools)
        dist = self._eval_internal(initial_state, *pools)
        
        final_dist = defaultdict(int)
        for state, weight in dist.items():
            outcome = self.final_outcome(state, *pools)
            final_dist[outcome] += weight
        
        if ndim is None:
            ndim = self.ndim(*pools)
        
        return hdroller.Die(final_dist, ndim=ndim)
    
    __call__ = eval
    
    def _eval_internal(self, initial_state, *pools):
        """
        Arguments:
            initial_state: The initial state. This is passed without change recursively.
            *pools: One or more `DicePool`s to evaluate.
                Values of `None` indicate that pool has no remaining outcomes to process.
                This *does* change recursively.
            
        Returns:
            A dict `{ state : weight }` describing the probability distribution over states.
        """
        cache_key = (initial_state, pools)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = defaultdict(int)
        
        if all(pool is None for pool in pools):
            result[initial_state] = 1
        else:
            outcome = max(pool.die().max_outcome() for pool in pools if pool is not None)
            for p in itertools.product(*[self._iter_pool(outcome, pool) for pool in pools]):
                prev_pools, counts, weights = zip(*p)
                prod_weight = math.prod(weights)
                prev = self._eval_internal(initial_state, *prev_pools)
                for prev_state, prev_weight in prev.items():
                    if self.reroll_state(prev_state, outcome, *counts):
                        continue
                    state = self.next_state(prev_state, outcome, *counts)
                    result[state] += prev_weight * prod_weight
        
        self._cache[cache_key] = result
        return result
    
    @staticmethod
    def _iter_pool(outcome, pool):
        """ Iterates over possible numbers of dice that could roll an outcome.
        
        Args:
            outcome: The outcome under consideration.
            pool: The `DicePool` under consideration.
        
        Yields:
            prev_pool: The remainder of the pool after taking out the dice that rolled the current outcome.
            count: How many dice rolled the current outcome, or `None` if the outcome is not in this pool.
            weight: The weight of that many dice rolling the current outcome.
        """
        if pool is None or outcome not in pool.die():
            yield pool, None, 1
        else:
            yield from pool.pop_max()

class SumPool(EvalPool):
    """ A simple `EvalPool` that just sums the dice in a pool. """
    def initial_state(self, pool):
        """ The running total starts at 0. """
        return 0
        
    def next_state(self, prev_state, outcome, count):
        """ Add the dice to the running total. """
        return prev_state + outcome * count

""" A shared `SumPool` object for caching results. """
sum_pool = SumPool()

class FindMatchingSets(EvalPool):
    """ A `EvalPool` that takes the best matching set in a pool.
    
    This prioritizes set size, then the outcome.
    
    The outcomes are `(set_size, outcome)`.
    """
    def initial_state(self, pool):
        """ Start with `set_size = -1` so any outcome will be written in. """
        return -1, 0
    
    def next_state(self, prev_state, outcome, count):
        """ Replace the last best set if this one is better. 
        
        Note the use of tuple comparison, which priortizes elements to the left.
        """
        return max(prev_state, (count, outcome))