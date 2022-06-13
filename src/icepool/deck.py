__docformat__ = 'google'

import icepool
import icepool.math
from icepool.common_args import is_dict
from icepool.collections import Counts
from icepool.generator import OutcomeCountGen
from icepool.deck_args import expand_create_args

from functools import cached_property

from typing import Any, Generator
from collections.abc import Mapping, Sequence


class Deck(OutcomeCountGen):
    """EXPERIMENTAL: Represents drawing a hand from a deck.

    In other words, this is sampling without replacement.
    """

    _data: Counts
    _hand_size: int

    def __new__(cls,
                outcomes,
                dups: Sequence[int] | None = None,
                *,
                hand_size: int):
        """Constructor for a deck.

        Args:
            outcomes: The outcomes of the deck, i.e. the cards. This can be
                one of the following:

                * A dict mapping outcomes to dups.
                * A sequence of outcomes.

                Each outcome may be one of the following:

                * A deck. The outcomes of the deck will be "flattened" into the
                    result; a deck object will never contain a deck as an
                    outcome.
                * A dict mapping outcomes to dups.
                * A tuple of outcomes.

                    Any tuple elements that are decks or dicts will expand the
                    tuple according to their independent joint distribution.
                    Use this carefully since it may create a large number of
                    outcomes.
                * Anything else will be treated as a scalar.
        """
        self = super(Deck, cls).__new__(cls)
        if is_dict(outcomes):
            if dups is not None:
                raise ValueError('dups cannot be used with a dict argument.')
            dups = tuple(outcomes.values())  # type: ignore
            outcomes = tuple(outcomes.keys())  # type: ignore
        else:
            if dups is None:
                dups = (1,) * len(outcomes)
            else:
                if len(dups) != len(outcomes):
                    raise ValueError(
                        'Length of dups must equal the number of outcomes.')
        if any(x < 0 for x in dups):
            raise ValueError('dups cannot have negative values.')
        self._data = expand_create_args(*outcomes, dups=dups)
        self._hand_size = hand_size
        if self.hand_size() > self.deck_size():
            raise ValueError('hand_size cannot exceed deck_size.')
        return self

    def outcomes(self) -> Sequence:
        return self._data.keys()

    def dups(self) -> Sequence[int]:
        return self._data.values()

    def items(self) -> Sequence[tuple[Any, int]]:
        return self._data.items()

    @cached_property
    def _deck_size(self) -> int:
        return sum(self._data.values())

    def deck_size(self) -> int:
        return self._deck_size

    def hand_size(self) -> int:
        return self._hand_size

    @cached_property
    def _denomiator(self) -> int:
        return icepool.math.comb(self.deck_size(), self.hand_size())

    def denominator(self) -> int:
        return self._denomiator

    def _is_resolvable(self) -> bool:
        return len(self.outcomes()) > 0

    def _pop_min(
        self, min_outcome
    ) -> Generator[tuple['OutcomeCountGen', int, int], None, None]:
        if not self.outcomes() or min_outcome != self.min_outcome():
            yield self, 0, 1
            return

        deck_count = self.dups()[0]

        min_count = max(0, deck_count + self.hand_size() - self.deck_size())
        max_count = min(deck_count, self.hand_size())
        for count in range(min_count, max_count + 1):
            popped_draw = Deck(
                self.outcomes()[1:],
                dups=self.dups()[1:],
                hand_size=self.hand_size() - count,
            )
            weight = icepool.math.comb(deck_count, count)
            yield popped_draw, count, weight

    def _pop_max(
        self, max_outcome
    ) -> Generator[tuple['OutcomeCountGen', int, int], None, None]:
        if not self.outcomes() or max_outcome != self.max_outcome():
            yield self, 0, 1
            return

        deck_count = self.dups()[-1]

        min_count = max(0, deck_count + self.hand_size() - self.deck_size())
        max_count = min(deck_count, self.hand_size())
        for count in range(min_count, max_count + 1):
            popped_draw = Deck(self.outcomes()[:-1],
                               dups=self.dups()[:-1],
                               hand_size=self.hand_size() - count)
            weight = icepool.math.comb(deck_count, count)
            yield popped_draw, count, weight

    def _estimate_direction_costs(self) -> tuple[int, int]:
        result = len(self.outcomes()) * self.hand_size()
        return result, result

    @cached_property
    def _key_tuple(self) -> tuple:
        return (Deck,) + tuple(self.items()) + (self.hand_size(),)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Deck):
            return False
        return self._key_tuple == other._key_tuple

    @cached_property
    def _hash(self) -> int:
        return hash(self._key_tuple)

    def __hash__(self) -> int:
        return self._hash


empty_deck = Deck([], hand_size=0)