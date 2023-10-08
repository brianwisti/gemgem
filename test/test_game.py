"""Tests for arcade gem game."""

import pytest

from pygame_gem import Direction, GemInfo


# pylint: disable=missing-function-docstring,missing-class-docstring,redefined-outer-name


class TestGemInfo:
    @pytest.mark.parametrize(
        "first_gem,second_gem, expected",
        [
            (GemInfo(0, 0, 0), GemInfo(0, 0, 1), True),
            (GemInfo(0, 0, 0), GemInfo(0, 1, 0), True),
            (GemInfo(0, 1, 0), GemInfo(0, 0, 0), True),
            (GemInfo(0, 0, 1), GemInfo(0, 0, 0), True),
            (GemInfo(0, 0, 0), GemInfo(0, 0, 0), False),
            (GemInfo(0, 1, 1), GemInfo(0, 1, 5), False),
            (GemInfo(0, 1, 1), GemInfo(0, 2, 2), False),
        ],
    )
    def test_is_neighbor_of(self, first_gem, second_gem, expected):
        assert first_gem.is_adjacent_to(second_gem) == expected

    @pytest.mark.parametrize(
        "first_gem,second_gem, first_direction, second_direction",
        [
            (GemInfo(0, 0, 0), GemInfo(0, 1, 0), Direction.RIGHT, Direction.LEFT),
            (GemInfo(0, 1, 0), GemInfo(0, 0, 0), Direction.LEFT, Direction.RIGHT),
            (GemInfo(0, 0, 1), GemInfo(0, 0, 0), Direction.DOWN, Direction.UP),
            (GemInfo(0, 0, 0), GemInfo(0, 0, 1), Direction.UP, Direction.DOWN),
        ],
    )
    def test_prepare_swap(
        self,
        first_gem: GemInfo,
        second_gem: GemInfo,
        first_direction: Direction,
        second_direction: Direction,
    ):
        first_gem.prepare_swap(second_gem)

        assert first_gem.direction == first_direction
        assert second_gem.direction == second_direction

    @pytest.mark.parametrize(
        "first_gem,second_gem",
        [
            (GemInfo(0, 0, 0), GemInfo(0, 0, 0)),
            (GemInfo(0, 1, 1), GemInfo(0, 1, 5)),
            (GemInfo(0, 1, 1), GemInfo(0, 2, 2)),
        ],
    )
    def test_invalid_swap(self, first_gem: GemInfo, second_gem: GemInfo):
        with pytest.raises(ValueError):
            first_gem.prepare_swap(second_gem)
