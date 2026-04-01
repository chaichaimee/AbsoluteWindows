# cmd_tools.py

import subprocess
import os
import ctypes
import tempfile
from ctypes import wintypes
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except:
	def _(x): return x

# ------------------------------------------------------------
# Helper: launch a batch file with admin rights and visible window
# ------------------------------------------------------------
def _launch_batch(batch_content, error_msg_prefix):
	"""
	Create a temporary batch file with given content, launch it as admin.
	Returns (success, error_message) tuple.
	"""
	try:
		fd, batch_path = tempfile.mkstemp(suffix='.bat', prefix='aw_', text=True)
		with os.fdopen(fd, 'w') as f:
			f.write(batch_content)
		log.info(f"Temporary batch file created: {batch_path}")

		result = ctypes.windll.shell32.ShellExecuteW(
			None, "runas", batch_path, None, None, 1  # SW_SHOWNORMAL
		)
		log.info(f"ShellExecuteW returned: {result}")

		if result > 32:
			return True, ""
		else:
			log.error(f"ShellExecuteW failed with code {result}")
			if result == 1223:
				return False, _("User cancelled the UAC elevation prompt.")
			else:
				return False, _(f"{error_msg_prefix} Error code: {result}")
	except Exception as e:
		log.exception(f"Exception in _launch_batch")
		return False, _("Exception occurred: {error}").format(error=str(e))

# ------------------------------------------------------------
# DISM
# ------------------------------------------------------------
def run_dism(config_dir):
	log.info("=== run_dism called ===")
	batch = rf"""@echo off
title DISM RestoreHealth Report
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\dism_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo DISM RestoreHealth Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Running DISM /Online /Cleanup-Image /RestoreHealth... >> "%REPORT%"
echo This may take 15-30 minutes. >> "%REPORT%"
echo ============================================ >> "%REPORT%"
DISM /Online /Cleanup-Image /RestoreHealth >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch DISM")

# ------------------------------------------------------------
# SFC Scannow
# ------------------------------------------------------------
def run_sfc_scannow(config_dir):
	log.info("=== run_sfc_scannow called ===")
	batch = rf"""@echo off
title SFC Scannow Report
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\sfc_scannow_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo SFC Scannow Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Attempting to start TrustedInstaller service... >> "%REPORT%"
sc config TrustedInstaller start= demand >nul 2>&1
sc start TrustedInstaller >nul 2>&1
if errorlevel 1 (
	net start TrustedInstaller >nul 2>&1
)
timeout /t 5 /nobreak >nul
echo Running SFC Scannow... >> "%REPORT%"
sfc /scannow >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch SFC Scannow")

# ------------------------------------------------------------
# Chkdsk
# ------------------------------------------------------------
def run_chkdsk(config_dir):
	log.info("=== run_chkdsk called ===")
	batch = rf"""@echo off
title Chkdsk Report
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\chkdsk_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Chkdsk Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Running chkdsk C: /f /r... >> "%REPORT%"
echo (If prompted to schedule at next reboot, answer Y automatically) >> "%REPORT%"
echo y | chkdsk C: /f /r >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch Chkdsk")

# ------------------------------------------------------------
# Disk Cleanup
# ------------------------------------------------------------
def run_disk_cleanup(config_dir):
	log.info("=== run_disk_cleanup called ===")
	batch = rf"""@echo off
title Disk Cleanup Report
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\disk_cleanup_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Disk Cleanup Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Before cleanup: >> "%REPORT%"
for /f "tokens=3" %%a in ('fsutil volume diskfree C: ^| find "avail"') do set BEFORE=%%a
echo Free space on C: %BEFORE% bytes >> "%REPORT%"
echo. >> "%REPORT%"
echo Running cleanmgr /verylowdisk... >> "%REPORT%"
cleanmgr /verylowdisk
echo After cleanup: >> "%REPORT%"
for /f "tokens=3" %%a in ('fsutil volume diskfree C: ^| find "avail"') do set AFTER=%%a
echo Free space on C: %AFTER% bytes >> "%REPORT%"
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch Disk Cleanup")

# ------------------------------------------------------------
# Power Diagnostic (battery report as HTML)
# ------------------------------------------------------------
def run_power_diagnostic(config_dir):
	log.info("=== run_power_diagnostic called ===")
	batch = rf"""@echo off
title Power Diagnostic (Battery Report)
set "CONFIG_DIR={config_dir}"
echo ============================================
echo Generating battery report...
echo ============================================
powercfg /batteryreport /output "%CONFIG_DIR%\battery_report.html"
if exist "%CONFIG_DIR%\battery_report.html" (
	echo Battery report saved to %CONFIG_DIR%\battery_report.html
	start "" "%CONFIG_DIR%\battery_report.html"
) else (
	echo Failed to generate battery report.
)
echo.
echo Press any key to close this window.
pause > nul
"""
	return _launch_batch(batch, "Failed to launch power diagnostic")

# ------------------------------------------------------------
# Disk Status (PowerShell)
# ------------------------------------------------------------
def run_disk_status(config_dir):
	log.info("=== run_disk_status called ===")
	batch = rf"""@echo off
title Disk Status Report
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\disk_status_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Disk Status Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Retrieving disk status using PowerShell... >> "%REPORT%"
powershell -command "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, Size | Format-List" >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch disk status")