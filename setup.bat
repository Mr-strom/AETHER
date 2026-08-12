@echo off
echo ===================================================
echo Setting up AETHER Environment
echo ===================================================

if not exist models mkdir models
if not exist data mkdir data

if not exist venv (
    echo Creating Python 3.11 Virtual Environment...
    python -m venv venv
)

echo Activating Virtual Environment...
call venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing backend dependencies...
pip install -r requirements.txt

if exist frontend (
    echo Setting up Frontend dependencies...
    cd frontend
    npm install
    cd ..
)

echo ===================================================
echo AETHER Setup Completed Successfully!
echo ===================================================
