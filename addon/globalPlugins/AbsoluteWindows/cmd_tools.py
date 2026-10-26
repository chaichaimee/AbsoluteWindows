# cmd_tools.py

import subprocess
import os
import re
import ctypes
import tempfile
import threading
import time
from ctypes import wintypes
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except Exception:
	def _(x): return x


# ------------------------------------------------------------
# SHELLEXECUTEINFOW / ShellExecuteExW plumbing
#
# _launch_batch previously used the simpler ShellExecuteW, which gives no
# process handle and therefore no way to know when the launched batch
# actually finished - which is why the temporary .bat files it creates were
# never cleaned up and accumulated in Temp over time. SEE_MASK_NOCLOSEPROCESS
# asks ShellExecuteExW to return a real process handle in hProcess, which a
# background thread can wait on before deleting the file - correct regardless
# of how the batch itself ends (pause, exit, or anything else), unlike trying
# to string-append a self-delete line to batch_content.
# ------------------------------------------------------------
class _SHELLEXECUTEINFOW(ctypes.Structure):
	_fields_ = [
		("cbSize", wintypes.DWORD),
		("fMask", ctypes.c_ulong),
		("hwnd", wintypes.HWND),
		("lpVerb", wintypes.LPCWSTR),
		("lpFile", wintypes.LPCWSTR),
		("lpParameters", wintypes.LPCWSTR),
		("lpDirectory", wintypes.LPCWSTR),
		("nShow", ctypes.c_int),
		("hInstApp", wintypes.HANDLE),
		("lpIDList", ctypes.c_void_p),
		("lpClass", wintypes.LPCWSTR),
		("hkeyClass", wintypes.HANDLE),
		("dwHotKey", wintypes.DWORD),
		("hIconOrMonitor", wintypes.HANDLE),
		("hProcess", wintypes.HANDLE),
	]


_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_NOASYNC = 0x00000100
_SW_SHOWNORMAL = 1
_INFINITE = 0xFFFFFFFF


def _cleanupBatchFile(batch_path):
	try:
		os.remove(batch_path)
	except OSError as e:
		log.debug(f"Could not remove temporary batch file {batch_path}: {e}")


def _launch_batch(batch_content, error_msg_prefix, elevated=True):
	"""
	Create a temporary batch file with the given content and launch it -
	elevated via UAC by default, or in the current user's own context when
	elevated=False (see run_winget_upgrade_all/run_winget_list/
	run_clear_url_cache for why some commands must NOT be elevated). Once the
	launched process exits, the temporary .bat file is removed on a
	background thread.
	Returns (success, error_message) tuple.
	"""
	try:
		fd, batch_path = tempfile.mkstemp(suffix='.bat', prefix='aw_', text=True)
		with os.fdopen(fd, 'w') as f:
			f.write(batch_content)
		log.info(f"Temporary batch file created: {batch_path}")

		executeInfo = _SHELLEXECUTEINFOW()
		executeInfo.cbSize = ctypes.sizeof(_SHELLEXECUTEINFOW)
		executeInfo.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NOASYNC
		executeInfo.hwnd = None
		executeInfo.lpVerb = "runas" if elevated else "open"
		executeInfo.lpFile = batch_path
		executeInfo.lpParameters = None
		executeInfo.lpDirectory = None
		executeInfo.nShow = _SW_SHOWNORMAL
		executeInfo.hInstApp = None

		succeeded = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(executeInfo))
		if not succeeded:
			errorCode = ctypes.windll.kernel32.GetLastError()
			log.error(f"ShellExecuteExW failed with code {errorCode}")
			_cleanupBatchFile(batch_path)
			if errorCode == 1223:
				return False, _("User cancelled the UAC elevation prompt.")
			else:
				return False, _(f"{error_msg_prefix} Error code: {errorCode}")

		log.info("ShellExecuteExW launched batch successfully")
		processHandle = executeInfo.hProcess
		if processHandle:
			def waitAndCleanup():
				try:
					ctypes.windll.kernel32.WaitForSingleObject(processHandle, _INFINITE)
				except Exception as e:
					log.warning(f"Failed waiting on batch process: {e}")
				finally:
					ctypes.windll.kernel32.CloseHandle(processHandle)
					_cleanupBatchFile(batch_path)
			threading.Thread(target=waitAndCleanup, daemon=True).start()
		else:
			# No process handle was returned (can happen for some verb/association
			# combinations) - clean up immediately rather than leak the file forever.
			_cleanupBatchFile(batch_path)

		return True, ""
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
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\dism_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo DISM RestoreHealth Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Running DISM /Online /Cleanup-Image /RestoreHealth... >> "%REPORT%"
echo This may take 15-30 minutes. >> "%REPORT%"
echo ============================================ >> "%REPORT%"
"%SYS32%\dism.exe" /Online /Cleanup-Image /RestoreHealth >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch DISM")

# ------------------------------------------------------------
# DISM international settings (language / locale / keyboard info)
# ------------------------------------------------------------
def run_dism_get_intl(config_dir):
	log.info("=== run_dism_get_intl called ===")
	batch = rf"""@echo off
title DISM International Settings Report
set "CONFIG_DIR={config_dir}"
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\dism_get_intl_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo DISM International Settings Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Running DISM /Online /Get-Intl... >> "%REPORT%"
"%SYS32%\dism.exe" /Online /Get-Intl >> "%REPORT%" 2>&1
echo DISM exit code: %errorlevel% >> "%REPORT%"
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch DISM Get-Intl")

# ------------------------------------------------------------
# SFC Scannow
# ------------------------------------------------------------
def run_sfc_scannow(config_dir):
	log.info("=== run_sfc_scannow called ===")
	batch = rf"""@echo off
title SFC Scannow Report
set "CONFIG_DIR={config_dir}"
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\sfc_scannow_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo SFC Scannow Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Attempting to start TrustedInstaller service... >> "%REPORT%"
"%SYS32%\sc.exe" config TrustedInstaller start= demand >nul 2>&1
"%SYS32%\sc.exe" start TrustedInstaller >nul 2>&1
if errorlevel 1 (
	"%SYS32%\net.exe" start TrustedInstaller >nul 2>&1
)
"%SYS32%\timeout.exe" /t 5 /nobreak >nul
echo Running SFC Scannow, this can take several minutes... >> "%REPORT%"
"%SYS32%\sfc.exe" /scannow >> "%REPORT%" 2>&1
echo SFC exit code: %errorlevel% >> "%REPORT%"
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
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
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\chkdsk_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Chkdsk Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Running chkdsk C: /f /r... >> "%REPORT%"
echo Windows cannot lock the C: drive while it is in use, so this normally >> "%REPORT%"
echo only SCHEDULES the check for the next restart rather than running it >> "%REPORT%"
echo immediately - that is expected. Restart Windows to see the actual >> "%REPORT%"
echo scan results. >> "%REPORT%"
echo (If prompted to schedule at next reboot, answer Y automatically) >> "%REPORT%"
echo y | "%SYS32%\chkdsk.exe" C: /f /r >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Current dirty-bit status for C: (set means a check is pending): >> "%REPORT%"
"%SYS32%\fsutil.exe" dirty query C: >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
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
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\disk_cleanup_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Disk Cleanup Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Before cleanup: >> "%REPORT%"
for /f "tokens=3" %%a in ('"%SYS32%\fsutil.exe" volume diskfree C: ^| find "avail"') do set BEFORE=%%a
echo Free space on C: %BEFORE% bytes >> "%REPORT%"
echo. >> "%REPORT%"
echo Running cleanmgr /verylowdisk... >> "%REPORT%"
"%SYS32%\cleanmgr.exe" /verylowdisk
echo After cleanup: >> "%REPORT%"
for /f "tokens=3" %%a in ('"%SYS32%\fsutil.exe" volume diskfree C: ^| find "avail"') do set AFTER=%%a
echo Free space on C: %AFTER% bytes >> "%REPORT%"
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
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
set "SYS32=%SystemRoot%\System32"
echo ============================================
echo Generating battery report...
echo ============================================
"%SYS32%\powercfg.exe" /batteryreport /output "%CONFIG_DIR%\battery_report.html"
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
set "PWSH=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "REPORT=%CONFIG_DIR%\disk_status_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Disk Status Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Retrieving disk status using PowerShell... >> "%REPORT%"
"%PWSH%" -command "Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, Size | Format-List" >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SystemRoot%\System32\notepad.exe" "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch disk status")

# ------------------------------------------------------------
# Windows Defender Full Scan (low priority, background)
# ------------------------------------------------------------
def run_defender_full_scan_low(config_dir):
	log.info("=== run_defender_full_scan_low called ===")
	batch = rf"""@echo off
title Windows Defender Full Scan (Low Priority)
echo Starting Windows Defender Full Scan at low CPU priority...
echo The scan will continue running in the background.
start /low "" "%ProgramFiles%\Windows Defender\MpCmdRun.exe" -Scan -ScanType 2
exit
"""
	return _launch_batch(batch, "Failed to start Windows Defender Full Scan")

# ------------------------------------------------------------
# winget package management
#
# winget is intentionally launched WITHOUT elevation (elevated=False below).
# On a per-user winget install it is commonly registered as a per-user App
# Execution Alias; running it from an elevated process can resolve to a
# different (or missing) winget context than the signed-in user actually
# has configured, and can install/upgrade packages into the wrong per-user
# vs. per-machine scope. Running unelevated matches how the user would run
# winget themselves from an ordinary command prompt.
# ------------------------------------------------------------
def run_winget_upgrade_all(config_dir):
	log.info("=== run_winget_upgrade_all called ===")
	batch = rf"""@echo off
title Winget Upgrade All Packages
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\winget_upgrade_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Winget Upgrade All Packages Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
winget upgrade --all --include-unknown --silent --accept-package-agreements --accept-source-agreements >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch winget upgrade", elevated=False)


def run_winget_list(config_dir):
	log.info("=== run_winget_list called ===")
	batch = rf"""@echo off
title Winget Installed Packages
set "CONFIG_DIR={config_dir}"
set "REPORT=%CONFIG_DIR%\winget_list_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Winget Installed Packages Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
winget list >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
notepad "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to launch winget list", elevated=False)

# ------------------------------------------------------------
# Windows Search database defragmentation
#
# There is no dedicated "defragment" switch for Windows Search. The index
# is an ESE (Extensible Storage Engine) database file, and esentutl /d is
# Microsoft's own documented tool for compacting/defragmenting an ESE
# database. The WSearch service must be stopped first, since it holds the
# file open, then restarted afterward. Controlling the service needs admin
# rights, so this stays elevated.
# ------------------------------------------------------------
def run_search_database_defrag(config_dir):
	log.info("=== run_search_database_defrag called ===")
	batch = rf"""@echo off
title Windows Search Database Defragmentation
set "CONFIG_DIR={config_dir}"
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\search_defrag_report.txt"
set "DB=%ProgramData%\Microsoft\Search\Data\Applications\Windows\Windows.edb"
if exist "%REPORT%" del "%REPORT%"
echo Windows Search Database Defragmentation Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Stopping Windows Search service... >> "%REPORT%"
"%SYS32%\net.exe" stop WSearch >> "%REPORT%" 2>&1
if not exist "%DB%" (
	echo Search database not found at %DB% >> "%REPORT%"
) else (
	echo Running esentutl /d on the search database... >> "%REPORT%"
	"%SYS32%\esentutl.exe" /d "%DB%" >> "%REPORT%" 2>&1
)
echo Restarting Windows Search service... >> "%REPORT%"
"%SYS32%\net.exe" start WSearch >> "%REPORT%" 2>&1
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to defragment the Windows Search database")

# ------------------------------------------------------------
# Windows Defender full scan (normal priority, foreground)
#
# The existing sibling run_defender_full_scan_low starts the same scan with
# "start /low"; this omits /low so the scan runs at normal default priority.
# Fire-and-forget like the low-priority sibling - a full scan can take a
# long time and this does not block waiting for it to finish.
# ------------------------------------------------------------
def run_defender_full_scan(config_dir):
	log.info("=== run_defender_full_scan called ===")
	batch = rf"""@echo off
title Windows Defender Full Scan
echo Starting Windows Defender Full Scan...
echo The scan will continue running in the background.
start "" "%ProgramFiles%\Windows Defender\MpCmdRun.exe" -Scan -ScanType 2
exit
"""
	return _launch_batch(batch, "Failed to start Windows Defender Full Scan")

# ------------------------------------------------------------
# Clear URL Cache
#
# "URL Cache" is the documented Windows/WinINet term for the on-disk
# Temporary Internet Files cache (the same cache the WinINet URL Cache API
# manages). RunDll32 InetCpl.cpl,ClearMyTracksByProcess 8 is Microsoft's own
# documented way to clear exactly that cache without opening Internet
# Options. This is a per-user cache, so no elevation is used.
# ------------------------------------------------------------
def run_clear_url_cache(config_dir):
	log.info("=== run_clear_url_cache called ===")
	batch = rf"""@echo off
title Clear URL Cache
set "CONFIG_DIR={config_dir}"
set "SYS32=%SystemRoot%\System32"
set "REPORT=%CONFIG_DIR%\clear_url_cache_report.txt"
if exist "%REPORT%" del "%REPORT%"
echo Clear URL Cache Report > "%REPORT%"
echo ============================================ >> "%REPORT%"
echo Clearing the Temporary Internet Files (URL) cache... >> "%REPORT%"
"%SYS32%\RunDll32.exe" InetCpl.cpl,ClearMyTracksByProcess 8
echo Done. >> "%REPORT%"
echo. >> "%REPORT%"
echo Report saved to %REPORT% >> "%REPORT%"
"%SYS32%\notepad.exe" "%REPORT%"
pause
"""
	return _launch_batch(batch, "Failed to clear the URL cache", elevated=False)

# ------------------------------------------------------------
# Open With associations: backup / restore via the per-user FileExts
# registry key (not DISM)
#
# The previous implementation used DISM's
# Export/Import-DefaultAppAssociations XML mechanism. Per Microsoft's own
# deployment documentation, that mechanism is designed to seed *new* user
# profiles at first logon (or an offline WIM/image), not to reapply
# associations to the already-active profile on a live, running system.
# On a live system, /Import-DefaultAppAssociations reports success (no
# errorlevel) but does not actually overwrite the existing per-extension
# "Open With" choice for the current user - which is exactly the symptom
# reported: after backup, restore, and a restart, the previously set
# program for opening the file was no longer set.
#
# Windows stores the live per-user "Open With" state directly under
# HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts (a
# UserChoice ProgId + Hash per extension, plus the Open-With MRU list).
# Exporting/importing that key with reg.exe round-trips the actual
# setting instead. Since this is the current user's own registry hive,
# no elevation/UAC is required - unlike the DISM-based batch approach,
# this also removes the risk of an elevation prompt being answered by a
# different administrator account and silently writing to the wrong
# profile's hive.
# ------------------------------------------------------------
_OPENWITH_REG_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
_REG_EXE_PATH = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "reg.exe")


def run_backup_open_with(config_dir):
	"""Export the current user's per-extension Open With associations to a
	.reg file. Performs blocking subprocess I/O, so this must be called from
	a background thread, never NVDA's main thread. Returns
	(success, backupDirOrErrorMessage).

	Note: this reliably round-trips associations on the SAME Windows
	installation/user account only. The UserChoice "Hash" value Windows
	stores per extension is validated against the current user's SID (and
	other install-specific factors) as an anti-tampering measure; there is
	no way for any third-party tool, this add-on included, to produce a
	Hash that will validate under a *different* SID. After a full Windows
	reinstall - even onto the same machine, with the same username - the
	new profile has a new SID, so a restore from a pre-reinstall backup
	will not silently reapply. This is a Windows platform limitation, not
	a bug in this restore mechanism; see run_restore_open_with."""
	log.info("=== run_backup_open_with called ===")
	timestampFolder = time.strftime("%d%B%Y_%H-%M")
	backupDir = os.path.join(config_dir, "openWith", timestampFolder)
	targetRegPath = os.path.join(backupDir, "FileExtsBackup.reg")

	try:
		os.makedirs(backupDir, exist_ok=True)
	except OSError as e:
		log.error(f"Could not create Open With backup folder: {e}")
		return False, _("Could not create the backup folder.")

	try:
		result = subprocess.run(
			[_REG_EXE_PATH, "export", _OPENWITH_REG_KEY, targetRegPath, "/y"],
			capture_output=True, text=True, timeout=30
		)
	except (subprocess.TimeoutExpired, OSError) as e:
		log.error(f"Open With registry export failed: {e}")
		return False, _("Failed to back up Open With associations.")

	if result.returncode != 0 or not os.path.isfile(targetRegPath):
		log.error(f"reg export returned {result.returncode}: {result.stderr.strip()}")
		return False, _("Failed to back up Open With associations.")

	log.info(f"Open With associations backed up to {targetRegPath}")
	return True, backupDir


def run_restore_open_with(config_dir, reg_path):
	"""Import a previously exported FileExts .reg file, restoring the
	current user's per-extension Open With associations. Performs blocking
	subprocess I/O, so this must be called from a background thread, never
	NVDA's main thread. Restarting Windows Explorer (or signing out and
	back in) is still required afterward for Explorer's own association
	cache to pick up the change.

	This only reliably restores associations backed up on THIS SAME Windows
	installation and user account - see the note in run_backup_open_with
	about why a backup taken before a Windows reinstall cannot be silently
	reapplied afterward (the per-extension Hash is tied to the user's SID,
	which a reinstall changes). reg import itself will not report an error
	in that case - Windows just silently ignores the hash-invalid entries -
	so a restore "succeeding" here means the import command ran, not that
	every association was necessarily re-applied.
	Returns (success, errorMessageOrNone)."""
	log.info(f"=== run_restore_open_with called with {reg_path} ===")
	if not os.path.isfile(reg_path):
		return False, _("The selected backup file no longer exists.")

	try:
		result = subprocess.run(
			[_REG_EXE_PATH, "import", reg_path],
			capture_output=True, text=True, timeout=30
		)
	except (subprocess.TimeoutExpired, OSError) as e:
		log.error(f"Open With registry import failed: {e}")
		return False, _("Failed to restore Open With associations.")

	if result.returncode != 0:
		log.error(f"reg import returned {result.returncode}: {result.stderr.strip()}")
		return False, _("Failed to restore Open With associations.")

	log.info(f"Open With associations restored from {reg_path}")
	return True, None


# ------------------------------------------------------------
# Windows service start-type changes (one elevated, hidden batch per request)
#
# sc config needs administrator rights, and NVDA normally runs as a standard
# user, so a plain sc.exe call from NVDA fails with "Access is denied". All the
# requested changes are therefore written into ONE hidden elevated batch (a
# single UAC prompt even for "Disable all"), and the batch records a per-service
# OK/FAIL line into a result file that this function reads back after the
# elevated process exits. Blocking: call from a background thread only.
# ------------------------------------------------------------
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_SW_HIDE = 0
_WAIT_OBJECT_0 = 0x00000000
_VALID_SERVICE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")
_VALID_START_TYPES = ("auto", "delayed-auto", "demand")

# Services that must never be changed by this tool, whatever a caller asks for:
# the audio stack and the other pieces screen reader, low-vision, Bluetooth
# braille/headset and text-input users depend on.
_PROTECTED_SERVICES = frozenset({
	"audiosrv", "audioendpointbuilder", "mmcss", "themes", "textinputmanagementservice",
	"bthserv", "bthavctpsvc", "rpcss", "dcomlaunch", "plugplay", "eventlog", "winmgmt",
})


def run_service_changes(config_dir, changes):
	"""Apply start-type changes to Windows services with a single elevated batch.

	changes is a list of dicts: {"name": str, "action": "disable"} or
	{"name": str, "action": "enable", "startType": "auto"|"delayed-auto"|"demand"}.
	Returns (launched, payload): payload is a {serviceName: True/False} dict when the
	elevated batch ran to completion, or a short error message string when it could
	not be launched (including the user cancelling the UAC prompt) or timed out."""
	log.info(f"=== run_service_changes called for {len(changes)} service(s) ===")
	resultPath = os.path.join(config_dir, "services_result.txt")
	try:
		if os.path.exists(resultPath):
			os.remove(resultPath)
	except OSError as e:
		log.debug(f"Could not remove stale services result file: {e}")

	lines = [
		"@echo off",
		'set "SYS32=%SystemRoot%\\System32"',
		f'set "RESULT={resultPath}"',
	]
	requested = []
	for change in changes:
		name = change.get("name", "")
		action = change.get("action")
		if not _VALID_SERVICE_NAME.match(name) or name.lower() in _PROTECTED_SERVICES:
			log.warning(f"Refusing to change service {name!r}")
			continue
		if action == "disable":
			lines.append(f'"%SYS32%\\net.exe" stop {name} /y >nul 2>&1')
			lines.append(f'"%SYS32%\\sc.exe" config {name} start= disabled >nul 2>&1')
			lines.append(f'if errorlevel 1 (echo {name}=FAIL>>"%RESULT%") else (echo {name}=OK>>"%RESULT%")')
		elif action == "enable":
			startType = change.get("startType")
			if startType not in _VALID_START_TYPES:
				startType = "demand"
			lines.append(f'"%SYS32%\\sc.exe" config {name} start= {startType} >nul 2>&1')
			lines.append("if errorlevel 1 (")
			lines.append(f'\techo {name}=FAIL>>"%RESULT%"')
			lines.append(") else (")
			lines.append(f'\techo {name}=OK>>"%RESULT%"')
			if startType != "demand":
				# Only automatic services are started right away; a manual one is left
				# for Windows to start on demand so enabling does not add idle RAM use.
				lines.append(f'\t"%SYS32%\\sc.exe" start {name} >nul 2>&1')
			lines.append(")")
		else:
			continue
		requested.append(name)
	lines.append("exit /b 0")

	if not requested:
		return False, _("No changeable services were selected.")

	batchContent = "\r\n".join(lines) + "\r\n"
	batchPath = None
	try:
		fd, batchPath = tempfile.mkstemp(suffix=".bat", prefix="aw_", text=True)
		with os.fdopen(fd, "w") as f:
			f.write(batchContent)

		executeInfo = _SHELLEXECUTEINFOW()
		executeInfo.cbSize = ctypes.sizeof(_SHELLEXECUTEINFOW)
		executeInfo.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NOASYNC
		executeInfo.hwnd = None
		executeInfo.lpVerb = "runas"
		executeInfo.lpFile = batchPath
		executeInfo.lpParameters = None
		executeInfo.lpDirectory = None
		executeInfo.nShow = _SW_HIDE
		executeInfo.hInstApp = None

		if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(executeInfo)):
			errorCode = ctypes.windll.kernel32.GetLastError()
			log.error(f"ShellExecuteExW (service changes) failed with code {errorCode}")
			if errorCode == 1223:
				return False, _("User cancelled the UAC elevation prompt.")
			return False, _("Could not start the elevated service change. Error code: {code}").format(code=errorCode)

		processHandle = executeInfo.hProcess
		if not processHandle:
			return False, _("Could not track the elevated service change.")
		try:
			waitResult = _kernel32.WaitForSingleObject(processHandle, 180 * 1000)
		finally:
			_kernel32.CloseHandle(processHandle)
		if waitResult != _WAIT_OBJECT_0:
			log.warning(f"Service change batch did not finish in time (wait result {waitResult})")
			return False, _("The service change took too long to finish.")
	except Exception as e:
		log.exception("Exception in run_service_changes")
		return False, _("Exception occurred: {error}").format(error=str(e))
	finally:
		if batchPath:
			_cleanupBatchFile(batchPath)

	results = {name: False for name in requested}
	try:
		with open(resultPath, "r", encoding="utf-8", errors="ignore") as f:
			for line in f:
				name, _sep, outcome = line.strip().partition("=")
				if name in results:
					results[name] = (outcome == "OK")
	except OSError as e:
		log.error(f"Could not read services result file: {e}")
	return True, results
