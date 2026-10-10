@echo off
REM Tao VoiceStudio.exe bang PyInstaller. Can Python 3.10-3.12 va internet. Mat 10-30 phut, dung luong vai GB.
cd /d "%~dp0"
if not exist .buildenv python -m venv .buildenv
call .buildenv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || goto :err
pyinstaller --noconfirm --clean --onedir --name VoiceStudio ^
  --add-data "static;static" ^
  --collect-all vieneu --collect-all sea_g2p --collect-all soundfile ^
  --collect-submodules uvicorn --collect-submodules fastapi --collect-submodules starlette ^
  --collect-data huggingface_hub ^
  launcher.py || goto :err
if exist ffmpeg.exe copy /y ffmpeg.exe dist\VoiceStudio\ffmpeg.exe >nul
if exist .env copy /y .env dist\VoiceStudio\.env >nul
echo.
echo Xong. Chay: dist\VoiceStudio\VoiceStudio.exe
echo Gui ca thu muc dist\VoiceStudio cho may khac (nen file .zip). Giong luu trong dist\VoiceStudio\voices.
pause
exit /b 0
:err
echo Build loi. Gui dong loi cuoi cung cho nguoi ho tro.
pause
exit /b 1
