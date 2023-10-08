# GemGem

For now just a refactoring of Al Sweigart's Bejeweled clone [`gemgem.py`][gemgem] so I can better understand what's involved in a match-three game. The code version of taking something apart to see what makes it tick.

[gemgem]: https://inventwithpython.com/blog/2011/06/24/new-game-source-code-gemgem-a-bejeweled-clone/

## Setup

```bash
python -m pip install -r requirements.txt
```

## Play

```bash
python pygame_gem.py
```

## Development

I'm driving this with [just](https://github.com/casey/just), but that's not necessary to poke around.

Test:

```bash
pygame -x
```

Check and lint:

```bash
prospector --strictness high --with-tool mypy pygame_gem.py
```

## License

Sticking with the original's Simplified BSD License. This repo should have a [LICENSE](./LICENSE) file with the details.
