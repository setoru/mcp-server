@echo off
setlocal

rem ======== Edit this value if you want a fixed merge directory ========
set "CONFIG_MERGE_DIR=C:\SWRDescriptionExports\vpcep-karpenter-06031141"
rem ===================================================================

python "%~dp0pull_swr_desc_part.py" %*
