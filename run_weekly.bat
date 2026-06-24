@echo off
REM 주 1회 자동 실행용 (작업 스케줄러 등록). 정가(amiami/hlj/bbts)->재그룹->분석->HTML.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\cware\project\figures-analysis"
"C:\Users\cware\AppData\Local\Programs\Python\Python312\python.exe" run.py weekly >> "data\weekly_log.txt" 2>&1
