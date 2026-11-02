# 🚀 Rocket Empire: Idle Space Tycoon

A polished 2D portrait idle-tycoon game written in **Python 3.11+** with **pygame-ce**.
Build rocket parts, move them through your factory, assemble rockets, launch them for money,
hire managers to automate everything, research technology, expand to nine planets and
restart with Space Legacy for permanent bonuses.

All artwork, sound effects and music are **original and generated in code**. The only
external assets are two fonts (Lilita One and Fredoka) under the SIL Open Font License.
There are **no ads, no loot boxes and no real-money purchases**. Gems are earned only by playing.

---

## 1. Install and run (Windows, beginner-friendly)

1. Install **Python 3.11 or newer** from <https://www.python.org/downloads/>.
   On the first installer screen, tick **“Add python.exe to PATH”**.
2. Open the project folder in **Visual Studio Code** (File → Open Folder…).
3. Open a terminal in VS Code (Terminal → New Terminal) and run:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

The game opens in a portrait window sized to fit your screen. You can resize it freely.

| Control | Action |
|---|---|
| Left click / tap | Press buttons, tap floors to work |
| Drag or mouse wheel | Scroll the factory and menus |
| `Esc` | Close the current menu / open Settings |
| `F12` | Save a screenshot to the save folder |

Saves are stored in `%APPDATA%\RocketEmpire\` (never in the game folder). The game
autosaves every 30 seconds, when the window loses focus, and when you quit.

## 2. Build a stand-alone Windows game (.exe)

Double-click `tools\build_windows.bat` (or run it from the terminal). It installs the
requirements, exports the art/audio to `assets/` and runs PyInstaller. The result is
`dist\RocketEmpire\RocketEmpire.exe`. Zip the whole `dist\RocketEmpire` folder to share it.
Players don't need Python installed.

## 3. Run the tests and tools

```bat
python -m pytest                          :: all automated tests
python tools\economy_sim.py --hours 24    :: a bot plays the economy and reports pacing
python tools\economy_sim.py --hours 168 --offline
python tools\screenshot_tour.py shots     :: headless screenshots of every screen
python tools\generate_assets.py           :: export art + audio to assets/
```

## 4. Project layout

```
main.py                 start the game
config/                 ALL balance numbers (JSON) - tune the game here
game/
  core/                 Game object, config loader, number formatting   (no pygame)
  economy/              formulas, modifiers, offline earnings           (no pygame)
  factories/            production-chain simulation                     (no pygame)
  managers/ research/ prestige/ missions/ shop/ saves/                  (no pygame)
  rendering/            procedural art, icons, particles, factory view
  ui/                   widgets, HUD, tutorial, screens/
  audio/                synthesizer + audio manager
  app.py                window, main loop, menus
tests/                  pytest suite
tools/                  economy bot, screenshot tour, asset export, Windows build
docs/                   developer guide, testing report, mobile guide, checklist
```

More detail: [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) ·
[`docs/TESTING_REPORT.md`](docs/TESTING_REPORT.md) ·
[`docs/MOBILE_PUBLISHING.md`](docs/MOBILE_PUBLISHING.md) ·
[`docs/CHECKLIST.md`](docs/CHECKLIST.md)
