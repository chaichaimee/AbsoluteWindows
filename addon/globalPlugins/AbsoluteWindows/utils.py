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
from ctypes import wintypes
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except:
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
		output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
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
		output = subprocess.check_output("netsh interface show interface", shell=True, text=True)
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
		value, reg_type = winreg.QueryValueEx(key_handle, "EnableLUA")
		winreg.CloseKey(key_handle)
		is_enabled = (value == 1)
		log.info(f"UAC registry EnableLUA = {value} (type {reg_type}) => enabled={is_enabled}")
		return is_enabled
	except FileNotFoundError:
		log.warning("EnableLUA registry key not found, assuming UAC enabled")
		return True
	except Exception as e:
		log.error(f"Failed to read UAC registry: {e}, falling back to reg query")
		try:
			cmd = 'reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA'
			output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
			for line in output.splitlines():
				if "EnableLUA" in line:
					parts = line.split()
					if len(parts) >= 3:
						value_str = parts[-1]
						if value_str == "0x1":
							log.info("reg query returned EnableLUA=0x1")
							return True
						elif value_str == "0x0":
							log.info("reg query returned EnableLUA=0x0")
							return False
			log.warning("reg query could not parse EnableLUA value, assuming True")
			return True
		except subprocess.CalledProcessError as e:
			log.error(f"reg query failed: {e}, assuming UAC enabled")
			return True
		except Exception as e2:
			log.error(f"Unexpected error in fallback: {e2}, assuming True")
			return True

def _setUACRegistry(value):
	cmd = f'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA /t REG_DWORD /d {value} /f'
	try:
		result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "reg.exe", cmd, None, 0)
		if result <= 32:
			log.error(f"Failed to launch reg.exe: {result}")
			return False
		time.sleep(0.5)
		current = isUACEnabled()
		expected = (value == 1)
		if current == expected:
			log.info(f"UAC registry set to {value} and verified")
			return True
		else:
			log.warning(f"UAC registry set to {value} but current is {current}, retrying with subprocess")
			try:
				subprocess.run(f'reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA /t REG_DWORD /d {value} /f', shell=True, check=True, timeout=5)
				time.sleep(0.3)
				if isUACEnabled() == expected:
					return True
			except Exception as e2:
				log.error(f"Fallback reg add also failed: {e2}")
			return False
	except Exception as e:
		log.error(f"_setUACRegistry exception: {e}")
		return False

def disableUAC():
	return _setUACRegistry(0)

def enableUAC():
	return _setUACRegistry(1)

def cleanTempFolders():
	overall_success = True
	userTemp = os.environ.get("TEMP", "")
	if userTemp and os.path.exists(userTemp):
		try:
			for item in os.listdir(userTemp):
				itemPath = os.path.join(userTemp, item)
				try:
					if os.path.isfile(itemPath):
						os.remove(itemPath)
					elif os.path.isdir(itemPath):
						shutil.rmtree(itemPath, ignore_errors=True)
				except Exception as e:
					log.warning(f"Could not delete {itemPath}: {e}")
		except Exception as e:
			log.error(f"User temp clean error: {e}")
			overall_success = False
	winTemp = r"C:\Windows\Temp"
	if os.path.exists(winTemp):
		try:
			for item in os.listdir(winTemp):
				itemPath = os.path.join(winTemp, item)
				try:
					if os.path.isfile(itemPath):
						os.remove(itemPath)
					elif os.path.isdir(itemPath):
						shutil.rmtree(itemPath, ignore_errors=True)
				except Exception as e:
					log.warning(f"Could not delete {itemPath}: {e}")
		except Exception as e:
			log.error(f"Windows temp clean error: {e}")
			overall_success = False
	return overall_success

def cleanRunHistory():
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
		i = 0
		valueNames = []
		while True:
			try:
				name, _, _ = winreg.EnumValue(key, i)
				valueNames.append(name)
				i += 1
			except OSError:
				break
		for name in valueNames:
			if name != "MRUList":
				winreg.DeleteValue(key, name)
		winreg.SetValueEx(key, "MRUList", 0, winreg.REG_SZ, "")
		winreg.CloseKey(key)
		return True
	except Exception as e:
		log.error(f"Run history clean error: {e}")
		return False

def get_current_wifi_password():
	try:
		output = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True)
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
		output = subprocess.check_output(cmd, shell=True, text=True)
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
		output = subprocess.check_output('tasklist /v /fi "status eq not responding"', shell=True, text=True)
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

def _is_recycle_bin_empty():
	try:
		info = SHQUERYRBINFO()
		info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
		result = shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
		if result == 0:
			return info.i64NumItems == 0
		else:
			log.warning(f"SHQueryRecycleBinW returned {result}")
			return False
	except Exception as e:
		log.warning(f"Failed to query recycle bin: {e}")
		return False

def empty_recycle_bin():
	try:
		if _is_recycle_bin_empty():
			return True, _("Recycle bin is already empty.")
		result = shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND)
		if result == 0:
			return True, _("Recycle bin emptied.")
		else:
			log.error(f"SHEmptyRecycleBinW failed with code {result}")
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

def get_suggested_services():
	suggested = [
		"SysMain", "WSearch", "XboxGipSvc", "XboxNetApiSvc", "XblAuthManager",
		"DiagTrack", "dmwappushservice", "lfsvc", "MapsBroker", "PcaSvc",
		"WMPNetworkSvc", "RemoteRegistry", "Fax", "TabletInputService"
	]
	services = []
	for svc in suggested:
		try:
			out = subprocess.check_output(f'sc query {svc}', shell=True, text=True, stderr=subprocess.DEVNULL)
			start_type = "Unknown"
			status = "Unknown"
			for line in out.splitlines():
				if "START_TYPE" in line:
					if "DISABLED" in line:
						start_type = _("Disabled")
					elif "DEMAND_START" in line:
						start_type = _("Manual")
					elif "AUTO_START" in line:
						start_type = _("Automatic")
				if "STATE" in line:
					if "RUNNING" in line:
						status = _("Running")
					elif "STOPPED" in line:
						status = _("Stopped")
			display = svc
			try:
				out2 = subprocess.check_output(f'sc qdescription {svc}', shell=True, text=True)
				for line in out2.splitlines():
					if "DESCRIPTION:" in line:
						display = line.split(":",1)[1].strip()
						break
			except:
				pass
			services.append({
				'name': svc,
				'display_name': display,
				'start_type': start_type,
				'status': status
			})
		except:
			continue
	return services

def disable_service(service_name):
	try:
		subprocess.run(f'sc stop {service_name}', shell=True, check=False, timeout=10)
		subprocess.run(f'sc config {service_name} start= disabled', shell=True, check=True, timeout=5)
		return True, ""
	except subprocess.CalledProcessError as e:
		log.error(f"Failed to disable service {service_name}: {e}")
		return False, str(e)

def enable_service(service_name):
	try:
		subprocess.run(f'sc config {service_name} start= delayed-auto', shell=True, check=True, timeout=5)
		subprocess.run(f'sc start {service_name}', shell=True, check=False, timeout=10)
		return True, ""
	except subprocess.CalledProcessError as e:
		log.error(f"Failed to enable service {service_name}: {e}")
		return False, str(e)

def open_services_mmc():
	try:
		subprocess.Popen("services.msc", shell=True)
		return True
	except Exception as e:
		log.error(f"Failed to open services.msc: {e}")
		return False

def clean_prefetch_recent():
	try:
		prefetch_dir = r"C:\Windows\Prefetch"
		if os.path.exists(prefetch_dir):
			for f in os.listdir(prefetch_dir):
				if f.lower() in ("readyboot", "readyboot.ini"):
					continue
				full = os.path.join(prefetch_dir, f)
				try:
					if os.path.isfile(full):
						os.remove(full)
				except Exception as e:
					log.warning(f"Could not delete prefetch file {full}: {e}")
		recent_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Recent')
		if os.path.exists(recent_dir):
			for f in os.listdir(recent_dir):
				full = os.path.join(recent_dir, f)
				try:
					if os.path.isfile(full):
						os.remove(full)
				except Exception as e:
					log.warning(f"Could not delete recent file {full}: {e}")
		return True, ""
	except Exception as e:
		log.error(f"Error cleaning prefetch/recent: {e}")
		return False, str(e)