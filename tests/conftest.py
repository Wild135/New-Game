import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(scope="session")
def config():
    from game.core.config import GameConfig
    return GameConfig()


@pytest.fixture
def game(config):
    from game.core.game import Game
    return Game(config, now=1_000_000.0)


@pytest.fixture
def rich_game(config):
    """A game with plenty of money for purchase tests."""
    from game.core.game import Game
    g = Game(config, now=1_000_000.0)
    g.credits = 1e12
    g.gems = 10_000
    g.rp = 100_000
    return g


def automate_earth(g):
    """Hire and assign a manager to every core floor."""
    for def_id, fid in (("alex", "parts"), ("sam", "transport"), ("riley", "assembly"), ("jordan", "launchpad")):
        g.credits += 1e9
        inst = g.managers.hire(def_id)
        assert inst is not None
        assert g.managers.assign(inst.uid, "earth", fid)
