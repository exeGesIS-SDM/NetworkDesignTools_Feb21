@echo off
call "C:\Program Files\QGIS 3.10\bin\o4w_env.bat"
call "C:\Program Files\QGIS 3.10\bin\qt5_env.bat"
call "C:\Program Files\QGIS 3.10\bin\py3_env.bat"

@echo on
"C:\Program Files\QGIS 3.10\apps\Python37\Scripts\pyrcc5.bat" -o %~dpn1.py %1