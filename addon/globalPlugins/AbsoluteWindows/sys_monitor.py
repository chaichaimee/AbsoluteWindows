# sys_monitor.py

import subprocess
import os
import threading
import time
import ctypes
from ctypes import wintypes
from logHandler import log
import addonHandler
import wx
import winVersion
from . import utils

addonHandler.initTranslation()

try:
	_ = addonHandler.getTranslation()
except Exception:
	def _(x): return x

kernel32 = ctypes.windll.kernel32
kernel32.GetTickCount64.restype = ctypes.c_ulonglong
kernel32.GetDiskFreeSpaceExW.argtypes = [
	wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ulonglong),
	ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong)
]
kernel32.GetDiskFreeSpaceExW.restype = wintypes.BOOL
kernel32.GetSystemPowerStatus.argtypes = [ctypes.c_void_p]
kernel32.GetSystemPowerStatus.restype = wintypes.BOOL

DRIVE_FIXED = 3


class FILETIME(ctypes.Structure):
	_fields_ = [
		("dwLowDateTime", wintypes.DWORD),
		("dwHighDateTime", wintypes.DWORD),
	]


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


class SYSTEM_POWER_STATUS(ctypes.Structure):
	_fields_ = [
		("ACLineStatus", ctypes.c_ubyte),
		("BatteryFlag", ctypes.c_ubyte),
		("BatteryLifePercent", ctypes.c_ubyte),
		("SystemStatusFlag", ctypes.c_ubyte),
		("BatteryLifeTime", wintypes.DWORD),
		("BatteryFullLifeTime", wintypes.DWORD),
	]


def _getSystemRoot():
	return os.environ.get('SystemRoot', 'C:\\Windows')


def _runCommand(cmd, timeout=1):
	try:
		startupinfo = subprocess.STARTUPINFO()
		startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		result = subprocess.run(
			cmd,
			capture_output=True,
			text=True,
			timeout=timeout,
			startupinfo=startupinfo,
			creationflags=subprocess.CREATE_NO_WINDOW,
			encoding='utf-8',
			errors='replace'
		)
		return result.stdout.strip()
	except subprocess.TimeoutExpired:
		return ""
	except Exception:
		return ""


def _runPowerShell(script, timeout=1):
	systemRoot = _getSystemRoot()
	powershell = os.path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
	if not os.path.exists(powershell):
		powershell = 'powershell.exe'
	return _runCommand([powershell, '-NoLogo', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-NoProfile', '-Command', script], timeout)


def _fileTimeToInt(fileTime):
	return (fileTime.dwHighDateTime << 32) | fileTime.dwLowDateTime


def get_cpu_usage():
	try:
		idleFirst = FILETIME()
		kernelFirst = FILETIME()
		userFirst = FILETIME()
		kernel32.GetSystemTimes(ctypes.byref(idleFirst), ctypes.byref(kernelFirst), ctypes.byref(userFirst))
		time.sleep(0.2)
		idleSecond = FILETIME()
		kernelSecond = FILETIME()
		userSecond = FILETIME()
		kernel32.GetSystemTimes(ctypes.byref(idleSecond), ctypes.byref(kernelSecond), ctypes.byref(userSecond))

		idleDelta = _fileTimeToInt(idleSecond) - _fileTimeToInt(idleFirst)
		totalDelta = (_fileTimeToInt(kernelSecond) - _fileTimeToInt(kernelFirst)) + (_fileTimeToInt(userSecond) - _fileTimeToInt(userFirst))
		if totalDelta <= 0:
			return _("??%")
		busyPercent = ((totalDelta - idleDelta) / totalDelta) * 100
		return _("{}%").format(round(busyPercent))
	except Exception:
		return _("??%")


def get_ram_usage():
	try:
		memoryStatus = MEMORYSTATUSEX()
		memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
		kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
		used_bytes = memoryStatus.ullTotalPhys - memoryStatus.ullAvailPhys
		used_gb = used_bytes / (1024 ** 3)
		total_gb = memoryStatus.ullTotalPhys / (1024 ** 3)
		percent = (used_bytes / memoryStatus.ullTotalPhys) * 100
		return _("{:.2F} GB of {:.2F} GB used ({:.1F}%)").format(used_gb, total_gb, round(percent, 1))
	except Exception:
		return _("??%")


def get_disk_usage():
	disk_info = []
	try:
		bitmask = kernel32.GetLogicalDrives()
		for i in range(26):
			if not (bitmask & (1 << i)):
				continue
			driveLetter = chr(ord('A') + i)
			path = f"{driveLetter}:\\"
			if kernel32.GetDriveTypeW(path) != DRIVE_FIXED:
				continue
			freeBytesAvailable = ctypes.c_ulonglong(0)
			totalBytes = ctypes.c_ulonglong(0)
			totalFreeBytes = ctypes.c_ulonglong(0)
			success = kernel32.GetDiskFreeSpaceExW(
				path,
				ctypes.byref(freeBytesAvailable),
				ctypes.byref(totalBytes),
				ctypes.byref(totalFreeBytes)
			)
			if not success or totalBytes.value == 0:
				continue
			used_bytes = totalBytes.value - totalFreeBytes.value
			used_gb = used_bytes / (1024 ** 3)
			total_gb = totalBytes.value / (1024 ** 3)
			percent = (used_bytes / totalBytes.value) * 100
			disk_info.append(_("{} {:.1F} GB of {:.1F} GB used ({:.0F}%)").format(f"{driveLetter}:", used_gb, total_gb, percent))
	except Exception:
		pass
	return disk_info


# One Get-Counter call for all four rate counters. The old code started four separate
# PowerShell processes with a 1 second timeout each; PowerShell's own startup plus
# Get-Counter's built-in 1 second sample interval is longer than that, so every one of
# them timed out and the whole block cost ~4 seconds while never producing a value.
_COUNTER_SCRIPT = (
	"Get-Counter -Counter '\\PhysicalDisk(_Total)\\Disk Read Bytes/sec',"
	"'\\PhysicalDisk(_Total)\\Disk Write Bytes/sec',"
	"'\\Network Interface(*)\\Bytes Received/sec',"
	"'\\Network Interface(*)\\Bytes Sent/sec' -ErrorAction SilentlyContinue "
	"| Select-Object -ExpandProperty CounterSamples "
	"| ForEach-Object { [string]::Format([cultureinfo]::InvariantCulture, '{0}|{1}', $_.Path, $_.CookedValue) }"
)
_COUNTER_TIMEOUT = 4
_MONITOR_DEADLINE = 4.5


def _parseCounterOutput(output):
	"""Sum the counter samples by kind. Returns (totals, seenKinds); pure text
	parsing, kept separate from the PowerShell call so it can be checked on its own."""
	totals = {"read": 0.0, "write": 0.0, "rx": 0.0, "tx": 0.0}
	seen = set()
	for line in output.splitlines():
		path, _sep, value = line.rpartition("|")
		path = path.lower()
		try:
			number = float(value)
		except ValueError:
			continue
		if "disk read bytes/sec" in path:
			kind = "read"
		elif "disk write bytes/sec" in path:
			kind = "write"
		elif "bytes received/sec" in path:
			kind = "rx"
		elif "bytes sent/sec" in path:
			kind = "tx"
		else:
			continue
		totals[kind] += number
		seen.add(kind)
	return totals, seen


def get_performance_counters():
	"""Returns {"disk_activity": text or None, "network_speed": text or None}."""
	result = {"disk_activity": None, "network_speed": None}
	output = _runPowerShell(_COUNTER_SCRIPT, timeout=_COUNTER_TIMEOUT)
	if not output:
		return result
	totals, seen = _parseCounterOutput(output)
	megabyte = 1024 * 1024
	if {"read", "write"} <= seen:
		result["disk_activity"] = _("{:.1F} MB/s read, {:.1F} MB/s write").format(
			totals["read"] / megabyte, totals["write"] / megabyte)
	if {"rx", "tx"} <= seen and (totals["rx"] > 0 or totals["tx"] > 0):
		result["network_speed"] = _("{:.1F} MB/s down, {:.1F} MB/s up").format(
			totals["rx"] / megabyte, totals["tx"] / megabyte)
	return result


def get_network_status():
	if utils.isInternetConnected():
		return _("Connected")
	return _("Disconnected")


def get_battery_info():
	try:
		powerStatus = SYSTEM_POWER_STATUS()
		success = kernel32.GetSystemPowerStatus(ctypes.byref(powerStatus))
		if not success:
			return None
		if powerStatus.BatteryFlag in (128, 255):
			return None
		percent = powerStatus.BatteryLifePercent
		if percent > 100:
			return None
		if powerStatus.ACLineStatus == 1:
			status_text = _("Fully Charged") if powerStatus.BatteryFlag == 8 else _("Charging")
		else:
			status_text = _("Low") if powerStatus.BatteryFlag == 2 else _("Discharging")
		return _("{}% ({})").format(percent, status_text)
	except Exception:
		return None


def get_uptime():
	try:
		uptimeMs = kernel32.GetTickCount64()
		totalSeconds = int(uptimeMs / 1000)
		days, remainder = divmod(totalSeconds, 86400)
		hours, remainder = divmod(remainder, 3600)
		minutes, seconds = divmod(remainder, 60)

		parts = []
		if days > 0:
			parts.append(_("{} day{}").format(days, "s" if days > 1 else ""))
		if hours > 0:
			parts.append(_("{} hour{}").format(hours, "s" if hours > 1 else ""))
		if minutes > 0:
			parts.append(_("{} minute{}").format(minutes, "s" if minutes > 1 else ""))
		if seconds > 0:
			parts.append(_("{} second{}").format(seconds, "s" if seconds > 1 else ""))

		if not parts:
			return _("<1 minute")
		return ", ".join(parts)
	except Exception:
		return _("??")


def _signalLabel(signalText):
	if not signalText.endswith("%"):
		return signalText
	value = int(signalText[:-1])
	if value >= 80:
		return _("Excellent")
	if value >= 60:
		return _("Good")
	if value >= 40:
		return _("Fair")
	if value >= 20:
		return _("Weak")
	return _("Very Weak")


def get_wifi_details():
	"""Returns (ssid, signalLabel) from a single netsh call; (None, None) when there
	is no connected Wi-Fi interface. The old code ran netsh twice, once per field."""
	netsh = os.path.join(_getSystemRoot(), "System32", "netsh.exe")
	output = _runCommand([netsh, "wlan", "show", "interfaces"], 2)
	ssid = None
	signal = None
	for line in output.splitlines():
		stripped = line.strip()
		if ssid is None and stripped.startswith("SSID") and not stripped.startswith("BSSID"):
			ssid = stripped.partition(":")[2].strip() or None
		elif signal is None and stripped.startswith("Signal"):
			rawSignal = stripped.partition(":")[2].strip()
			try:
				signal = _signalLabel(rawSignal) if rawSignal else None
			except ValueError:
				signal = rawSignal or None
	if not ssid:
		return None, None
	return ssid, signal


class DISPLAY_DEVICEW(ctypes.Structure):
	_fields_ = [
		("cb", wintypes.DWORD),
		("DeviceName", wintypes.WCHAR * 32),
		("DeviceString", wintypes.WCHAR * 128),
		("StateFlags", wintypes.DWORD),
		("DeviceID", wintypes.WCHAR * 128),
		("DeviceKey", wintypes.WCHAR * 128),
	]


def get_gpu_info():
	"""First real display adapter name via EnumDisplayDevicesW, which answers in
	milliseconds; the old Get-CimInstance PowerShell call timed out on this machine
	and the GPU line never appeared."""
	try:
		user32 = ctypes.WinDLL("user32", use_last_error=True)
		user32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD]
		user32.EnumDisplayDevicesW.restype = wintypes.BOOL
		for index in range(16):
			device = DISPLAY_DEVICEW()
			device.cb = ctypes.sizeof(DISPLAY_DEVICEW)
			if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
				break
			name = device.DeviceString.strip()
			lowered = name.lower()
			if not name or "mirror" in lowered or "remote" in lowered or "basic" in lowered:
				continue
			return name[:30]
	except (OSError, AttributeError) as e:
		log.debug(f"GPU lookup failed: {e}")
	return None


def _count_running_processes():
	"""Number of running processes via psapi EnumProcesses, or None on failure.
	EnumProcesses reports how many bytes it filled but not how many it dropped, so
	the buffer is doubled until the result no longer fills it completely."""
	psapi = ctypes.WinDLL("psapi", use_last_error=True)
	psapi.EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
	psapi.EnumProcesses.restype = wintypes.BOOL
	capacity = 1024
	while capacity <= 65536:
		pids = (wintypes.DWORD * capacity)()
		bytesReturned = wintypes.DWORD(0)
		if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(bytesReturned)):
			return None
		if bytesReturned.value < ctypes.sizeof(pids):
			return bytesReturned.value // ctypes.sizeof(wintypes.DWORD)
		capacity *= 2
	return None


def get_process_count():
	# Previously this called utils.enumerate_running_processes(), which does not
	# exist anywhere in the add-on; the resulting AttributeError was swallowed by a
	# silent "except Exception: pass", so the readout always fell through to "??".
	try:
		count = _count_running_processes()
		if count:
			return str(count)
		log.warning("Process count unavailable: EnumProcesses returned no result")
	except (OSError, AttributeError, ValueError) as e:
		log.warning(f"Process count failed: {e}")
	return _("??")


def get_windows_activation_status():
	try:
		psScript = "Get-CimInstance -ClassName SoftwareLicensingProduct -Filter 'PartialProductKey IS NOT NULL' | Select-Object -ExpandProperty LicenseStatus"
		output = _runPowerShell(psScript, timeout=3)
		if output:
			for line in output.splitlines():
				statusValue = line.strip()
				if statusValue == "1":
					return _("Activated")
				elif statusValue.isdigit():
					return _("Not Activated")
	except Exception:
		pass

	try:
		systemRoot = _getSystemRoot()
		cscriptExe = os.path.join(systemRoot, "System32", "cscript.exe")
		slmgrVbs = os.path.join(systemRoot, "System32", "slmgr.vbs")

		if os.path.exists(cscriptExe) and os.path.exists(slmgrVbs):
			output = _runCommand([cscriptExe, "//nologo", slmgrVbs, "/dli"], timeout=3)
			if output:
				if "License Status: Licensed" in output or "Licensed" in output:
					return _("Activated")
				elif "License Status:" in output:
					return _("Not Activated")
	except Exception:
		pass

	return None


def get_windows_version():
	try:
		ver = winVersion.getWinVer()
		arch = ver.processorArchitecture
		winverName = ver.releaseName
		if ver.productType != "workstation":
			winverName = _("Windows Server {}").format(winverName.rpartition(' ')[-1])
		buildRevision = "{}.{}".format(ver.build, ver.revision)
		return _("{} ({} bit) build {}").format(winverName, arch, buildRevision)
	except Exception:
		pass
	return _("??")


def get_monitor_items_async(callback):
	# The collectors are independent, so they run side by side and the dialog opens
	# when the slowest one finishes (capped by _MONITOR_DEADLINE) instead of after the
	# sum of all of them, which took ~9 seconds when run one after another. A
	# collector that has not answered by the deadline is left out of the list (or
	# shows as unknown) rather than holding the window back.
	def worker():
		try:
			results = {}

			def runCollector(key, func):
				try:
					results[key] = func()
				except Exception as e:
					log.warning("System information collector {} failed: {}".format(key, e))

			collectors = {
				"cpu": get_cpu_usage,
				"ram": get_ram_usage,
				"disk": get_disk_usage,
				"counters": get_performance_counters,
				"network": get_network_status,
				"wifi": get_wifi_details,
				"battery": get_battery_info,
				"gpu": get_gpu_info,
				"activation": get_windows_activation_status,
			}
			threads = []
			for key, func in collectors.items():
				thread = threading.Thread(target=runCollector, args=(key, func), daemon=True)
				thread.start()
				threads.append(thread)
			deadline = time.time() + _MONITOR_DEADLINE
			for thread in threads:
				thread.join(max(0.0, deadline - time.time()))
			snapshot = dict(results)

			items = []
			items.append(("CPU: {}".format(snapshot.get("cpu") or _("??%")), "cpu"))
			items.append(("RAM: {}".format(snapshot.get("ram") or _("??%")), "ram"))

			for disk_item in snapshot.get("disk") or []:
				items.append(("Disk: {}".format(disk_item), "disk"))
			if not snapshot.get("disk"):
				items.append(("Disk: ??", "disk"))

			counters = snapshot.get("counters") or {}
			if counters.get("disk_activity"):
				items.append(("Disk Activity: {}".format(counters["disk_activity"]), "disk_activity"))
			if counters.get("network_speed"):
				items.append(("Network Speed: {}".format(counters["network_speed"]), "network_speed"))
			else:
				networkStatus = _("Connected") if snapshot.get("network") else _("Disconnected")
				items.append(("Network: {}".format(networkStatus), "network"))

			ssid, signal = snapshot.get("wifi") or (None, None)
			if ssid:
				if signal:
					items.append(("Wi-Fi: {} (Signal {})".format(ssid, signal), "wifi"))
				else:
					items.append(("Wi-Fi: {}".format(ssid), "wifi"))

			if snapshot.get("battery"):
				items.append(("Battery: {}".format(snapshot["battery"]), "battery"))

			items.append(("Uptime: {}".format(get_uptime()), "uptime"))
			items.append(("Processes: {}".format(get_process_count()), "processes"))

			if snapshot.get("gpu"):
				items.append(("GPU: {}".format(snapshot["gpu"]), "gpu"))

			items.append(("Windows Activation: {}".format(snapshot.get("activation") or "Unknown"), "activation"))
			items.append(("Windows: {}".format(get_windows_version()), "windows"))

			wx.CallAfter(callback, items)
		except Exception as e:
			log.error("Error collecting monitor data: {}".format(e))
			wx.CallAfter(callback, [("Error collecting data", "error")])

	threading.Thread(target=worker, daemon=True).start()


def get_monitor_items():
	"""Synchronous fallback used when a caller needs an immediate, non-async snapshot."""
	items = []
	items.append(("CPU: {}".format(get_cpu_usage()), "cpu"))
	items.append(("RAM: {}".format(get_ram_usage()), "ram"))
	for disk_item in get_disk_usage():
		items.append(("Disk: {}".format(disk_item), "disk"))
	items.append(("Uptime: {}".format(get_uptime()), "uptime"))
	items.append(("Processes: {}".format(get_process_count()), "processes"))
	items.append(("Windows: {}".format(get_windows_version()), "windows"))
	return items


