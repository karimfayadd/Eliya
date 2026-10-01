@echo off
title Eliya — Network Intelligence
echo.
echo  Starting Eliya...
echo  Dashboard will open at http://127.0.0.1:7331
echo.
python eliya.py --traffic %*
pause
