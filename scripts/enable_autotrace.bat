@echo off
:: Enable PyTraceFlow autotrace for multiprocessing children
:: Usage:
::   call scripts\enable_autotrace.bat
::   python your_script.py
:: To disable, close the shell or unset the variables manually.

set PYTHONPATH=C:\Users\torog\PycharmProjects\FlowTrace;%PYTHONPATH%
set PYTRACEFLOW_AUTOTRACE=1
set PYTRACEFLOW_OUT_DIR=C:\Users\torog\PycharmProjects\FlowTrace\bench-output\autotrace
set PYTRACEFLOW_FLUSH_INTERVAL=5
set PYTRACEFLOW_FLUSH_CALL_THRESHOLD=500
set PYTRACEFLOW_SKIP_INPUTS=1
set PYTRACEFLOW_SKIP_OUTPUTS=1
set PYTRACEFLOW_VERBOSE=1
:: Uncomment to avoid tracing the main process
:: set PYTRACEFLOW_SKIP_MAIN=1

:: Optional knobs (uncomment to use)
:: set PYTRACEFLOW_WITH_MEMORY=1
:: set PYTRACEFLOW_NO_MEMORY=1
:: set PYTRACEFLOW_NO_TRACEMALLOC=1
:: set PYTRACEFLOW_FLUSH_INTERVAL=10
:: set PYTRACEFLOW_FLUSH_CALL_THRESHOLD=2000
:: set PYTRACEFLOW_SKIP_INPUTS=0
:: set PYTRACEFLOW_SKIP_OUTPUTS=0
:: set PYTRACEFLOW_VERBOSE=0
:: set PYTRACEFLOW_OUT_DIR=.

echo PyTraceFlow autotrace enabled for this session.
