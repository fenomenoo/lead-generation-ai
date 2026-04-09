@echo off
REM Sets up the daily email scheduler as a Windows Task Scheduler job
REM Runs once at 9am every day, sending due follow-ups automatically

set PY=C:\Users\USER\AppData\Local\Programs\Python\Python311\python.exe
set SCRIPT=C:\Users\USER\Projects\lead-generation-ai\scheduler.py

schtasks /create /tn "ClientMachine-DailySend" /tr "\"%PY%\" \"%SCRIPT%\"" /sc DAILY /st 09:00 /f /rl HIGHEST

echo.
echo Task created: ClientMachine-DailySend
echo Will run daily at 9:00 AM, sending any due emails automatically.
echo.
echo To check status: schtasks /query /tn "ClientMachine-DailySend"
echo To run now:      schtasks /run /tn "ClientMachine-DailySend"
echo To remove:       schtasks /delete /tn "ClientMachine-DailySend" /f
pause
