@echo off
REM 매일 1회 자동 실행용 (작업 스케줄러 등록). 환율->수집->리포트.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\cware\project\figures-analysis"
"C:\Users\cware\AppData\Local\Programs\Python\Python312\python.exe" run.py daily >> "data\daily_log.txt" 2>&1
