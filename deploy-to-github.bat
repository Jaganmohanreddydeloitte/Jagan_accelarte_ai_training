@echo off
REM GitHub Deployment Script for Accelerate with AI Lab
REM Run this after installing Git and setting up GitHub repo

echo.
echo ====================================================
echo   Accelerate with AI Lab - GitHub Deployment
echo ====================================================
echo.

REM Check if git is installed
git --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH
    echo Please install Git from: https://git-scm.com/download/win
    echo.
    pause
    exit /b 1
)

echo [Step 1] Checking Git configuration...
git config --global user.name > nul 2>&1
if errorlevel 1 (
    echo WARNING: Git user name not configured
    echo Run: git config --global user.name "Your Name"
    echo.
)

echo [Step 2] Initializing Git repository...
if exist .git (
    echo ✓ Git repository already initialized
) else (
    git init
    echo ✓ Git repository initialized
)

echo.
echo [Step 3] Creating .gitignore...
if exist .gitignore (
    echo ✓ .gitignore already exists
) else (
    REM Create .gitignore
    (
        echo # Environment
        echo .env
        echo .env.local
        echo *.env
        echo.
        echo # Python
        echo __pycache__/
        echo *.py[cod]
        echo *$py.class
        echo *.egg-info/
        echo.
        echo # Data and Runtime
        echo *.parquet
        echo *.csv
        echo audit_logs/
        echo data/lineage/
        echo reports/
        echo.
        echo # Streamlit
        echo .streamlit/
        echo.
        echo # IDE
        echo .vscode/
        echo .idea/
    ) > .gitignore
    echo ✓ .gitignore created
)

echo.
echo [Step 4] Staging files...
git add .
echo ✓ Files staged

echo.
echo [Step 5] Creating initial commit...
git commit -m "Initial commit: Enterprise AI data pipeline with lineage tracking and interactive chat" --quiet
if errorlevel 0 (
    echo ✓ Initial commit created
) else (
    echo ℹ Nothing to commit (files already committed)
)

echo.
echo ====================================================
echo   NEXT STEPS:
echo ====================================================
echo.
echo 1. Go to GitHub: https://github.com/new
echo.
echo 2. Create a new repository with these settings:
echo    - Repository name: accelerate-with-ai-lab
echo    - Public: Yes
echo    - Initialize: No
echo.
echo 3. After creating repo, copy your repo URL
echo    (should look like: https://github.com/USERNAME/REPO.git)
echo.
echo 4. Add remote and push:
echo    git remote add origin https://github.com/USERNAME/REPO.git
echo    git branch -M main
echo    git push -u origin main
echo.
echo 5. Verify on GitHub that all files are present
echo.
echo ====================================================
echo.
pause
