@echo off
REM 와이스 실거래(낙찰가) 누적용 — 자주 폴링(낙찰 피드 20건 고정). 작업 스케줄러 등록.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\cware\project\figures-analysis"
"C:\Users\cware\AppData\Local\Programs\Python\Python312\python.exe" run.py wyyyes >> "data\wyyyes_log.txt" 2>&1
