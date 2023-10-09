# Gemgem (a Bejeweled clone)
# By Brian Wisti brianwisti@pobox.com
# Based on code by Al Sweigart al@inventwithpython.com
# http://inventwithpython.com/pygame
# Released under a "Simplified BSD" license

"""
This program has "gem data structures", which are basically dictionaries
with the following keys:
  'x' and 'y' - The location of the gem on the board. 0,0 is the top left.
                There is also a ROWABOVEBOARD row that 'y' can be set to,
                to indicate that it is above the board.
  'direction' - one of the four constant variables UP, DOWN, LEFT, RIGHT.
                This is the direction the gem is moving.
  'imageNum'  - The integer index into GEMIMAGES to denote which image
                this gem uses.
"""

import copy
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

import pygame
from rich.logging import RichHandler

logging.basicConfig(
    level="INFO", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)

FPS = 30  # frames per second to update the screen
WINDOW_WIDTH = 600  # width of the program's window, in pixels
WINDOW_HEIGHT = 600  # height in pixels

BOARD_WIDTH = 8  # how many columns in the board
BOARD_HEIGHT = 8  # how many rows in the board
GEM_IMAGE_SIZE = 64  # width & height of each space in pixels

# NUMGEMIMAGES is the number of gem types. You will need .png image
# files named gem0.png, gem1.png, etc. up to gem(N-1).png.
NUM_GEM_IMAGES = 7
assert NUM_GEM_IMAGES >= 5  # game needs at least 5 types of gems to work

# NUMMATCHSOUNDS is the number of different sounds to choose from when
# a match is made. The .wav files are named match0.wav, match1.wav, etc.
NUM_MATCH_SOUNDS = 6

MOVE_RATE = 25  # 1 to 100, larger num means faster animations
DEDUCT_SPEED = 0.8  # reduces score by 1 point every DEDUCTSPEED seconds.

#             R    G    B
PURPLE = (255, 0, 255)
LIGHTBLUE = (170, 190, 255)
BLUE = (0, 0, 255)
RED = (255, 100, 100)
BLACK = (0, 0, 0)
BROWN = (85, 65, 0)
HIGHLIGHTCOLOR = PURPLE  # color of the selected gem's border
BGCOLOR = LIGHTBLUE  # background color on the screen
GRIDCOLOR = BLUE  # color of the game board
GAMEOVERCOLOR = RED  # color of the "Game over" text.
GAMEOVERBGCOLOR = BLACK  # background color of the "Game over" text.
SCORECOLOR = BROWN  # color of the text for the player's score

# The amount of space to the sides of the board to the edge of the window
# is used several times, so calculate it once here and store in variables.
XMARGIN = int((WINDOW_WIDTH - GEM_IMAGE_SIZE * BOARD_WIDTH) / 2)
YMARGIN = int((WINDOW_HEIGHT - GEM_IMAGE_SIZE * BOARD_HEIGHT) / 2)


EMPTY_SPACE = -1  # an arbitrary, nonpositive value
ROW_ABOVE_BOARD = BOARD_HEIGHT + 1

# constants for direction values
Direction = Enum("Direction", ["UP", "DOWN", "LEFT", "RIGHT"])
BoardRects = list[list[pygame.Rect]]
ImageList = list[pygame.Surface]
Position = tuple[int, int]


@dataclass
class GemInfo:
    """Describes a single gem and its movement."""

    image_num: int
    x: int
    y: int
    direction: Direction = Direction.DOWN

    def is_adjacent_to(self, other: "GemInfo"):
        """
        Return True if adjacent to other gem.

        A gem is adjacent if it is directly above, below, left, or right of the other gem.

        Raises a ValueError when two gems occupy the same space.
        """

        if self.x == other.x and self.y == other.y:
            return False

        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5 <= 1

    def prepare_swap(self, other: "GemInfo"):
        """Set each gem's direction to swap locations."""

        if not self.is_adjacent_to(other):
            raise ValueError("Gems must be adjacent")

        if self.x > other.x and self.y == other.y:
            self.direction = Direction.LEFT
            other.direction = Direction.RIGHT
        elif self.x < other.x and self.y == other.y:
            self.direction = Direction.RIGHT
            other.direction = Direction.LEFT
        elif self.x == other.x and self.y < other.y:
            self.direction = Direction.UP
            other.direction = Direction.DOWN
        elif self.x == other.x and self.y > other.y:
            self.direction = Direction.DOWN
            other.direction = Direction.UP


GemList = Sequence[GemInfo]


@dataclass
class GameBoard:
    """Manages location and relations of gems on the board."""

    squares: list[list[int]] = field(default_factory=list)

    def __post_init__(self):
        """Fill squares if needed."""
        if not self.squares:
            self.squares = [[EMPTY_SPACE] * BOARD_HEIGHT for _ in range(BOARD_WIDTH)]

    def __getitem__(self, index: int):
        """Return first level of indexed values"""
        return self.squares[index]

    def __setitem__(self, index: int, value: list[int]):
        """Assign first level of indexed values."""
        self.squares[index] = value

    def can_make_move(self):
        """Return True if the board is in a state where a matching move can be made on it."""

        # The patterns in oneOffPatterns represent gems that are configured
        # in a way where it only takes one move to make a triplet.
        one_off_patterns = (
            ((0, 1), (1, 0), (2, 0)),
            ((0, 1), (1, 1), (2, 0)),
            ((0, 0), (1, 1), (2, 0)),
            ((0, 1), (1, 0), (2, 1)),
            ((0, 0), (1, 0), (2, 1)),
            ((0, 0), (1, 1), (2, 1)),
            ((0, 0), (0, 2), (0, 3)),
            ((0, 0), (0, 1), (0, 3)),
        )

        # The x and y variables iterate over each space on the board.
        # If we use + to represent the currently iterated space on the
        # board, then this pattern: ((0,1), (1,0), (2,0))refers to identical
        # gems being set up like this:
        #
        #     +A
        #     B
        #     C
        #
        # That is, gem A is offset from the + by (0,1), gem B is offset
        # by (1,0), and gem C is offset by (2,0). In this case, gem A can
        # be swapped to the left to form a vertical three-in-a-row triplet.
        #
        # There are eight possible ways for the gems to be one move
        # away from forming a triple, hence oneOffPattern has 8 patterns.

        for x in range(BOARD_WIDTH):
            for y in range(BOARD_HEIGHT):
                for pat in one_off_patterns:
                    # check each possible pattern of "match in next move" to
                    # see if a possible move can be made.
                    if (
                        self.get_gem_at(x + pat[0][0], y + pat[0][1])
                        == self.get_gem_at(x + pat[1][0], y + pat[1][1])
                        == self.get_gem_at(x + pat[2][0], y + pat[2][1])
                        != None
                    ) or (
                        self.get_gem_at(x + pat[0][1], y + pat[0][0])
                        == self.get_gem_at(x + pat[1][1], y + pat[1][0])
                        == self.get_gem_at(x + pat[2][1], y + pat[2][0])
                        != None
                    ):
                        return True  # return True the first time you find a pattern
        return False

    def find_matching_gems(self):
        """Find sets of three or more matching gems and return them in a list."""
        gems_to_remove = (
            []
        )  # a list of lists of gems in matching triplets that should be removed
        board_copy = copy.deepcopy(self)

        # loop through each space, checking for 3 adjacent identical gems
        for x in range(BOARD_WIDTH):
            for y in range(BOARD_HEIGHT):
                # look for horizontal matches
                if (
                    self.get_gem_at(x, y)
                    == self.get_gem_at(x + 1, y)
                    == self.get_gem_at(x + 2, y)
                    and self.get_gem_at(x, y) != EMPTY_SPACE
                ):
                    target_gem = board_copy[x][y]
                    offset = 0
                    remove_set = []

                    while self.get_gem_at(x + offset, y) == target_gem:
                        # keep checking if there's more than 3 gems in a row
                        remove_set.append((x + offset, y))
                        board_copy[x + offset][y] = EMPTY_SPACE
                        offset += 1

                    gems_to_remove.append(remove_set)

                # look for vertical matches
                if (
                    self.get_gem_at(x, y)
                    == self.get_gem_at(x, y + 1)
                    == self.get_gem_at(x, y + 2)
                    and self.get_gem_at(x, y) != EMPTY_SPACE
                ):
                    target_gem = board_copy[x][y]
                    offset = 0
                    remove_set = []

                    while self.get_gem_at(x, y + offset) == target_gem:
                        # keep checking, in case there's more than 3 gems in a row
                        remove_set.append((x, y + offset))
                        board_copy[x][y + offset] = EMPTY_SPACE
                        offset += 1

                    gems_to_remove.append(remove_set)

        return gems_to_remove

    def get_board_copy_minus_gems(self, gems: GemList):
        """
        Returns a copy of the passed board data structure without the gems in the "gems" list.
        """
        #
        # Gems is a list of dicts, with keys x, y, direction, imageNum

        board_copy = copy.deepcopy(self)

        # Remove some of the gems from this board data structure copy.
        for gem in gems:
            if gem.y != ROW_ABOVE_BOARD:
                board_copy[gem.x][gem.y] = EMPTY_SPACE

        return board_copy

    def get_drop_slots(self, gem_images: ImageList):
        """
        Creates a "drop slot" for each column, filled with gems that the column is lacking.

        This function assumes that the gems have been gravity dropped already.
        """
        board_copy = copy.deepcopy(self)
        board_copy.pull_down_all_gems()
        drop_slots: list[list[int]] = []

        for _ in range(BOARD_WIDTH):
            drop_slots.append([])

        # count the number of empty spaces in each column on the board
        for x in range(BOARD_WIDTH):
            for y in range(BOARD_HEIGHT - 1, -1, -1):  # start from bottom, going up
                if board_copy[x][y] == EMPTY_SPACE:
                    possible_gems = list(range(len(gem_images)))
                    for offset_x, offset_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                        # Narrow down the possible gems we should put in the
                        # blank space so we don't end up putting an two of
                        # the same gems next to each other when they drop.
                        neighbor_gem = self.get_gem_at(x + offset_x, y + offset_y)
                        if neighbor_gem is not None and neighbor_gem in possible_gems:
                            possible_gems.remove(neighbor_gem)

                    new_gem = random.choice(possible_gems)
                    board_copy[x][y] = new_gem
                    drop_slots[x].append(new_gem)

        return drop_slots

    def get_dropping_gems(self):
        """Find all the gems that have an empty space below them"""
        board_copy = copy.deepcopy(self)
        dropping_gems = []

        for x in range(BOARD_WIDTH):
            for y in range(BOARD_HEIGHT - 2, -1, -1):
                if (
                    board_copy[x][y + 1] == EMPTY_SPACE
                    and board_copy[x][y] != EMPTY_SPACE
                ):
                    # This space drops if not empty but the space below it is
                    dropping_gems.append(GemInfo(image_num=board_copy[x][y], x=x, y=y))
                    board_copy[x][y] = EMPTY_SPACE

        return dropping_gems

    def get_gem_at(self, x: int, y: int):
        """Return the gem image number stored at the given x, y coordinates of the board."""
        if x < 0 or y < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
            return None

        return self.squares[x][y]

    def get_swapping_gems(self, first_x_y, second_x_y):
        """Check if the gems are adjacent and can be swapped"""
        # If the gems at the (X, Y) coordinates of the two gems are adjacent,
        # then their 'direction' keys are set to the appropriate direction
        # value to be swapped with each other.
        # Otherwise, (None, None) is returned.
        first_gem = GemInfo(
            image_num=self.squares[first_x_y["x"]][first_x_y["y"]],
            x=first_x_y["x"],
            y=first_x_y["y"],
        )
        second_gem = GemInfo(
            image_num=self.squares[second_x_y["x"]][second_x_y["y"]],
            x=second_x_y["x"],
            y=second_x_y["y"],
        )

        if first_gem.is_adjacent_to(second_gem):
            first_gem.prepare_swap(second_gem)
            return first_gem, second_gem

        # These gems are not adjacent and can't be swapped.
        return None, None

    def move_gems(self, moving_gems: GemList):
        """Moves the gems on the board based on their direction property"""
        # movingGems is a list of dicts with keys x, y, direction, imageNum
        for gem in moving_gems:
            if gem.y != ROW_ABOVE_BOARD:
                self.squares[gem.x][gem.y] = EMPTY_SPACE
                move_x = 0
                move_y = 0

                if gem.direction == Direction.LEFT:
                    move_x = -1
                elif gem.direction == Direction.RIGHT:
                    move_x = 1
                elif gem.direction == Direction.DOWN:
                    move_y = 1
                elif gem.direction == Direction.UP:
                    move_y = -1

                self.squares[gem.x + move_x][gem.y + move_y] = gem.image_num
            else:
                # gem is located above the board (where new gems come from)
                self.squares[gem.x][0] = gem.image_num  # move to top row

    def pull_down_all_gems(self):
        """pulls down gems on the board to the bottom to fill in any gaps"""
        for x in range(BOARD_WIDTH):
            gems_in_column = []

            for y in range(BOARD_HEIGHT):
                if self.squares[x][y] != EMPTY_SPACE:
                    gems_in_column.append(self.squares[x][y])
            self.squares[x] = (
                [EMPTY_SPACE] * (BOARD_HEIGHT - len(gems_in_column))
            ) + gems_in_column


@dataclass
class GameSession:
    """Tracks score and status of current game."""

    score: int = 0
    game_is_over: bool = False
    board: GameBoard = field(default_factory=GameBoard)
    first_selected_gem: dict[str, int] | None = None
    clicked_space: dict[str, int] | None = None

    def end_game_if_stuck(self):
        """Mark this game as over if there are no moves on the board."""
        if not self.board.can_make_move():
            self.game_is_over = True


@dataclass
class GameSounds:
    """Knows what sounds to play for particular situations."""

    bad_swap: pygame.mixer.Sound = field(init=False)
    match: Sequence[pygame.mixer.Sound] = field(init=False, default_factory=list)

    def __post_init__(self):
        self.bad_swap = pygame.mixer.Sound("badswap.wav")
        # Load game sounds.
        self.match = [
            pygame.mixer.Sound(f"match{i}.wav") for i in range(NUM_MATCH_SOUNDS)
        ]


@dataclass
class GemGame:
    """Manages drawing the game itself."""

    fps_clock: pygame.time.Clock = field(init=False, default_factory=pygame.time.Clock)
    display_surf: pygame.Surface = field(init=False)
    basic_font: pygame.font.Font = field(init=False)
    gem_images: list[pygame.Surface] = field(init=False, default_factory=list)
    game_sounds: GameSounds = field(init=False, default_factory=GameSounds)
    board_rects: BoardRects = field(init=False, default_factory=list)
    last_mouse_down: tuple[int, int] | None = None

    def __post_init__(self):
        """Initialize fields."""
        self.display_surf = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.basic_font = pygame.font.Font("freesansbold.ttf", 36)

        # Load gem images.
        session_image_files: set[str] = set()
        available_images = os.listdir("assets/images")

        while len(session_image_files) < NUM_GEM_IMAGES:
            session_image_files.add(random.choice(available_images))

        logging.info("session image files: %s", session_image_files)

        for image_file in session_image_files:
            gem_image = pygame.image.load(f"assets/images/{image_file}")

            if gem_image.get_size() != (GEM_IMAGE_SIZE, GEM_IMAGE_SIZE):
                gem_image = pygame.transform.smoothscale(
                    gem_image, (GEM_IMAGE_SIZE, GEM_IMAGE_SIZE)
                )

            self.gem_images.append(gem_image)

        # Create pygame.Rect objects for each board space to
        # do board-coordinate-to-pixel-coordinate conversions.
        self.board_rects = []

        for x in range(BOARD_WIDTH):
            self.board_rects.append([])

            for y in range(BOARD_HEIGHT):
                rect = pygame.Rect(
                    (
                        XMARGIN + (x * GEM_IMAGE_SIZE),
                        YMARGIN + (y * GEM_IMAGE_SIZE),
                        GEM_IMAGE_SIZE,
                        GEM_IMAGE_SIZE,
                    )
                )
                self.board_rects[x].append(rect)

    def animate_moving_gems(
        self,
        board: GameBoard,
        gems: GemList,
        points_text,
        score: int,
    ):
        """Animates the moving gems and points text on the board"""
        # pointsText is a dictionary with keys 'x', 'y', and 'points'
        progress = 0  # progress at 0 represents beginning, 100 means finished.

        while progress < 100:  # animation loop
            self.display_surf.fill(BGCOLOR)
            self.draw_board(board)

            for gem in gems:  # Draw each gem.
                self.draw_moving_gem(gem, progress)

            self.draw_score(score)

            for point_text in points_text:
                points_surf = self.basic_font.render(
                    str(point_text["points"]), 1, SCORECOLOR
                )
                points_rect = points_surf.get_rect()
                points_rect.center = (point_text["x"], point_text["y"])
                self.display_surf.blit(points_surf, points_rect)

            pygame.display.update()
            self.fps_clock.tick(FPS)
            progress += MOVE_RATE

    def draw_board(self, board: GameBoard):
        """Draws the gems on the board using the board data structure."""
        for x in range(BOARD_WIDTH):
            for y in range(BOARD_HEIGHT):
                pygame.draw.rect(
                    self.display_surf, GRIDCOLOR, self.board_rects[x][y], 1
                )
                gem_to_draw = board[x][y]

                if gem_to_draw != EMPTY_SPACE:
                    self.display_surf.blit(
                        self.gem_images[gem_to_draw], self.board_rects[x][y]
                    )

    def draw_moving_gem(self, gem: GemInfo, progress):
        """
        Draw a gem sliding in the direction that its 'direction' key indicates.

        The progress parameter is a number from 0 (just starting) to 100 (slide complete).
        """
        movex = 0
        movey = 0
        progress *= 0.01

        if gem.direction == Direction.UP:
            movey = -int(progress * GEM_IMAGE_SIZE)
        elif gem.direction == Direction.DOWN:
            movey = int(progress * GEM_IMAGE_SIZE)
        elif gem.direction == Direction.RIGHT:
            movex = int(progress * GEM_IMAGE_SIZE)
        elif gem.direction == Direction.LEFT:
            movex = -int(progress * GEM_IMAGE_SIZE)

        basex = gem.x
        basey = gem.y

        if basey == ROW_ABOVE_BOARD:
            basey = -1

        pixelx = XMARGIN + (basex * GEM_IMAGE_SIZE)
        pixely = YMARGIN + (basey * GEM_IMAGE_SIZE)
        rect = pygame.Rect(
            (pixelx + movex, pixely + movey, GEM_IMAGE_SIZE, GEM_IMAGE_SIZE)
        )
        self.display_surf.blit(self.gem_images[gem.image_num], rect)

    def draw_score(self, score):
        """Draws the score text in the lower left corner of the screen."""
        score_img = self.basic_font.render(str(score), 1, SCORECOLOR)
        score_rect = score_img.get_rect()
        score_rect.bottomleft = (10, WINDOW_HEIGHT - 6)
        self.display_surf.blit(score_img, score_rect)

    def fill_board_and_animate(self, board: GameBoard, points, score):
        """
        Fills the board with gems and animates their placement using existing animation functions.
        """
        drop_slots = board.get_drop_slots(self.gem_images)

        while drop_slots != [[]] * BOARD_WIDTH:
            # do the dropping animation as long as there are more gems to drop
            moving_gems = board.get_dropping_gems()

            for x, drop_slot in enumerate(drop_slots):
                if len(drop_slot) != 0:
                    # cause the lowest gem in each slot to begin moving in the DOWN direction
                    moving_gems.append(
                        GemInfo(
                            image_num=drop_slot[0],
                            x=x,
                            y=ROW_ABOVE_BOARD,
                        )
                    )

            board_copy = board.get_board_copy_minus_gems(moving_gems)
            self.animate_moving_gems(
                board_copy,
                moving_gems,
                points,
                score,
            )
            board.move_gems(moving_gems)

            # Make the next row of gems from the drop slots
            # the lowest by deleting the previous lowest gems.
            for x, drop_slot in enumerate(drop_slots):
                if len(drop_slot) == 0:
                    continue

                board[x][0] = drop_slot[0]
                del drop_slots[x][0]

    def highlight_space(self, x: int, y: int):
        """Highlights the space at the given x,y board coordinates"""
        pygame.draw.rect(self.display_surf, HIGHLIGHTCOLOR, self.board_rects[x][y], 4)


def main():
    """Initialize the game and start the main game loop."""

    # Initial set up.
    pygame.init()
    gem_game = GemGame()
    pygame.display.set_caption("Gemgem")

    while True:
        run_game(gem_game)


def run_game(gem_game: GemGame):
    """Plays through a single game. When the game is over, this function returns."""

    # initalize the session
    session = GameSession()
    gem_game.fill_board_and_animate(
        session.board, [], session.score
    )  # Drop the initial gems.

    # initialize variables for the start of a new game
    last_score_deduction = time.time()
    click_continue_text_surf = None

    while True:  # main game loop
        session.clicked_space = None

        for event in pygame.event.get():  # event handling loop
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE
            ):
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYUP and event.key == pygame.K_BACKSPACE:
                return  # start a new game

            elif event.type == pygame.MOUSEBUTTONUP:
                if session.game_is_over:
                    return  # after games ends, click to start a new game

                if event.pos == gem_game.last_mouse_down:
                    # This event is a mouse click, not the end of a mouse drag.
                    session.clicked_space = check_for_gem_click(
                        event.pos, gem_game.board_rects
                    )
                elif gem_game.last_mouse_down:
                    # this is the end of a mouse drag
                    session.first_selected_gem = check_for_gem_click(
                        gem_game.last_mouse_down, gem_game.board_rects
                    )
                    session.clicked_space = check_for_gem_click(
                        event.pos, gem_game.board_rects
                    )

                    if not session.first_selected_gem or not session.clicked_space:
                        # if not part of a valid drag, deselect both
                        session.first_selected_gem = None
                        session.clicked_space = None
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # this is the start of a mouse click or mouse drag
                gem_game.last_mouse_down = event.pos

        if session.clicked_space and not session.first_selected_gem:
            # This was the first gem clicked on.
            session.first_selected_gem = session.clicked_space
        elif session.clicked_space and session.first_selected_gem:
            # Two gems have been clicked on and selected. Swap the gems.
            first_swapping_gem, second_swapping_gem = session.board.get_swapping_gems(
                session.first_selected_gem, session.clicked_space
            )

            if first_swapping_gem is None and second_swapping_gem is None:
                # If both are None, then the gems were not adjacent
                session.first_selected_gem = None  # deselect the first gem
                continue

            # Show the swap animation on the screen.
            board_copy = session.board.get_board_copy_minus_gems(
                (first_swapping_gem, second_swapping_gem)
            )
            gem_game.animate_moving_gems(
                board_copy,
                [first_swapping_gem, second_swapping_gem],
                [],
                session.score,
            )

            assert first_swapping_gem
            assert second_swapping_gem
            # Swap the gems in the board data structure.
            session.board[first_swapping_gem.x][
                first_swapping_gem.y
            ] = second_swapping_gem.image_num
            session.board[second_swapping_gem.x][
                second_swapping_gem.y
            ] = first_swapping_gem.image_num

            # See if this is a matching move.
            matched_gems = session.board.find_matching_gems()

            if not matched_gems:
                # Was not a matching move; swap the gems back
                gem_game.game_sounds.bad_swap.play()
                gem_game.animate_moving_gems(
                    board_copy,
                    [first_swapping_gem, second_swapping_gem],
                    [],
                    session.score,
                )
                session.board[first_swapping_gem.x][
                    first_swapping_gem.y
                ] = second_swapping_gem.image_num
                session.board[second_swapping_gem.x][
                    second_swapping_gem.y
                ] = first_swapping_gem.image_num
            else:
                # This was a matching move.
                score_add = 0

                while matched_gems:
                    # Remove matched gems, then pull down the board.

                    # points is a list of dicts that tells fillBoardAndAnimate()
                    # where on the screen to display text to show how many
                    # points the player got. points is a list because if
                    # the playergets multiple matches, then multiple points text should appear.
                    points = []
                    gem = None

                    for gem_set in matched_gems:
                        score_add += 10 + (len(gem_set) - 3) * 10

                        for gem in gem_set:
                            session.board[gem[0]][gem[1]] = EMPTY_SPACE

                        if gem:
                            points.append(
                                {
                                    "points": score_add,
                                    "x": gem[0] * GEM_IMAGE_SIZE + XMARGIN,
                                    "y": gem[1] * GEM_IMAGE_SIZE + YMARGIN,
                                }
                            )
                    random.choice(gem_game.game_sounds.match).play()
                    session.score += score_add

                    # Drop the new gems.
                    gem_game.fill_board_and_animate(
                        session.board, points, session.score
                    )

                    # Check if there are any new matches.
                    matched_gems = session.board.find_matching_gems()

            session.first_selected_gem = None
            session.end_game_if_stuck()

        # Draw the board.
        gem_game.display_surf.fill(BGCOLOR)
        gem_game.draw_board(session.board)

        if session.first_selected_gem is not None:
            gem_game.highlight_space(
                session.first_selected_gem["x"], session.first_selected_gem["y"]
            )

        if session.game_is_over:
            if click_continue_text_surf is None:
                # Only render the text once. In future iterations, just
                # use the Surface object already in clickContinueTextSurf
                click_continue_text_surf = gem_game.basic_font.render(
                    f"Final Score: {session.score} (Click to continue)",
                    1,
                    GAMEOVERCOLOR,
                    GAMEOVERBGCOLOR,
                )
                click_continue_text_rect = click_continue_text_surf.get_rect()
                click_continue_text_rect.center = int(WINDOW_WIDTH / 2), int(
                    WINDOW_HEIGHT / 2
                )

            gem_game.display_surf.blit(
                click_continue_text_surf, click_continue_text_rect
            )
        elif session.score > 0 and time.time() - last_score_deduction > DEDUCT_SPEED:
            # score drops over time
            session.score -= 1
            last_score_deduction = time.time()

        gem_game.draw_score(session.score)
        pygame.display.update()
        gem_game.fps_clock.tick(FPS)


def check_for_gem_click(pos: Position, board_rects: BoardRects):
    """See if the mouse click was on the board"""
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if board_rects[x][y].collidepoint(pos[0], pos[1]):
                return {"x": x, "y": y}

    return None  # Click was not on the board.


if __name__ == "__main__":
    main()
