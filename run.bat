@echo off
chcp 65001 >nul
echo Building the search pages (preprocess.py)...
python preprocess.py
if errorlevel 1 (
    echo.
    echo Something went wrong. Try installing the requirements first:
    echo     python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo.
echo Opening the chatbot...
start "" "%~dp0output\chat.html"
