@echo off
REM ======================================================================
REM Template launch script for the Factorio dedicated server.
REM Copy this to C:\FactorioServer\start-server.bat and replace
REM PUT_YOUR_RCON_PASSWORD_HERE with the real password.
REM DO NOT commit the real start-server.bat (it's in .gitignore).
REM ======================================================================

set "FACTORIO=C:\Program Files (x86)\Steam\steamapps\common\Factorio\bin\x64\factorio.exe"

"%FACTORIO%" ^
  --start-server "C:\FactorioServer\saves\server.zip" ^
  --server-settings "C:\FactorioServer\server-settings.json" ^
  --port 34197 ^
  --rcon-bind 127.0.0.1:27015 ^
  --rcon-password "PUT_YOUR_RCON_PASSWORD_HERE" ^
  --console-log "C:\FactorioServer\console.log" ^
  --mod-directory "C:\FactorioServer\mods"

pause
