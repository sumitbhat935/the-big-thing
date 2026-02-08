@echo off
REM BigThing v2 - Setup Windows Task Scheduler
REM Runs the daily report once per day at 5:00 PM (after market close)

set PYTHON=py -3.12
set SCRIPT=%~dp0daily_report.py
set CONFIG=%~dp0..\config.json
set OUTPUT=%~dp0..\report.json

echo Creating scheduled task: BigThing Daily Report (5:00 PM)...
schtasks /Create /SC DAILY /TN "BigThing Daily Report" /TR "\"%PYTHON%\" \"%SCRIPT%\" --config \"%CONFIG%\" --output \"%OUTPUT%\"" /ST 17:00 /F

echo.
echo Done. The report will run daily at 5:00 PM.
echo To run manually:  %PYTHON% "%SCRIPT%" --config "%CONFIG%" --output "%OUTPUT%"
echo To delete the task: schtasks /Delete /TN "BigThing Daily Report" /F
pause
