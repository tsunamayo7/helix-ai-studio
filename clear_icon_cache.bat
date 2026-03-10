@echo off
:: ===========================================================================
:: clear_icon_cache.bat — Helix AI Studio アイコンキャッシュクリア
:: ===========================================================================
:: タスクバーアイコンが古い・表示されない場合にこのスクリプトを実行してください。
:: 管理者権限は不要です。
:: ===========================================================================

echo [Helix AI Studio] アイコンキャッシュをクリアしています...
echo.

:: Helix AI Studio を終了（起動中の場合）
taskkill /f /im HelixAIStudio.exe 2>nul
taskkill /f /im python.exe /fi "WINDOWTITLE eq Helix AI Studio*" 2>nul
timeout /t 1 /nobreak >nul

:: Explorer を一時停止
echo [1/4] Explorer を停止中...
taskkill /f /im explorer.exe 2>nul
timeout /t 2 /nobreak >nul

:: IconCache.db を削除
echo [2/4] IconCache.db を削除中...
del /f /q "%LOCALAPPDATA%\IconCache.db" 2>nul
del /f /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache*.db" 2>nul
del /f /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache*.db" 2>nul

:: ユーザー定義アプリケーション AUMID エントリを削除して再登録
echo [3/5] AUMID レジストリエントリをクリア中...
reg delete "HKCU\Software\Classes\HelixAIStudio.HelixAIStudio.App" /f 2>nul

:: v12.8.2: AUMID DefaultIcon を正しいアイコンパスで再登録
:: これにより、アプリ未起動時（タスクバーピン止め・スタートメニュー）でも
:: 正しいアイコンが表示される
echo [4/5] AUMID DefaultIcon を再登録中...
reg add "HKCU\Software\Classes\HelixAIStudio.HelixAIStudio.App\DefaultIcon" /ve /t REG_SZ /d "%~dp0icon.ico,0" /f 2>nul

:: Explorer を再起動
echo [5/5] Explorer を再起動中...
start explorer.exe
timeout /t 2 /nobreak >nul

echo.
echo 完了しました。
echo Helix AI Studio を起動してタスクバーアイコンを確認してください。
echo.
echo   python HelixAIStudio.py
echo.
pause
