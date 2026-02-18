@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python seed_data.py
python run.py
