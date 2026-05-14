@echo off
REM Boot azure functions host. The WindowsApps Python 3.11 that `py` launcher
REM resolves to is what the worker spawns under, regardless of env vars or
REM PATH ordering. Inject .funcvenv\Lib\site-packages onto PYTHONPATH so that
REM Python finds our deps (azure-durable-functions, agent-framework, etc.)
REM without us having to install into the system Python.
SETLOCAL
SET "languageWorkers__python__defaultExecutablePath=c:\dev\ghcp sdk stuff\.funcvenv\Scripts\python.exe"
SET "LANGUAGE_WORKERS__PYTHON__DEFAULTEXECUTABLEPATH=c:\dev\ghcp sdk stuff\.funcvenv\Scripts\python.exe"
SET "PYTHONPATH=c:\dev\ghcp sdk stuff;c:\dev\ghcp sdk stuff\.funcvenv\Lib\site-packages"
SET "PATH=c:\dev\ghcp sdk stuff\.funcvenv\Scripts;%PATH%"
cd /d "c:\dev\ghcp sdk stuff"
func start --port 7071 --no-build %*
