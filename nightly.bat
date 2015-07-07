call sample_setenv.bat
call setenv.bat

mkdir "%BUILDS%"

call sdist.bat
xcopy /Y "dist\metalink-checker-*.zip" "%BUILDS%\."
move "%BUILDS%\metalink-checker-*.zip" "%BUILDS%\%DATE%_Metalink_Checker.zip"