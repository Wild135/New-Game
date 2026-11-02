# PyInstaller build recipe.  Build with:  python -m PyInstaller --noconfirm rocket_empire.spec
# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
datas = [("config", "config"), ("assets", "assets")]
icon_path = os.path.join("assets", "images", "icon.ico")

a = Analysis(["main.py"], pathex=["."], binaries=[], datas=datas, hiddenimports=[],
             hookspath=[], runtime_hooks=[], excludes=["tkinter", "pytest"], cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RocketEmpire", debug=False, strip=False,
          upx=False, console=False, icon=icon_path if os.path.exists(icon_path) else None)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="RocketEmpire")
