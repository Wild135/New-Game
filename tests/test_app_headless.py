"""Integration tests that run the real pygame app headlessly (no window)."""
import pygame
import pytest

from game.app import SCREENS, App
from game.ui import theme


@pytest.fixture
def app(tmp_path):
    a = App(headless=True, data_dir=str(tmp_path))
    for _ in range(8):        # run the loading steps
        a.frame(1 / 60)
    yield a
    pygame.quit()


def click(app, pos):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    app.frame(1 / 60)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    app.frame(1 / 60)
    app.frame(1 / 60)


def test_loading_reaches_menu_and_game(app):
    assert app.scene == "menu"
    click(app, (theme.WIDTH // 2, 895))          # PLAY button
    assert app.scene == "game"


def test_every_screen_opens_and_draws(app):
    app.start_game()
    app.tutorial.skip()
    for name in SCREENS:
        if name == "offline":
            continue
        app.stack.clear()
        app.open(name)
        for _ in range(3):
            app.frame(1 / 60)
        assert app.stack, name
    app.stack.clear()
    for fid in app.game.factory.floors:
        app.open_floor_panel(fid)
        app.frame(1 / 60)


def test_tutorial_can_be_completed_by_clicking(app):
    app.start_game()
    tut = app.tutorial
    for _ in range(400):
        if not tut.active:
            break
        step = tut.current()
        app.frame(1 / 60)
        if step.button:
            click(app, tut._button_rect().center)
        else:
            rect = app.tutorial_rects.get(step.target)
            if rect is None:
                app.frame(1 / 60)
                continue
            click(app, rect.center)
            for _ in range(20):
                app.frame(1 / 10)  # let production happen
    assert not tut.active, f"tutorial stuck at step {app.game.tutorial['step']}"
    assert app.game.stats["rockets_launched"] >= 1
    assert app.game.stats["managers_hired"] >= 1


def test_upgrade_button_click(app):
    app.start_game()
    app.tutorial.skip()
    app.game.credits = 1000
    app.frame(1 / 60)
    rect = app.factory_view.highlight_rects["upg:launchpad"]
    click(app, rect.center)
    assert app.game.factory.floors["launchpad"].level == 2


def test_rapid_clicking_and_scrolling(app):
    app.start_game()
    app.tutorial.skip()
    app.game.credits = 1e6
    app.frame(1 / 60)
    rect = app.factory_view.highlight_rects["upg:launchpad"]
    for _ in range(30):
        click(app, rect.center)
    assert app.game.credits >= 0
    for _ in range(10):
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3, flipped=False))
        app.frame(1 / 60)
    assert app.factory_view.scroll.offset > 0


def test_save_and_reload_via_app(app, tmp_path):
    app.start_game()
    app.game.credits = 4242
    app.game.tutorial["done"] = True
    assert app.save_now()
    app2 = App(headless=True, data_dir=str(tmp_path))
    for _ in range(8):
        app2.frame(1 / 60)
    assert app2.game.credits == pytest.approx(4242, rel=0.01)


def test_long_absence_shows_offline_screen(app):
    from game.ui.screens.settings import OfflineScreen
    app.start_game()
    app.tutorial.skip()
    for def_id, fid in (("alex", "parts"), ("sam", "transport"), ("riley", "assembly"), ("jordan", "launchpad")):
        app.game.credits += 1e6
        inst = app.game.managers.hire(def_id)
        app.game.managers.assign(inst.uid, "earth", fid)
    app.last_wall -= 3600          # simulate the computer sleeping for an hour
    app.game.last_seen -= 3600
    app.frame(1 / 60)
    assert any(isinstance(s, OfflineScreen) for s in app.stack)
