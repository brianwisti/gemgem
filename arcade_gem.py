"""An Arcade implementation of the Gemgem (Bejeweled clone) game."""

import copy
import logging
import random
from dataclasses import dataclass
from enum import Enum

import arcade
from rich.logging import RichHandler
from arcade import color

logging.basicConfig(
    level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)


# Start with simple square boards
BOARD_WIDTH = 8
BOARD_HEIGHT = 8
GEM_COUNT = 7
GEM_IMAGE_SIZE = 64
# The amount of space to the sides of the board to the edge of the window
# is used several times, so calculate it once here and store in variables.
BOARD_MARGIN = 5
WINDOW_HEIGHT = (GEM_IMAGE_SIZE + BOARD_MARGIN) * BOARD_HEIGHT + BOARD_MARGIN
WINDOW_WIDTH = (GEM_IMAGE_SIZE + BOARD_MARGIN) * BOARD_WIDTH + BOARD_MARGIN

# colors for the board
COLOR_GRID = color.BLACK_BEAN
COLOR_EMPTY_SQUARE = color.WHITE_SMOKE
COLOR_SELECTED_SQUARE = color.GRAPE

# Identifies squares without a gem.
EMPTY_SPACE = -1


# Arbitrary noninteger representing above the board
ROW_ABOVE_BOARD = "row above board"

GameBoard = list[list[int]]
EMPTY_ROW: list[list] = [[]] * BOARD_WIDTH

# constants for direction values
Direction = Enum("Direction", ["UP", "DOWN", "LEFT", "RIGHT"])


@dataclass
class GemInfo:
    """Describes a single gem and its movement."""

    image_num: int
    x: int
    y: int
    direction: Direction


GemList = list[GemInfo]


class GemGame(arcade.Window):
    """Our custom game Window."""

    board: GameBoard
    score: int

    def __init__(self):
        """Initialize the game window."""
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, "Gem Game")
        # Holds our gem images.
        self.score = 0
        self.board = get_blank_board()
        arcade.set_background_color(color.AMAZON)

    def on_draw(self):
        """Render the current frame."""
        arcade.start_render()
        assert self.board

        drop_slots = get_drop_slots(self.board)

        while drop_slots != EMPTY_ROW:
            logging.info("drop slots: %s", drop_slots)
            moving_gems = get_dropping_gems(self.board)
            logging.info("moving gems: %s", moving_gems)

            for index, drop_slot in enumerate(drop_slots):
                if drop_slot:
                    # cause the lowest gem in each slot to begin moving in the DOWN direction
                    moving_gems.append(
                        GemInfo(
                            image_num=drop_slot[0],
                            x=index,
                            y=ROW_ABOVE_BOARD,
                            direction=Direction.DOWN,
                        )
                    )

            board_copy = get_board_copy_minus_gems(self.board, moving_gems)
            logging.debug("board copy: %s", board_copy)

            logging.warning("render gems here")
            move_gems(self.board, moving_gems)

            # Make the next row of gems from the drop slots
            # the lowest by deleting the previous lowest gems.
            for x, drop_slot in enumerate(drop_slots):
                if len(drop_slot) == 0:
                    continue

                self.board[x][0] = drop_slot[0]
                del drop_slots[x][0]

        board_sprites = arcade.SpriteList()
        for row in range(BOARD_HEIGHT):
            for column in range(BOARD_WIDTH):
                x = (
                    (BOARD_MARGIN + GEM_IMAGE_SIZE) * column
                    + BOARD_MARGIN
                    + GEM_IMAGE_SIZE // 2
                )
                y = (
                    (BOARD_MARGIN + GEM_IMAGE_SIZE) * row
                    + BOARD_MARGIN
                    + GEM_IMAGE_SIZE // 2
                )

                this_value = self.board[row][column]

                if this_value == EMPTY_SPACE:
                    sprite = arcade.SpriteSolidColor(
                        GEM_IMAGE_SIZE, GEM_IMAGE_SIZE, COLOR_EMPTY_SQUARE
                    )
                else:
                    sprite = arcade.Sprite(f"./gem{this_value}.png")

                sprite.center_x = x
                sprite.center_y = y
                board_sprites.append(sprite)

        board_sprites.draw()

    def on_mouse_press(self, x, y, button, modifiers):
        """Called when the user presses a mouse button."""
        assert self.board

        # Change the x/y screen coordinates to grid coordinates
        column = x // (GEM_IMAGE_SIZE + BOARD_MARGIN)
        row = y // (GEM_IMAGE_SIZE + BOARD_MARGIN)

        logging.info(
            "Click coordinates: (%s, %s). Grid coordinats: (%s, %s)", x, y, row, column
        )


def get_blank_board() -> GameBoard:
    """Create and return a blank board data structure."""
    return [[EMPTY_SPACE for _ in range(BOARD_HEIGHT)] for _ in range(BOARD_WIDTH)]


def get_drop_slots(board: GameBoard):
    """
    Creates a "drop slot" for each column, filled with a number of gems that that column is lacking.

    This function assumes that the gems have been gravity dropped already.
    """
    assert board

    board_copy = copy.deepcopy(board)

    for x in range(BOARD_WIDTH):
        gems_in_column = []

        for y in range(BOARD_HEIGHT):
            if board_copy[x][y] != EMPTY_SPACE:
                gems_in_column.append(board_copy[x][y])

        board_copy[x] = (
            [EMPTY_SPACE] * (BOARD_HEIGHT - len(gems_in_column))
        ) + gems_in_column

    drop_slots: GameBoard = [[] for _ in range(BOARD_WIDTH)]

    # count the number of empty spaces in each column on the board
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT - 1, -1, -1):  # start from bottom, going up
            if board[x][y] == EMPTY_SPACE:
                possible_gems = list(range(1, GEM_COUNT + 1))
                offsets = ((0, -1), (1, 0), (0, 1), (-1, 0))

                for offset_x, offset_y in offsets:
                    # Narrow down the possible gems we should put in the
                    # blank space so we don't end up putting an two of
                    # the same gems next to each other when they drop.
                    neighbor_gem = get_gem_at(
                        board_copy,
                        x + offset_x,
                        y + offset_y,
                    )

                    if neighbor_gem is not None and neighbor_gem in possible_gems:
                        possible_gems.remove(neighbor_gem)

                new_gem = random.choice(possible_gems)
                board_copy[x][y] = new_gem
                drop_slots[x].append(new_gem)

    return drop_slots


def get_gem_at(board: GameBoard, x: int, y: int):
    """Return the gem image number stored at the given x, y coordinates of the board."""
    if 0 < x < BOARD_WIDTH and 0 < y < BOARD_HEIGHT:
        logging.info("get_gem_at(): (%s, %s) → %s", x, y, board[x][y])
        return board[x][y]

    logging.warning("get_gem_at(): (%s, %s) -> out of bounds", x, y)
    return None


def get_dropping_gems(board: GameBoard) -> GemList:
    """Find all the gems that have an empty space below them"""
    board_copy = copy.deepcopy(board)
    dropping_gems = []

    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT - 2, -1, -1):
            if board_copy[x][y + 1] == EMPTY_SPACE and board_copy[x][y] != EMPTY_SPACE:
                # This space drops if not empty but the space below it is
                dropping_gems.append(
                    GemInfo(
                        image_num=board_copy[x][y],
                        x=x,
                        y=y,
                        direction=Direction.DOWN,
                    )
                )
                board_copy[x][y] = EMPTY_SPACE

    return dropping_gems


def get_board_copy_minus_gems(board: GameBoard, gems: GemList):
    """Returns a copy of the passed board data structure without the gems in the "gems" list."""
    #
    # Gems is a list of dicts, with keys x, y, direction, image_num

    board_copy = copy.deepcopy(board)

    # Remove some of the gems from this board data structure copy.
    for gem in gems:
        if gem.y != ROW_ABOVE_BOARD:
            board_copy[gem.x][gem.y] = EMPTY_SPACE

    return board_copy


def move_gems(board: GameBoard, moving_gems: GemList):
    """Moves the gems on the board based on their direction property"""
    # movingGems is a list of dicts with keys x, y, direction, image_num
    for gem in moving_gems:
        if gem.y != ROW_ABOVE_BOARD:
            board[gem.x][gem.y] = EMPTY_SPACE
            movex = 0
            movey = 0

            if gem.direction == Direction.LEFT:
                movex = -1
            elif gem.direction == Direction.RIGHT:
                movex = 1
            elif gem.direction == Direction.DOWN:
                movey = 1
            elif gem.direction == Direction.UP:
                movey = -1

            board[gem.x + movex][gem.y + movey] = gem.image_num
        else:
            # gem is located above the board (where new gems come from)
            board[gem.x][0] = gem.image_num  # move to top row


def main():
    """Set up the game and run the main game loop."""
    window = GemGame()
    arcade.run()


if __name__ == "__main__":
    main()
