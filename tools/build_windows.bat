@echo off
REM Builds a stand-alone Windows game: dist\RocketEmpire\RocketEmpire.exe
REM Run this from the project folder on a Windows PC with Python installed.
python -m pip install -r requirements.txt
python tools\generate_assets.py
python -m PyInstaller --noconfirm rocket_empire.spec
echo.
echo Done! Your game is in dist\RocketEmpire\RocketEmpire.exe
pause
