@echo off
echo Press ENTER to accept default values (in parentheses), or type new values and hit ENTER.
set WIDTH="1920"
set /p WIDTH="Please enter the WIDTH of your screen resolution in pixels (1920): "
set HEIGHT="1080"
set /p HEIGHT="Please enter the HEIGHT of your screen resolution in pixels (1080): "
set LTRBOX="0"
set /p LTRBOX="Do you want the dialog letterbox proportions adjusted? (no): "
set EXE="swkotor.exe"
set /p EXE="Please enter the name of the swkotor.exe file you wish to patch (swkotor.exe): "
hires_patcher %WIDTH% %HEIGHT% %LTRBOX% %EXE%
pause
