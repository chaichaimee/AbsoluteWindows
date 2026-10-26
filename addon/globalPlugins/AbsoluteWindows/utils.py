# utils.py

import subprocess
import os
import ctypes
import shutil
import winreg
import psutil
import time
import threading
import wx
import ui
import tones
from ctypes import wintypes
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except Exception:
	def _(x): return x

SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

BM_CLICK = 0x00F5

shell32 = ctypes.windll.shell32
shell32.SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
shell32.SHEmptyRecycleBinW.restype = ctypes.c_long

kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

psapi = ctypes.windll.psapi
psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
psapi.EmptyWorkingSet.restype = wintypes.BOOL

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
PROCESS_VM_READ = 0x0010

class SHQUERYRBINFO(ctypes.Structure):
	_fields_ = [
		("cbSize", wintypes.DWORD),
		("i64Size", ctypes.c_ulonglong),
		("i64NumItems", ctypes.c_ulonglong),
	]

shell32.SHQueryRecycleBinW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(SHQUERYRBINFO)]
shell32.SHQueryRecycleBinW.restype = ctypes.c_long

# Constants for GetDriveTypeW
DRIVE_REMOVABLE = 2

def open_system_tray():
	try:
		user32 = ctypes.windll.user32
		VK_LWIN = 0x5B
		VK_B = 0x42
		KEYEVENTF_KEYUP = 0x0002

		user32.keybd_event(VK_LWIN, 0, 0, 0)
		user32.keybd_event(VK_B, 0, 0, 0)
		user32.keybd_event(VK_B, 0, KEYEVENTF_KEYUP, 0)
		user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
		return True
	except Exception as e:
		log.error(f"System tray open error: {e}")
		return False

def restart_audio_services():
	cmd = "net stop Audiosrv /y && net start Audiosrv"
	return _runAsAdmin(cmd, hide=True)

def get_usb_drives():
	drives = []
	try:
		bitmask = ctypes.windll.kernel32.GetLogicalDrives()
		for i in range(26):
			if bitmask & (1 << i):
				drive_letter = chr(ord('A') + i)
				path = f"{drive_letter}:\\"
				drive_type = ctypes.windll.kernel32.GetDriveTypeW(path)
				if drive_type == DRIVE_REMOVABLE:
					volume_name = _("USB Drive")
					buf = ctypes.create_unicode_buffer(256)
					fs_buf = ctypes.create_unicode_buffer(256)
					serial = wintypes.DWORD()
					max_comp = wintypes.DWORD()
					flags = wintypes.DWORD()
					success = ctypes.windll.kernel32.GetVolumeInformationW(
						path, buf, 256,
						ctypes.byref(serial),
						ctypes.byref(max_comp),
						ctypes.byref(flags),
						fs_buf, 256
					)
					if success and buf.value:
						volume_name = buf.value
					drives.append({
						'letter': f"{drive_letter}:",
						'name': volume_name
					})
	except Exception as e:
		log.error(f"Error getting USB drives via API: {e}")
	return drives

def eject_usb(drive_letter):
	systemRoot = os.environ.get('SystemRoot', 'C:\\Windows')
	powershellPath = os.path.join(systemRoot, 'Sysnative', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
	if not os.path.isfile(powershellPath):
		powershellPath = os.path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
	if not os.path.isfile(powershellPath):
		powershellPath = 'powershell.exe'

	ps_script = f"$driveEject = New-Object -comObject Shell.Application; $driveEject.Namespace(17).ParseName('{drive_letter}').InvokeVerb('Eject')"
	try:
		subprocess.run(
			[powershellPath, '-ExecutionPolicy', 'Bypass', '-NoProfile', '-Command', ps_script],
			check=True,
			timeout=10,
			capture_output=True,
			startupinfo=None
		)
		tones.beep(440, 100)
		return True
	except Exception as e:
		log.error(f"Eject USB error: {e}")
		tones.beep(220, 200)
		return False

def toggle_bluetooth():
	ps_script = (
		"[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null; "
		"$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults(); "
		"foreach($r in $radios) { "
		"if($r.Kind -eq 'Bluetooth') { "
		"if($r.State -eq 'On') { $r.SetStateAsync('Off').GetResults(); Write-Output 'Off' } "
		"else { $r.SetStateAsync('On').GetResults(); Write-Output 'On' } "
		"} }"
	)
	try:
		info = subprocess.STARTUPINFO()
		info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		out = subprocess.check_output(
			["powershell", "-ExecutionPolicy", "Bypass", "-NoProfile", "-Command", ps_script],
			startupinfo=info, text=True, timeout=10
		)
		if "Off" in out: return True, _("Bluetooth turned off.")
		elif "On" in out: return True, _("Bluetooth turned on.")
		return False, _("Could not find or change Bluetooth status.")
	except Exception as e:
		log.error(f"BT toggle error: {e}")
		return False, _("Failed to toggle Bluetooth.")

def force_restart_now():
	try:
		subprocess.Popen("shutdown.exe /r /t 0", shell=True)
	except Exception as e:
		log.error(f"Force restart failed: {e}")

def boot_to_uefi_firmware():
	cmd = "shutdown.exe /r /fw /t 0"
	return _runAsAdmin(cmd, hide=True)

def isInternetConnected():
	try:
		subprocess.check_output("ping -n 1 8.8.8.8", shell=True, timeout=2, stderr=subprocess.DEVNULL)
		return True
	except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
		return False
	except Exception as e:
		log.error(f"Internet check error: {e}")
		return False

def _runAsAdmin(command, hide=True, keepOpen=False):
	try:
		showCmd = 0 if hide else 1
		cmdPrefix = "/k" if keepOpen else "/c"
		result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f"{cmdPrefix} {command}", None, showCmd)
		if result <= 32:
			log.error(f"ShellExecuteW failed with code: {result}")
			return False
		return True
	except Exception as e:
		log.error(f"Elevation failed: {e}")
		return False

def get_active_adapter_name():
	try:
		output = subprocess.check_output("netsh interface show interface", shell=True, text=True, timeout=5)
		lines = output.splitlines()
		for line in lines:
			if "Connected" in line:
				parts = line.split()
				if len(parts) >= 4:
					try:
						connected_idx = parts.index("Connected")
						if connected_idx + 2 < len(parts):
							name_parts = parts[connected_idx+2:]
							adapter_name = " ".join(name_parts)
						else:
							adapter_name = parts[-1]
					except ValueError:
						adapter_name = parts[-1]
					adapter_name = adapter_name.strip()
					if adapter_name and adapter_name not in ("Enabled", "Connected", "Dedicated", "Internal"):
						log.info(f"Active adapter found: {adapter_name}")
						return adapter_name
		log.error("No active adapter found via netsh")
		return None
	except Exception as e:
		log.error(f"netsh get_active_adapter_name error: {e}")
		return None

def disable_adapter(name):
	cmd = f'netsh interface set interface name="{name}" admin=DISABLED'
	return _runAsAdmin(cmd, hide=True)

def enable_adapter(name):
	cmd = f'netsh interface set interface name="{name}" admin=ENABLED'
	return _runAsAdmin(cmd, hide=True)

def get_first_disabled_adapter():
	try:
		output = subprocess.check_output("netsh interface show interface", shell=True, text=True, timeout=5)
		for line in output.splitlines():
			if "Disabled" in line:
				parts = line.split()
				if len(parts) >= 4:
					try:
						disabled_idx = parts.index("Disabled")
						if disabled_idx + 2 < len(parts):
							name_parts = parts[disabled_idx+2:]
							adapter_name = " ".join(name_parts)
						else:
							adapter_name = parts[-1]
					except ValueError:
						adapter_name = parts[-1]
					adapter_name = adapter_name.strip()
					if adapter_name and adapter_name not in ("Enabled", "Disabled", "Dedicated", "Internal"):
						log.info(f"Disabled adapter found: {adapter_name}")
						return adapter_name
		return None
	except Exception as e:
		log.error(f"get_first_disabled_adapter error: {e}")
		return None

def isUACEnabled():
	try:
		KEY_WOW64_64KEY = 0x0100
		key_handle = winreg.OpenKey(
			winreg.HKEY_LOCAL_MACHINE,
			r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
			0,
			winreg.KEY_READ | KEY_WOW64_64KEY
		)
		value, _ = winreg.QueryValueEx(key_handle, "EnableLUA")
		winreg.CloseKey(key_handle)
		return (value == 1)
	except Exception as e:
		log.warning(f"Could not read UAC registry: {e}, assuming enabled")
		return True

def _setUACRegistry(value):
	# Bug fix: lpFile below is already "reg.exe" (fully qualified), so
	# lpParameters must be just reg's own arguments - it must NOT repeat "reg"
	# as the first word. The previous version built cmd starting with "reg add
	# ...", which ShellExecuteW passed straight through as
	# `reg.exe reg add ...`; reg.exe treats "reg" as an invalid operation and
	# exits immediately with an error, which is why every UAC toggle attempt
	# failed near-instantly regardless of UAC's actual current state. Also now
	# uses the fully-qualified reg.exe path rather than relying on PATH
	# resolution in the elevated process, consistent with the other cmd_tools
	# batches after the powershell "not recognized" finding.
	regExePath = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'reg.exe')
	cmd = f'add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA /t REG_DWORD /d {value} /f'
	try:
		result = ctypes.windll.shell32.ShellExecuteW(None, "runas", regExePath, cmd, None, 0)
		if result <= 32:
			log.error(f"Failed to launch reg.exe: {result}")
			return False
		time.sleep(0.5)
		current = isUACEnabled()
		expected = (value == 1)
		return (current == expected)
	except Exception as e:
		log.error(f"_setUACRegistry exception: {e}")
		return False

def disableUAC():
	return _setUACRegistry(0)

def enableUAC():
	return _setUACRegistry(1)

def isSearchWebResultsDisabled():
	"""Returns True if Windows Search's "search the web" results are disabled
	via the per-user BingSearchEnabled value, False if enabled - including
	when the value is absent, since Windows treats a missing value as
	enabled by default."""
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search", 0, winreg.KEY_READ)
		value, _regType = winreg.QueryValueEx(key, "BingSearchEnabled")
		winreg.CloseKey(key)
		return value == 0
	except FileNotFoundError:
		return False
	except OSError as e:
		log.warning(f"Could not read Search Web Results registry: {e}, assuming enabled")
		return False

def toggleSearchWebResults():
	"""Flips the per-user BingSearchEnabled value under
	HKCU\\...\\CurrentVersion\\Search. No elevation is required - this is the
	current user's own registry hive. Returns (success, isDisabledAfterToggle)."""
	currentlyDisabled = isSearchWebResultsDisabled()
	newValue = 1 if currentlyDisabled else 0
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search", 0, winreg.KEY_SET_VALUE)
		winreg.SetValueEx(key, "BingSearchEnabled", 0, winreg.REG_DWORD, newValue)
		winreg.CloseKey(key)
	except OSError as e:
		log.error(f"Failed to toggle Search Web Results: {e}")
		return False, currentlyDisabled
	return True, (newValue == 0)

def cleanTempFolders():
	totalRemoved = 0
	overallSuccess = True
	
	userTempPath = os.environ.get("TEMP", "")
	if userTempPath and os.path.exists(userTempPath):
		try:
			for item in os.listdir(userTempPath):
				itemFullPath = os.path.join(userTempPath, item)
				try:
					if os.path.isfile(itemFullPath):
						os.remove(itemFullPath)
						totalRemoved += 1
					elif os.path.isdir(itemFullPath):
						shutil.rmtree(itemFullPath, ignore_errors=True)
						totalRemoved += 1
				except Exception:
					pass
		except Exception as e:
			log.error(f"User temp clean error: {e}")
			overallSuccess = False
			
	winTempPath = r"C:\Windows\Temp"
	if os.path.exists(winTempPath):
		try:
			for item in os.listdir(winTempPath):
				itemFullPath = os.path.join(winTempPath, item)
				try:
					if os.path.isfile(itemFullPath):
						os.remove(itemFullPath)
						totalRemoved += 1
					elif os.path.isdir(itemFullPath):
						shutil.rmtree(itemFullPath, ignore_errors=True)
						totalRemoved += 1
				except Exception:
					pass
		except Exception as e:
			log.error(f"Windows temp clean error: {e}")
			overallSuccess = False
			
	return overallSuccess, totalRemoved

def cleanRunHistory():
	try:
		targetKey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
		itemIndex = 0
		historyItems = []
		while True:
			try:
				itemName, _, _ = winreg.EnumValue(targetKey, itemIndex)
				historyItems.append(itemName)
				itemIndex += 1
			except OSError:
				break
				
		removedCount = 0
		for itemName in historyItems:
			if itemName != "MRUList":
				winreg.DeleteValue(targetKey, itemName)
				removedCount += 1
				
		winreg.SetValueEx(targetKey, "MRUList", 0, winreg.REG_SZ, "")
		winreg.CloseKey(targetKey)
		return True, removedCount
	except Exception as e:
		log.error(f"Run history clean error: {e}")
		return False, 0

def get_current_wifi_password():
	try:
		output = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, timeout=5)
		ssid = None
		for line in output.splitlines():
			if "SSID" in line and "BSSID" not in line:
				parts = line.split(":")
				if len(parts) >= 2:
					ssid = parts[1].strip()
					break
		if not ssid:
			return (None, None)

		cmd = f'netsh wlan show profile name="{ssid}" key=clear'
		output = subprocess.check_output(cmd, shell=True, text=True, timeout=5)
		password = None
		for line in output.splitlines():
			if "Key Content" in line:
				parts = line.split(":")
				if len(parts) >= 2:
					password = parts[1].strip()
					break
		return (ssid, password)
	except subprocess.CalledProcessError as e:
		log.error(f"Wi-Fi password fetch failed: {e}")
		return (None, None)
	except Exception as e:
		log.error(f"Unexpected error in get_current_wifi_password: {e}")
		return (None, None)

def copy_to_clipboard(text):
	try:
		if not ctypes.windll.user32.OpenClipboard(None):
			log.error("Failed to open clipboard")
			return False
		ctypes.windll.user32.EmptyClipboard()
		hGlobal = ctypes.windll.kernel32.GlobalAlloc(0x2000, len(text.encode('utf-16-le')) + 2)
		if not hGlobal:
			ctypes.windll.user32.CloseClipboard()
			log.error("GlobalAlloc failed")
			return False
		pGlobal = ctypes.windll.kernel32.GlobalLock(hGlobal)
		ctypes.memmove(pGlobal, text.encode('utf-16-le'), len(text.encode('utf-16-le')) + 2)
		ctypes.windll.kernel32.GlobalUnlock(hGlobal)
		ctypes.windll.user32.SetClipboardData(13, hGlobal)
		ctypes.windll.user32.CloseClipboard()
		return True
	except Exception as e:
		log.error(f"Clipboard copy error: {e}")
		return False

def kill_not_responding_apps():
	try:
		output = subprocess.check_output('tasklist /v /fi "status eq not responding"', shell=True, text=True, timeout=5)
		lines = output.splitlines()
		pids = []
		for line in lines:
			if "PID" in line or "===" in line or not line.strip():
				continue
			parts = line.split()
			if len(parts) >= 2:
				try:
					pid = int(parts[1])
					pids.append(pid)
				except ValueError:
					continue
		count = 0
		for pid in pids:
			try:
				subprocess.run(f'taskkill /pid {pid} /f', shell=True, check=True, timeout=5)
				count += 1
			except Exception as e:
				log.warning(f"Failed to kill PID {pid}: {e}")
		return count
	except subprocess.CalledProcessError as e:
		if e.returncode == 1:
			return 0
		log.error(f"kill_not_responding_apps error: {e}")
		return 0
	except Exception as e:
		log.error(f"kill_not_responding_apps unexpected error: {e}")
		return 0

def restart_explorer():
	try:
		subprocess.run("taskkill /f /im explorer.exe", shell=True, check=True, timeout=5)
		subprocess.run("start explorer.exe", shell=True, check=True, timeout=5)
		return True
	except Exception as e:
		log.error(f"Failed to restart explorer: {e}")
		return False

def empty_recycle_bin():
	try:
		rbInfo = SHQUERYRBINFO()
		rbInfo.cbSize = ctypes.sizeof(SHQUERYRBINFO)
		queryStatus = shell32.SHQueryRecycleBinW(None, ctypes.byref(rbInfo))
		
		itemsToRemove = 0
		if queryStatus == 0:
			itemsToRemove = rbInfo.i64NumItems
			if itemsToRemove == 0:
				return True, _("Recycle bin is already empty.")
		else:
			log.warning(f"SHQueryRecycleBinW returned {queryStatus}")

		emptyStatus = shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
		if emptyStatus == 0:
			return True, _("Recycle bin emptied. {count} items removed.").format(count=itemsToRemove)
		else:
			log.error(f"SHEmptyRecycleBinW failed with code {emptyStatus}")
			return False, _("Failed to empty recycle bin.")
	except Exception as e:
		log.error(f"Empty recycle bin error: {e}")
		return False, _("Failed to empty recycle bin.")

def run_disk_cleanup_silent():
	try:
		result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cleanmgr.exe", "/sagerun:1", None, 0)
		if result > 32:
			return True
		else:
			result2 = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cleanmgr.exe", "/verylowdisk", None, 0)
			return result2 > 32
	except Exception as e:
		log.error(f"Failed to run disk cleanup: {e}")
		return False

def clear_ram_cache():
	try:
		class MEMORYSTATUSEX(ctypes.Structure):
			_fields_ = [
				("dwLength", wintypes.DWORD),
				("dwMemoryLoad", wintypes.DWORD),
				("ullTotalPhys", ctypes.c_ulonglong),
				("ullAvailPhys", ctypes.c_ulonglong),
				("ullTotalPageFile", ctypes.c_ulonglong),
				("ullAvailPageFile", ctypes.c_ulonglong),
				("ullTotalVirtual", ctypes.c_ulonglong),
				("ullAvailVirtual", ctypes.c_ulonglong),
				("ullAvailExtendedVirtual", ctypes.c_ulonglong),
			]
		memoryStatus = MEMORYSTATUSEX()
		memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
		kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
		available_before = memoryStatus.ullAvailPhys

		for proc in psutil.process_iter(['pid', 'name']):
			try:
				if proc.info['name'] in ['System', 'Idle', 'Memory Compression', 'nvda.exe']:
					continue
				hProcess = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA | PROCESS_VM_READ, False, proc.info['pid'])
				if hProcess:
					psapi.EmptyWorkingSet(hProcess)
					kernel32.CloseHandle(hProcess)
			except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
				continue

		kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
		available_after = memoryStatus.ullAvailPhys
		freed = available_after - available_before
		return freed if freed > 0 else 0
	except Exception as e:
		log.error(f"Failed to clear RAM cache: {e}")
		return -1

def get_startup_items():
	items = []
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
		i = 0
		while True:
			name, value, _dummy = winreg.EnumValue(key, i)
			items.append({
				'name': name,
				'type': 'Registry (User)',
				'status': _("Enabled"),
				'location': 'HKCU\\...\\Run',
				'data': value,
				'reg_path': r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
				'value_name': name
			})
			i += 1
	except OSError:
		pass
	try:
		key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
		i = 0
		while True:
			name, value, _dummy = winreg.EnumValue(key, i)
			items.append({
				'name': name,
				'type': 'Registry (Machine)',
				'status': _("Enabled"),
				'location': 'HKLM\\...\\Run',
				'data': value,
				'reg_path': r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run",
				'value_name': name
			})
			i += 1
	except OSError:
		pass
	user_startup = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
	if os.path.exists(user_startup):
		for f in os.listdir(user_startup):
			full = os.path.join(user_startup, f)
			if os.path.isfile(full) and (f.endswith('.lnk') or f.endswith('.exe')):
				items.append({
					'name': f,
					'type': 'Startup Folder (User)',
					'status': _("Enabled"),
					'location': user_startup,
					'data': full,
					'file_path': full
				})
	common_startup = os.path.join(os.getenv('PROGRAMDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
	if os.path.exists(common_startup):
		for f in os.listdir(common_startup):
			full = os.path.join(common_startup, f)
			if os.path.isfile(full) and (f.endswith('.lnk') or f.endswith('.exe')):
				items.append({
					'name': f,
					'type': 'Startup Folder (All Users)',
					'status': _("Enabled"),
					'location': common_startup,
					'data': full,
					'file_path': full
				})
	return items

def disable_startup_item(item, backupDir):
	if 'reg_path' in item:
		try:
			if 'HKCU' in item['reg_path']:
				root = winreg.HKEY_CURRENT_USER
				subkey = item['reg_path'].replace(r'HKCU\\', '')
			else:
				root = winreg.HKEY_LOCAL_MACHINE
				subkey = item['reg_path'].replace(r'HKLM\\', '')
			key = winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE)
			winreg.DeleteValue(key, item['value_name'])
			winreg.CloseKey(key)
			return True
		except Exception as e:
			log.error(f"Failed to disable registry startup item: {e}")
			return False
	elif 'file_path' in item:
		try:
			dest = os.path.join(backupDir, os.path.basename(item['file_path']))
			if os.path.exists(dest):
				name, ext = os.path.splitext(dest)
				dest = f"{name}_{int(time.time())}{ext}"
			shutil.move(item['file_path'], dest)
			return True
		except Exception as e:
			log.error(f"Failed to move startup shortcut: {e}")
			return False
	return False

def enable_startup_item(item, backupDir):
	if 'reg_path' in item:
		try:
			if 'HKCU' in item['reg_path']:
				root = winreg.HKEY_CURRENT_USER
				subkey = item['reg_path'].replace(r'HKCU\\', '')
			else:
				root = winreg.HKEY_LOCAL_MACHINE
				subkey = item['reg_path'].replace(r'HKLM\\', '')
			key = winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE)
			winreg.SetValueEx(key, item['value_name'], 0, winreg.REG_SZ, item['data'])
			winreg.CloseKey(key)
			return True
		except Exception as e:
			log.error(f"Failed to enable registry startup item: {e}")
			return False
	elif 'file_path' in item:
		base = os.path.basename(item['file_path'])
		candidates = [f for f in os.listdir(backupDir) if f.startswith(base) or f == base]
		if not candidates:
			log.error("No backup found for shortcut")
			return False
		src = os.path.join(backupDir, candidates[0])
		try:
			shutil.move(src, item['file_path'])
			return True
		except Exception as e:
			log.error(f"Failed to restore shortcut: {e}")
			return False
	return False

def get_available_drives():
	drives = []
	for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
		path = f"{letter}:\\"
		if os.path.exists(path):
			drives.append(path)
	return drives

def optimize_drive(drive):
	try:
		result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "defrag.exe", f"{drive} /O", None, 0)
		return result > 32, ""
	except Exception as e:
		log.error(f"Optimize drive error: {e}")
		return False, str(e)

# ------------------------------------------------------------
# Manage Services catalog
#
# safety: "safe"    - no known effect on speech, audio, Braille or other
#                     accessibility use; included in "Disable all".
#         "caution" - can affect something an assistive-technology user may rely
#                     on (printing/embossers, Start-menu search, troubleshooters,
#                     touch/voice input, security updates...). Never touched by
#                     "Disable all"; only changed when selected explicitly, after
#                     a warning.
# enableType: start type used by "Enable" when no original value was recorded for
#             the service. Best-effort Windows 10/11 defaults, not verified on
#             every build - any service this tool disables has its real start
#             type recorded first and restored exactly instead.
# Services that do not exist on the machine are simply left out of the list.
# The audio stack (Audiosrv, AudioEndpointBuilder, MMCSS), Themes (high contrast),
# TextInputManagementService and the Bluetooth services are deliberately NOT here,
# and cmd_tools refuses to change them even if asked.
# ------------------------------------------------------------
SERVICE_CATALOG = [
	{"name": "Spooler", "safety": "caution", "enableType": "auto",
		"note": _("Needed for printing, including braille embossers")},
	{"name": "WSearch", "safety": "caution", "enableType": "delayed-auto",
		"note": _("Disabling slows Start menu and File Explorer search")},
	{"name": "wuauserv", "safety": "caution", "enableType": "demand",
		"note": _("Disabling stops Windows security updates")},
	{"name": "DPS", "safety": "caution", "enableType": "auto",
		"note": _("Needed by Windows troubleshooters, including the audio one")},
	{"name": "SysMain", "safety": "safe", "enableType": "auto", "note": ""},
	{"name": "DiagTrack", "safety": "safe", "enableType": "auto", "note": ""},
	{"name": "dmwappushservice", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "lfsvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "MapsBroker", "safety": "safe", "enableType": "delayed-auto", "note": ""},
	{"name": "PcaSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "WMPNetworkSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "RemoteRegistry", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "XboxNetApiSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "XblAuthManager", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "XblGameSave", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "XboxGipSvc", "safety": "caution", "enableType": "demand",
		"note": _("Needed for Xbox controllers, including the Adaptive Controller")},
	{"name": "TabletInputService", "safety": "caution", "enableType": "demand",
		"note": _("Needed for touch keyboard, handwriting and voice typing")},
	{"name": "Fax", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "WerSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "DoSvc", "safety": "safe", "enableType": "delayed-auto", "note": ""},
	{"name": "diagnosticshub.standardcollector.service", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "PhoneSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "RetailDemo", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "icssvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "WpcMonSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "SEMgrSvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "WalletService", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "wisvc", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "AJRouter", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "WebClient", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "TapiSrv", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "SmsRouter", "safety": "safe", "enableType": "demand", "note": ""},
	{"name": "SCardSvr", "safety": "caution", "enableType": "demand",
		"note": _("Needed for smart card sign-in and some banking cards")},
	{"name": "stisvc", "safety": "caution", "enableType": "auto",
		"note": _("Needed for scanners and cameras, including scanning documents for OCR")},
]

# Windows' own display names, used only to label a catalog service that is not
# installed on this machine (installed ones take the name straight from the system).
_SERVICE_TITLES = {
	"Spooler": "Print Spooler",
	"WSearch": "Windows Search",
	"wuauserv": "Windows Update",
	"DPS": "Diagnostic Policy Service",
	"SysMain": "SysMain",
	"DiagTrack": "Connected User Experiences and Telemetry",
	"dmwappushservice": "Device Management Wireless Application Protocol (WAP) Push message Routing Service",
	"lfsvc": "Geolocation Service",
	"MapsBroker": "Downloaded Maps Manager",
	"PcaSvc": "Program Compatibility Assistant Service",
	"WMPNetworkSvc": "Windows Media Player Network Sharing Service",
	"RemoteRegistry": "Remote Registry",
	"XboxNetApiSvc": "Xbox Live Networking Service",
	"XblAuthManager": "Xbox Live Auth Manager",
	"XblGameSave": "Xbox Live Game Save",
	"XboxGipSvc": "Xbox Accessory Management Service",
	"TabletInputService": "Touch Keyboard and Handwriting Panel Service",
	"Fax": "Fax",
	"WerSvc": "Windows Error Reporting Service",
	"DoSvc": "Delivery Optimization",
	"diagnosticshub.standardcollector.service": "Microsoft (R) Diagnostics Hub Standard Collector Service",
	"PhoneSvc": "Phone Service",
	"RetailDemo": "Retail Demo Service",
	"icssvc": "Windows Mobile Hotspot Service",
	"WpcMonSvc": "Parental Controls",
	"SEMgrSvc": "Payments and NFC/SE Manager",
	"WalletService": "WalletService",
	"wisvc": "Windows Insider Service",
	"AJRouter": "AllJoyn Router Service",
	"WebClient": "WebClient",
	"TapiSrv": "Telephony",
	"SmsRouter": "Microsoft Windows SMS Router Service",
	"SCardSvr": "Smart Card",
	"stisvc": "Windows Image Acquisition (WIA)",
}

_SC_EXE = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "sc.exe")


def _run_sc(args, timeout=5):
	"""Run sc.exe (fully qualified, no shell) and return its stdout, or "" when the
	service is missing or the call fails."""
	try:
		result = subprocess.run(
			[_SC_EXE] + args, capture_output=True, text=True, timeout=timeout,
			creationflags=subprocess.CREATE_NO_WINDOW
		)
	except (subprocess.TimeoutExpired, OSError) as e:
		log.debug(f"sc {args} failed: {e}")
		return ""
	if result.returncode != 0:
		return ""
	return result.stdout


def _parse_start_type(qcOutput):
	for line in qcOutput.splitlines():
		if "START_TYPE" not in line:
			continue
		if "DISABLED" in line:
			return "disabled"
		if "DEMAND_START" in line:
			return "demand"
		if "AUTO_START" in line:
			return "delayed-auto" if "DELAYED" in line else "auto"
	return "unknown"


def _start_type_label(startTypeKey):
	return {
		"disabled": _("Disabled"),
		"demand": _("Manual"),
		"auto": _("Automatic"),
		"delayed-auto": _("Automatic (Delayed Start)"),
	}.get(startTypeKey, _("Unknown"))


def get_service_states():
	"""Return the catalog entries that exist on this machine, with live start type,
	run state, real display name and description. The start type comes from
	"sc qc" - the previous version read it from "sc query", which never prints
	START_TYPE, so every service showed "Unknown". Runs several sc.exe processes,
	so call it from a background thread, never NVDA's main thread."""
	runStates = {}
	allOutput = _run_sc(["query", "type=", "service", "state=", "all"], timeout=15)
	currentName = None
	for line in allOutput.splitlines():
		line = line.strip()
		if line.startswith("SERVICE_NAME:"):
			currentName = line.split(":", 1)[1].strip().lower()
		elif line.startswith("STATE") and currentName:
			if "RUNNING" in line:
				runStates[currentName] = _("Running")
			elif "STOPPED" in line:
				runStates[currentName] = _("Stopped")
			else:
				runStates[currentName] = _("Other")

	services = []
	for entry in SERVICE_CATALOG:
		name = entry["name"]
		qcOutput = _run_sc(["qc", name])
		if not qcOutput:
			log.debug(f"Service {name} not found on this system, listing it as not installed")
			services.append({
				"name": name,
				"display_name": _SERVICE_TITLES.get(name, name),
				"description": "",
				"start_type_key": "missing",
				"start_type": _("Not installed"),
				"status": "",
				"safety": entry["safety"],
				"note": entry["note"],
				"enable_type": entry["enableType"],
			})
			continue
		displayName = name
		for line in qcOutput.splitlines():
			if "DISPLAY_NAME" in line:
				displayName = line.split(":", 1)[1].strip() or name
				break
		description = ""
		for line in _run_sc(["qdescription", name]).splitlines():
			if "DESCRIPTION:" in line:
				description = line.split(":", 1)[1].strip()
				break
		startTypeKey = _parse_start_type(qcOutput)
		services.append({
			"name": name,
			"display_name": displayName,
			"description": description,
			"start_type_key": startTypeKey,
			"start_type": _start_type_label(startTypeKey),
			"status": runStates.get(name.lower(), _("Stopped")),
			"safety": entry["safety"],
			"note": entry["note"],
			"enable_type": entry["enableType"],
		})
	services.sort(key=lambda svc: (svc["display_name"].casefold(), svc["name"].casefold()))
	return services


def _service_state_path(configDir):
	return os.path.join(configDir, "services_state.json")


def load_service_state(configDir):
	"""Original start types recorded before this tool disabled a service. Falls back
	to the rolling backup copy if the main file is unreadable."""
	import json
	statePath = _service_state_path(configDir)
	for candidate in (statePath, statePath + ".bak"):
		try:
			with open(candidate, "r", encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, dict):
				return data
		except FileNotFoundError:
			continue
		except (OSError, ValueError) as e:
			log.warning(f"Could not read service state file {candidate}: {e}")
	return {}


def save_service_state(configDir, state):
	"""Atomic write (temp file + fsync + backup + os.replace) so a crash mid-write
	cannot leave a truncated state file."""
	import json
	statePath = _service_state_path(configDir)
	tempPath = statePath + ".tmp"
	try:
		with open(tempPath, "w", encoding="utf-8") as f:
			json.dump(state, f, indent=1)
			f.flush()
			os.fsync(f.fileno())
		if os.path.exists(statePath):
			shutil.copy2(statePath, statePath + ".bak")
		os.replace(tempPath, statePath)
		return True
	except OSError as e:
		log.error(f"Could not save service state file: {e}")
		return False


def apply_service_action(configDir, services, action):
	"""Disable or enable the given service dicts (from get_service_states).
	"disable" records each service's current start type first, so "enable" can put
	back exactly what was there instead of guessing. Services already in the target
	state are skipped. Blocking (elevated batch + UAC prompt): call from a
	background thread only. Returns (ok, payload): payload is a
	{serviceName: True/False} dict on success, or an error message string."""
	from . import cmd_tools
	state = load_service_state(configDir)
	changes = []
	for svc in services:
		name = svc["name"]
		if svc["start_type_key"] == "missing":
			continue
		if action == "disable":
			if svc["start_type_key"] == "disabled":
				continue
			if svc["start_type_key"] != "unknown":
				state[name] = svc["start_type_key"]
			changes.append({"name": name, "action": "disable"})
		else:
			if svc["start_type_key"] != "disabled":
				continue
			startType = state.get(name) or svc["enable_type"]
			changes.append({"name": name, "action": "enable", "startType": startType})
	if not changes:
		return False, _("Nothing to change - the selected services are already in that state.")
	if action == "disable":
		save_service_state(configDir, state)
	return cmd_tools.run_service_changes(configDir, changes)


def open_services_mmc():
	try:
		subprocess.Popen("services.msc", shell=True)
		return True
	except Exception as e:
		log.error(f"Failed to open services.msc: {e}")
		return False

def clean_prefetch_recent():
	try:
		totalRemoved = 0
		prefetchPath = r"C:\Windows\Prefetch"
		if os.path.exists(prefetchPath):
			for prefetchFile in os.listdir(prefetchPath):
				if prefetchFile.lower() in ("readyboot", "readyboot.ini"):
					continue
				fullPath = os.path.join(prefetchPath, prefetchFile)
				try:
					if os.path.isfile(fullPath):
						os.remove(fullPath)
						totalRemoved += 1
				except Exception:
					pass
					
		recentPath = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Recent')
		if os.path.exists(recentPath):
			for recentFile in os.listdir(recentPath):
				fullPath = os.path.join(recentPath, recentFile)
				try:
					if os.path.isfile(fullPath):
						os.remove(fullPath)
						totalRemoved += 1
				except Exception:
					pass
					
		return True, totalRemoved
	except Exception as e:
		log.error(f"Error cleaning prefetch/recent: {e}")
		return False, str(e)


def list_open_with_backups(config_dir):
	"""Return (folderDisplayName, regFilePath) tuples for each saved Open With
	association backup (a FileExts registry export - see cmd_tools.py), most
	recently created first."""
	backupsRoot = os.path.join(config_dir, "openWith")
	results = []
	try:
		if not os.path.isdir(backupsRoot):
			return results
		for entryName in os.listdir(backupsRoot):
			entryPath = os.path.join(backupsRoot, entryName)
			regPath = os.path.join(entryPath, "FileExtsBackup.reg")
			if os.path.isfile(regPath):
				results.append((entryName, regPath))
		results.sort(key=lambda pair: os.path.getmtime(pair[1]), reverse=True)
	except OSError as e:
		log.error(f"Failed to list Open With backups: {e}")
	return results
