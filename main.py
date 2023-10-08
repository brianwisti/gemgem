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
import random
import sys
import time
from enum import Enum

import pygame
from pygame.locals import *

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

# constants for direction values
Direction = Enum("Direction", ["UP", "DOWN", "LEFT", "RIGHT"])

EMPTY_SPACE = -1  # an arbitrary, nonpositive value
ROW_ABOVE_BOARD = "row above board"  # an arbitrary, noninteger value


def main():
    """Initialize the game and start the main game loop."""
    global FPSCLOCK, DISPLAYSURF, GEM_IMAGES, GAME_SOUNDS, BASICFONT, BOARDRECTS

    # Initial set up.
    pygame.init()
    FPSCLOCK = pygame.time.Clock()
    DISPLAYSURF = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Gemgem")
    BASICFONT = pygame.font.Font("freesansbold.ttf", 36)

    # Load the images
    GEM_IMAGES = []

    for i in range(1, NUM_GEM_IMAGES + 1):
        gem_image = pygame.image.load(f"gem{i}.png")

        if gem_image.get_size() != (GEM_IMAGE_SIZE, GEM_IMAGE_SIZE):
            gem_image = pygame.transform.smoothscale(
                gem_image, (GEM_IMAGE_SIZE, GEM_IMAGE_SIZE)
            )

        GEM_IMAGES.append(gem_image)

    # Load the sounds.
    GAME_SOUNDS = {}
    GAME_SOUNDS["bad swap"] = pygame.mixer.Sound("badswap.wav")
    GAME_SOUNDS["match"] = []

    for i in range(NUM_MATCH_SOUNDS):
        GAME_SOUNDS["match"].append(pygame.mixer.Sound(f"match{i}.wav"))

    # Create pygame.Rect objects for each board space to
    # do board-coordinate-to-pixel-coordinate conversions.
    BOARDRECTS = []

    for x in range(BOARD_WIDTH):
        BOARDRECTS.append([])

        for y in range(BOARD_HEIGHT):
            r = pygame.Rect(
                (
                    XMARGIN + (x * GEM_IMAGE_SIZE),
                    YMARGIN + (y * GEM_IMAGE_SIZE),
                    GEM_IMAGE_SIZE,
                    GEM_IMAGE_SIZE,
                )
            )
            BOARDRECTS[x].append(r)

    while True:
        run_game()


def run_game():
    """Plays through a single game. When the game is over, this function returns."""

    # initalize the board
    game_board = get_blank_board()
    score = 0
    fill_board_and_animate(game_board, [], score)  # Drop the initial gems.

    # initialize variables for the start of a new game
    first_selected_gem = None
    last_mouse_down_x = None
    last_mouse_down_y = None
    game_is_over = False
    last_score_deduction = time.time()
    click_continue_text_surf = None

    while True:  # main game loop
        clicked_space = None
        for event in pygame.event.get():  # event handling loop
            if event.type == QUIT or (event.type == KEYUP and event.key == K_ESCAPE):
                pygame.quit()
                sys.exit()
            elif event.type == KEYUP and event.key == K_BACKSPACE:
                return  # start a new game

            elif event.type == MOUSEBUTTONUP:
                if game_is_over:
                    return  # after games ends, click to start a new game

                if event.pos == (last_mouse_down_x, last_mouse_down_y):
                    # This event is a mouse click, not the end of a mouse drag.
                    clicked_space = check_for_gem_click(event.pos)
                else:
                    # this is the end of a mouse drag
                    first_selected_gem = check_for_gem_click(
                        (last_mouse_down_x, last_mouse_down_y)
                    )
                    clicked_space = check_for_gem_click(event.pos)
                    if not first_selected_gem or not clicked_space:
                        # if not part of a valid drag, deselect both
                        first_selected_gem = None
                        clicked_space = None
            elif event.type == MOUSEBUTTONDOWN:
                # this is the start of a mouse click or mouse drag
                last_mouse_down_x, last_mouse_down_y = event.pos

        if clicked_space and not first_selected_gem:
            # This was the first gem clicked on.
            first_selected_gem = clicked_space
        elif clicked_space and first_selected_gem:
            # Two gems have been clicked on and selected. Swap the gems.
            first_swapping_gem, second_swapping_gem = get_swapping_gems(
                game_board, first_selected_gem, clicked_space
            )

            if first_swapping_gem is None and second_swapping_gem is None:
                # If both are None, then the gems were not adjacent
                first_selected_gem = None  # deselect the first gem
                continue

            # Show the swap animation on the screen.
            board_copy = get_board_copy_minus_gems(
                game_board, (first_swapping_gem, second_swapping_gem)
            )
            animate_moving_gems(
                board_copy, [first_swapping_gem, second_swapping_gem], [], score
            )

            assert first_swapping_gem
            assert second_swapping_gem
            # Swap the gems in the board data structure.
            game_board[first_swapping_gem["x"]][
                first_swapping_gem["y"]
            ] = second_swapping_gem["imageNum"]
            game_board[second_swapping_gem["x"]][
                second_swapping_gem["y"]
            ] = first_swapping_gem["imageNum"]

            # See if this is a matching move.
            matched_gems = find_matching_gems(game_board)
            if matched_gems == []:
                # Was not a matching move; swap the gems back
                GAME_SOUNDS["bad swap"].play()
                animate_moving_gems(
                    board_copy, [first_swapping_gem, second_swapping_gem], [], score
                )
                game_board[first_swapping_gem["x"]][
                    first_swapping_gem["y"]
                ] = first_swapping_gem["imageNum"]
                game_board[second_swapping_gem["x"]][
                    second_swapping_gem["y"]
                ] = second_swapping_gem["imageNum"]
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
                    for gem_set in matched_gems:
                        score_add += 10 + (len(gem_set) - 3) * 10

                        for gem in gem_set:
                            game_board[gem[0]][gem[1]] = EMPTY_SPACE

                        # Why are we referencing `gem` outside the loop?
                        points.append(
                            {
                                "points": score_add,
                                "x": gem[0] * GEM_IMAGE_SIZE + XMARGIN,
                                "y": gem[1] * GEM_IMAGE_SIZE + YMARGIN,
                            }
                        )
                    random.choice(GAME_SOUNDS["match"]).play()
                    score += score_add

                    # Drop the new gems.
                    fill_board_and_animate(game_board, points, score)

                    # Check if there are any new matches.
                    matched_gems = find_matching_gems(game_board)
            first_selected_gem = None

            if not can_make_move(game_board):
                game_is_over = True

        # Draw the board.
        DISPLAYSURF.fill(BGCOLOR)
        draw_board(game_board)

        if first_selected_gem is not None:
            highlight_space(first_selected_gem["x"], first_selected_gem["y"])

        if game_is_over:
            if click_continue_text_surf is None:
                # Only render the text once. In future iterations, just
                # use the Surface object already in clickContinueTextSurf
                click_continue_text_surf = BASICFONT.render(
                    f"Final Score: {score} (Click to continue)",
                    1,
                    GAMEOVERCOLOR,
                    GAMEOVERBGCOLOR,
                )
                click_continue_text_rect = click_continue_text_surf.get_rect()
                click_continue_text_rect.center = int(WINDOW_WIDTH / 2), int(
                    WINDOW_HEIGHT / 2
                )

            DISPLAYSURF.blit(click_continue_text_surf, click_continue_text_rect)
        elif score > 0 and time.time() - last_score_deduction > DEDUCT_SPEED:
            # score drops over time
            score -= 1
            last_score_deduction = time.time()
        draw_score(score)
        pygame.display.update()
        FPSCLOCK.tick(FPS)


def get_swapping_gems(board, first_x_y, second_x_y):
    """Check if the gems are adjacent and can be swapped"""
    # If the gems at the (X, Y) coordinates of the two gems are adjacent,
    # then their 'direction' keys are set to the appropriate direction
    # value to be swapped with each other.
    # Otherwise, (None, None) is returned.
    first_gem = {
        "imageNum": board[first_x_y["x"]][first_x_y["y"]],
        "x": first_x_y["x"],
        "y": first_x_y["y"],
    }
    second_gem = {
        "imageNum": board[second_x_y["x"]][second_x_y["y"]],
        "x": second_x_y["x"],
        "y": second_x_y["y"],
    }

    if first_gem["x"] == second_gem["x"] + 1 and first_gem["y"] == second_gem["y"]:
        first_gem["direction"] = Direction.LEFT
        second_gem["direction"] = Direction.RIGHT
    elif first_gem["x"] == second_gem["x"] - 1 and first_gem["y"] == second_gem["y"]:
        first_gem["direction"] = Direction.RIGHT
        second_gem["direction"] = Direction.LEFT
    elif first_gem["y"] == second_gem["y"] + 1 and first_gem["x"] == second_gem["x"]:
        first_gem["direction"] = Direction.UP
        second_gem["direction"] = Direction.DOWN
    elif first_gem["y"] == second_gem["y"] - 1 and first_gem["x"] == second_gem["x"]:
        first_gem["direction"] = Direction.DOWN
        second_gem["direction"] = Direction.UP
    else:
        # These gems are not adjacent and can't be swapped.
        return None, None
    return first_gem, second_gem


def get_blank_board():
    """Create and return a blank board data structure."""
    board = []

    for _ in range(BOARD_WIDTH):
        board.append([EMPTY_SPACE] * BOARD_HEIGHT)

    return board


def fill_board_and_animate(board, points, score):
    """Fills the board with gems and animates their placement using existing animation functions."""
    drop_slots = get_drop_slots(board)

    while drop_slots != [[]] * BOARD_WIDTH:
        # do the dropping animation as long as there are more gems to drop
        moving_gems = get_dropping_gems(board)

        for x, drop_slot in enumerate(drop_slots):
            if len(drop_slot) != 0:
                # cause the lowest gem in each slot to begin moving in the DOWN direction
                moving_gems.append(
                    {
                        "imageNum": drop_slot[0],
                        "x": x,
                        "y": ROW_ABOVE_BOARD,
                        "direction": Direction.DOWN,
                    }
                )

        board_copy = get_board_copy_minus_gems(board, moving_gems)
        animate_moving_gems(board_copy, moving_gems, points, score)
        move_gems(board, moving_gems)

        # Make the next row of gems from the drop slots
        # the lowest by deleting the previous lowest gems.
        for x, drop_slot in enumerate(drop_slots):
            if len(drop_slot) == 0:
                continue

            board[x][0] = drop_slot[0]
            del drop_slots[x][0]


def get_drop_slots(board):
    """Creates a "drop slot" for each column and fills the slot with a number of gems that that column is lacking.

    This function assumes that the gems have been gravity dropped already.
    """
    board_copy = copy.deepcopy(board)
    pull_down_all_gems(board_copy)

    drop_slots = []

    for _ in range(BOARD_WIDTH):
        drop_slots.append([])

    # count the number of empty spaces in each column on the board
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT - 1, -1, -1):  # start from bottom, going up
            if board_copy[x][y] == EMPTY_SPACE:
                possible_gems = list(range(len(GEM_IMAGES)))
                for offset_x, offset_y in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    # Narrow down the possible gems we should put in the
                    # blank space so we don't end up putting an two of
                    # the same gems next to each other when they drop.
                    neighbor_gem = get_gem_at(board_copy, x + offset_x, y + offset_y)
                    if neighbor_gem is not None and neighbor_gem in possible_gems:
                        possible_gems.remove(neighbor_gem)

                new_gem = random.choice(possible_gems)
                board_copy[x][y] = new_gem
                drop_slots[x].append(new_gem)

    return drop_slots


def pull_down_all_gems(board):
    """pulls down gems on the board to the bottom to fill in any gaps"""
    for x in range(BOARD_WIDTH):
        gems_in_column = []

        for y in range(BOARD_HEIGHT):
            if board[x][y] != EMPTY_SPACE:
                gems_in_column.append(board[x][y])
        board[x] = (
            [EMPTY_SPACE] * (BOARD_HEIGHT - len(gems_in_column))
        ) + gems_in_column


def can_make_move(board):
    """Return True if the board is in a state where a matching move can be made on it. Otherwise return False."""

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
                    get_gem_at(board, x + pat[0][0], y + pat[0][1])
                    == get_gem_at(board, x + pat[1][0], y + pat[1][1])
                    == get_gem_at(board, x + pat[2][0], y + pat[2][1])
                    != None
                ) or (
                    get_gem_at(board, x + pat[0][1], y + pat[0][0])
                    == get_gem_at(board, x + pat[1][1], y + pat[1][0])
                    == get_gem_at(board, x + pat[2][1], y + pat[2][0])
                    != None
                ):
                    return True  # return True the first time you find a pattern
    return False


def draw_moving_gem(gem, progress):
    """
    Draw a gem sliding in the direction that its 'direction' key indicates.

    The progress parameter is a number from 0 (just starting) to 100 (slide complete).
    """
    movex = 0
    movey = 0
    progress *= 0.01

    if gem["direction"] == Direction.UP:
        movey = -int(progress * GEM_IMAGE_SIZE)
    elif gem["direction"] == Direction.DOWN:
        movey = int(progress * GEM_IMAGE_SIZE)
    elif gem["direction"] == Direction.RIGHT:
        movex = int(progress * GEM_IMAGE_SIZE)
    elif gem["direction"] == Direction.LEFT:
        movex = -int(progress * GEM_IMAGE_SIZE)

    basex = gem["x"]
    basey = gem["y"]
    if basey == ROW_ABOVE_BOARD:
        basey = -1

    pixelx = XMARGIN + (basex * GEM_IMAGE_SIZE)
    pixely = YMARGIN + (basey * GEM_IMAGE_SIZE)
    r = pygame.Rect((pixelx + movex, pixely + movey, GEM_IMAGE_SIZE, GEM_IMAGE_SIZE))
    DISPLAYSURF.blit(GEM_IMAGES[gem["imageNum"]], r)


def get_gem_at(board, x, y):
    """Return the gem image number stored at the given x, y coordinates of the board."""
    if x < 0 or y < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
        return None
    else:
        return board[x][y]


def find_matching_gems(board):
    """Find sets of three or more matching gems and return them in a list."""
    gems_to_remove = (
        []
    )  # a list of lists of gems in matching triplets that should be removed
    board_copy = copy.deepcopy(board)

    # loop through each space, checking for 3 adjacent identical gems
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            # look for horizontal matches
            if (
                get_gem_at(board_copy, x, y)
                == get_gem_at(board_copy, x + 1, y)
                == get_gem_at(board_copy, x + 2, y)
                and get_gem_at(board_copy, x, y) != EMPTY_SPACE
            ):
                target_gem = board_copy[x][y]
                offset = 0
                remove_set = []

                while get_gem_at(board_copy, x + offset, y) == target_gem:
                    # keep checking if there's more than 3 gems in a row
                    remove_set.append((x + offset, y))
                    board_copy[x + offset][y] = EMPTY_SPACE
                    offset += 1
                gems_to_remove.append(remove_set)

            # look for vertical matches
            if (
                get_gem_at(board_copy, x, y)
                == get_gem_at(board_copy, x, y + 1)
                == get_gem_at(board_copy, x, y + 2)
                and get_gem_at(board_copy, x, y) != EMPTY_SPACE
            ):
                target_gem = board_copy[x][y]
                offset = 0
                remove_set = []
                while get_gem_at(board_copy, x, y + offset) == target_gem:
                    # keep checking, in case there's more than 3 gems in a row
                    remove_set.append((x, y + offset))
                    board_copy[x][y + offset] = EMPTY_SPACE
                    offset += 1
                gems_to_remove.append(remove_set)

    return gems_to_remove


def highlight_space(x, y):
    """Highlights the space at the given x,y board coordinates"""
    pygame.draw.rect(DISPLAYSURF, HIGHLIGHTCOLOR, BOARDRECTS[x][y], 4)


def get_dropping_gems(board):
    """Find all the gems that have an empty space below them"""
    board_copy = copy.deepcopy(board)
    dropping_gems = []

    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT - 2, -1, -1):
            if board_copy[x][y + 1] == EMPTY_SPACE and board_copy[x][y] != EMPTY_SPACE:
                # This space drops if not empty but the space below it is
                dropping_gems.append(
                    {
                        "imageNum": board_copy[x][y],
                        "x": x,
                        "y": y,
                        "direction": Direction.DOWN,
                    }
                )
                board_copy[x][y] = EMPTY_SPACE

    return dropping_gems


def animate_moving_gems(board, gems, points_text, score):
    """Animates the moving gems and points text on the board"""
    # pointsText is a dictionary with keys 'x', 'y', and 'points'
    progress = 0  # progress at 0 represents beginning, 100 means finished.

    while progress < 100:  # animation loop
        DISPLAYSURF.fill(BGCOLOR)
        draw_board(board)

        for gem in gems:  # Draw each gem.
            draw_moving_gem(gem, progress)

        draw_score(score)

        for point_text in points_text:
            points_surf = BASICFONT.render(str(point_text["points"]), 1, SCORECOLOR)
            points_rect = points_surf.get_rect()
            points_rect.center = (point_text["x"], point_text["y"])
            DISPLAYSURF.blit(points_surf, points_rect)

        pygame.display.update()
        FPSCLOCK.tick(FPS)
        progress += MOVE_RATE


def move_gems(board, moving_gems):
    """Moves the gems on the board based on their direction property"""
    # movingGems is a list of dicts with keys x, y, direction, imageNum
    for gem in moving_gems:
        if gem["y"] != ROW_ABOVE_BOARD:
            board[gem["x"]][gem["y"]] = EMPTY_SPACE
            movex = 0
            movey = 0

            if gem["direction"] == Direction.LEFT:
                movex = -1
            elif gem["direction"] == Direction.RIGHT:
                movex = 1
            elif gem["direction"] == Direction.DOWN:
                movey = 1
            elif gem["direction"] == Direction.UP:
                movey = -1
            board[gem["x"] + movex][gem["y"] + movey] = gem["imageNum"]
        else:
            # gem is located above the board (where new gems come from)
            board[gem["x"]][0] = gem["imageNum"]  # move to top row


def check_for_gem_click(pos):
    """See if the mouse click was on the board"""
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            if BOARDRECTS[x][y].collidepoint(pos[0], pos[1]):
                return {"x": x, "y": y}

    return None  # Click was not on the board.


def draw_board(board):
    """Draws the gems on the board using the board data structure."""
    for x in range(BOARD_WIDTH):
        for y in range(BOARD_HEIGHT):
            pygame.draw.rect(DISPLAYSURF, GRIDCOLOR, BOARDRECTS[x][y], 1)
            gem_to_draw = board[x][y]

            if gem_to_draw != EMPTY_SPACE:
                DISPLAYSURF.blit(GEM_IMAGES[gem_to_draw], BOARDRECTS[x][y])


def get_board_copy_minus_gems(board, gems):
    """Returns a copy of the passed board data structure without the gems in the "gems" list."""
    #
    # Gems is a list of dicts, with keys x, y, direction, imageNum

    board_copy = copy.deepcopy(board)

    # Remove some of the gems from this board data structure copy.
    for gem in gems:
        if gem["y"] != ROW_ABOVE_BOARD:
            board_copy[gem["x"]][gem["y"]] = EMPTY_SPACE

    return board_copy


def draw_score(score):
    """Draws the score text in the lower left corner of the screen."""
    score_img = BASICFONT.render(str(score), 1, SCORECOLOR)
    score_rect = score_img.get_rect()
    score_rect.bottomleft = (10, WINDOW_HEIGHT - 6)
    DISPLAYSURF.blit(score_img, score_rect)


if __name__ == "__main__":
    main()
