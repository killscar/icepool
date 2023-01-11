__docformat__ = 'google'

import icepool.expression

from icepool.evaluator.multiset_evaluator import MultisetEvaluator
from icepool.typing import Outcome

from typing import TypeVar

T_contra = TypeVar('T_contra', bound=Outcome, contravariant=True)
"""Type variable representing the input outcome type."""

U_co = TypeVar('U_co', bound=Outcome, covariant=True)
"""Type variable representing the final outcome type."""


class ExpressionEvaluator(MultisetEvaluator[T_contra, int, U_co]):
    """Wraps an evaluator with expressions to be evaluated first."""

    def __init__(self,
                 *expressions: 'icepool.expression.MultisetExpression',
                 evaluator: MultisetEvaluator[T_contra, int, U_co],
                 truth_value: bool | None = None) -> None:
        self._evaluator = evaluator
        self._expressions = expressions
        self._truth_value = truth_value

    def next_state(self, state, outcome, *counts):
        """Adjusts the counts, then forwards to inner."""
        counts = (expression.evaluate_counts(outcome, counts)
                  for expression in self._expressions)
        return self._evaluator.next_state(state, outcome, *counts)

    def final_outcome(self, final_state, *generators):
        """Forwards to inner."""
        return self._evaluator.final_outcome(final_state, *generators)

    def order(self, *generators):
        """Forwards to inner."""
        return self._evaluator.order(*generators)

    def alignment(self, *generators):
        """Forwards to inner."""
        return self._evaluator.alignment(*generators)

    def __bool__(self) -> bool:
        if self._truth_value is None:
            raise TypeError(
                'MultisetExpression only has a truth value if it is the result of the == or != operator.'
            )
        return self._truth_value


class MapExpressionEvaluator(MultisetEvaluator[T_contra, tuple[int, ...],
                                               U_co]):
    """An evaluator that jointly applies the given expression and evaluator to each input multiset.

    The resulting outcomes are tuples with length equal to the number of input multisets.
    """

    def __init__(self, expression: 'icepool.expression.MultisetExpression',
                 evaluator: MultisetEvaluator[T_contra, int, U_co]) -> None:
        """Constructor.

        Args:
            expression: The expression to apply. This should take in a single int.
            evaluator: The evaluator to use. Note that methods that are called
                with `*generators` will be provided with all generators.
        """
        self._evaluator = evaluator
        self._expression = expression

    def next_state(self, states, outcome, *counts):
        """Adjusts the counts, then forwards to inner."""
        counts = (self._expression.evaluate_counts(outcome, (count,))
                  for count in counts)
        if states is None:
            return tuple(
                self._evaluator.next_state(None, outcome, count)
                for count in counts)
        else:
            return tuple(
                self._evaluator.next_state(state, outcome, count)
                for state, count in zip(states, counts))

    def final_outcome(self, final_states, *generators):
        """Forwards to inner."""
        return tuple(
            self._evaluator.final_outcome(final_state, *generators)
            for final_state in final_states)

    def order(self, *generators):
        """Forwards to inner."""
        return self._evaluator.order(*generators)

    def alignment(self, *generators):
        """Forwards to inner."""
        return self._evaluator.alignment(*generators)
