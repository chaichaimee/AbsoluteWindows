# sys_monitor.py

import subprocess
import os
import threading
from logHandler import log
import addonHandler
import core
import winVersion
import re

addonHandler.initTranslation()

try:
	_ = addonHandler.getTranslation()
except:
	def _(x): return x


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
			encoding='utf-8',
			errors='replace'
		)
		return result.stdout.strip()
	except subprocess.TimeoutExpired:
		return ""
	except Exception:
		return ""


def _runWmic(query, timeout=1):
	systemRoot = _getSystemRoot()
	wmic = os.path.join(systemRoot, 'System32', 'wbem', 'wmic.exe')
	if not os.path.exists(wmic):
		wmic = 'wmic.exe'
	return _runCommand([wmic] + query.split(), timeout)


def _runPowerShell(script, timeout=1):
	systemRoot = _getSystemRoot()
	powershell = os.path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
	if not os.path.exists(powershell):
		powershell = 'powershell.exe'
	return _runCommand([powershell, '-ExecutionPolicy', 'Bypass', '-NoProfile', '-Command', script], timeout)


def get_cpu_usage():
	try:
		output = _runWmic("cpu get loadpercentage")
		lines = output.splitlines()
		for line in lines:
			line = line.strip()
			if line.isdigit():
				return _("{}%").format(int(line))
	except Exception:
		pass
	
	try:
		import psutil
		return _("{}%").format(round(psutil.cpu_percent(interval=0.1), 1))
	except Exception:
		pass
	
	return _("??%")


def get_ram_usage():
	try:
		output = _runWmic("os get FreePhysicalMemory,TotalVisibleMemorySize")
		lines = output.splitlines()
		for line in lines:
			if "FreePhysicalMemory" in line or not line.strip():
				continue
			parts = line.split()
			if len(parts) >= 2:
				try:
					free_kb = int(parts[0])
					total_kb = int(parts[1])
					used_kb = total_kb - free_kb
					percent = (used_kb / total_kb) * 100
					used_gb = used_kb / (1024 * 1024)
					total_gb = total_kb / (1024 * 1024)
					return _("{:.2F} GB of {:.2F} GB used ({:.1F}%)").format(used_gb, total_gb, round(percent, 1))
				except ValueError:
					continue
	except Exception:
		pass
	
	try:
		import psutil
		mem = psutil.virtual_memory()
		used_gb = mem.used / (1024**3)
		total_gb = mem.total / (1024**3)
		percent = mem.percent
		return _("{:.2F} GB of {:.2F} GB used ({:.1F}%)").format(used_gb, total_gb, round(percent, 1))
	except Exception:
		pass
	
	return _("??%")


def get_disk_usage():
	disk_info = []
	
	try:
		output = _runWmic("logicaldisk where DriveType=3 get DeviceId,FreeSpace,Size")
		lines = output.splitlines()
		for line in lines:
			if "DeviceId" in line or not line.strip():
				continue
			parts = line.split()
			if len(parts) >= 3:
				try:
					drive = parts[0]
					free = int(parts[1])
					total = int(parts[2])
					used_gb = (total - free) / (1024**3)
					total_gb = total / (1024**3)
					percent = ((total - free) / total) * 100
					disk_info.append(_("{} {:.1F} GB of {:.1F} GB used ({:.0F}%)").format(drive, used_gb, total_gb, percent))
				except ValueError:
					continue
	except Exception:
		pass
	
	if not disk_info:
		try:
			import psutil
			for partition in psutil.disk_partitions():
				if partition.fstype:
					try:
						usage = psutil.disk_usage(partition.mountpoint)
						used_gb = usage.used / (1024**3)
						total_gb = usage.total / (1024**3)
						percent = usage.percent
						disk_info.append(_("{} {:.1F} GB of {:.1F} GB used ({:.0F}%)").format(
							partition.device[:2], used_gb, total_gb, percent))
					except Exception:
						pass
		except Exception:
			pass
	
	return disk_info


def get_disk_activity():
	try:
		import psutil
		disk_io = psutil.disk_io_counters()
		if disk_io:
			read_speed = disk_io.read_bytes / (1024 * 1024)
			write_speed = disk_io.write_bytes / (1024 * 1024)
			return _("{:.1F} MB/s read, {:.1F} MB/s write").format(read_speed, write_speed)
	except Exception:
		pass
	
	try:
		script = "Get-Counter '\\PhysicalDisk(_Total)\\Disk Read Bytes/sec' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue"
		read_bytes = _runPowerShell(script)
		script2 = "Get-Counter '\\PhysicalDisk(_Total)\\Disk Write Bytes/sec' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue"
		write_bytes = _runPowerShell(script2)
		if read_bytes and write_bytes:
			read_mb = float(read_bytes) / (1024 * 1024)
			write_mb = float(write_bytes) / (1024 * 1024)
			return _("{:.1F} MB/s read, {:.1F} MB/s write").format(read_mb, write_mb)
	except Exception:
		pass
	
	return None


def get_network_speed():
	try:
		import psutil
		net_io = psutil.net_io_counters()
		if net_io:
			down_mb = net_io.bytes_recv / (1024 * 1024)
			up_mb = net_io.bytes_sent / (1024 * 1024)
			if down_mb > 0 or up_mb > 0:
				return _("{:.1F} MB/s down, {:.1F} MB/s up").format(down_mb, up_mb)
	except Exception:
		pass
	
	try:
		script = "Get-Counter '\\Network Interface(*)\\Bytes Received/sec' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples | ForEach-Object { $_.CookedValue } | Measure-Object -Sum | Select-Object -ExpandProperty Sum"
		received = _runPowerShell(script)
		script2 = "Get-Counter '\\Network Interface(*)\\Bytes Sent/sec' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CounterSamples | ForEach-Object { $_.CookedValue } | Measure-Object -Sum | Select-Object -ExpandProperty Sum"
		sent = _runPowerShell(script2)
		if received and sent:
			down_mb = float(received) / (1024 * 1024)
			up_mb = float(sent) / (1024 * 1024)
			if down_mb > 0 or up_mb > 0:
				return _("{:.1F} MB/s down, {:.1F} MB/s up").format(down_mb, up_mb)
	except Exception:
		pass
	
	return None


def get_network_status():
	try:
		output = _runCommand(["ping", "-n", "1", "8.8.8.8"], 2)
		if "time=" in output.lower() or "ttl=" in output.lower():
			return _("Connected")
	except Exception:
		pass
	return _("Disconnected")


def get_battery_info():
	try:
		output = _runWmic("path Win32_Battery get EstimatedChargeRemaining,BatteryStatus")
		lines = output.splitlines()
		for line in lines:
			if "EstimatedChargeRemaining" in line or not line.strip():
				continue
			parts = line.split()
			if len(parts) >= 2:
				try:
					percent = int(parts[0])
					status = int(parts[1])
					status_text = {
						1: _("Charging"),
						2: _("Charging"),
						3: _("Fully Charged"),
						4: _("Discharging"),
						5: _("Low")
					}.get(status, _("Unknown"))
					return _("{}% ({})").format(percent, status_text)
				except ValueError:
					continue
	except Exception:
		pass
	return None


def get_uptime():
	try:
		output = _runWmic("os get lastbootuptime")
		lines = output.splitlines()
		for line in lines:
			if "LastBootUpTime" in line or not line.strip():
				continue
			if line.strip():
				try:
					from datetime import datetime
					dt_str = line.strip().split('.')[0]
					dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
					now = datetime.now()
					delta = now - dt
					
					days = delta.days
					hours, rem = divmod(delta.seconds, 3600)
					minutes, seconds = divmod(rem, 60)
					
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
					pass
	except Exception:
		pass
	
	try:
		import psutil
		boot_time = psutil.boot_time()
		from datetime import datetime
		delta = datetime.now() - datetime.fromtimestamp(boot_time)
		
		days = delta.days
		hours, rem = divmod(delta.seconds, 3600)
		minutes, seconds = divmod(rem, 60)
		
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
		pass
	
	return _("??")


def get_wifi_info():
	try:
		output = _runCommand(["netsh", "wlan", "show", "interfaces"], 1)
		for line in output.splitlines():
			if "SSID" in line and "BSSID" not in line:
				parts = line.split(":")
				if len(parts) >= 2:
					ssid = parts[1].strip()
					if ssid:
						return ssid
	except Exception:
		pass
	return None


def get_wifi_signal():
	try:
		output = _runCommand(["netsh", "wlan", "show", "interfaces"], 1)
		for line in output.splitlines():
			if "Signal" in line:
				parts = line.split(":")
				if len(parts) >= 2:
					signal = parts[1].strip()
					if signal.endswith("%"):
						value = int(signal[:-1])
						if value >= 80:
							return _("Excellent")
						elif value >= 60:
							return _("Good")
						elif value >= 40:
							return _("Fair")
						elif value >= 20:
							return _("Weak")
						else:
							return _("Very Weak")
					return signal
	except Exception:
		pass
	return None


def get_gpu_info():
	try:
		script = "Get-WmiObject -Class Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '*Mirror*' -and $_.Name -notlike '*Remote*' -and $_.Name -notlike '*Basic*' } | Select-Object -First 1 -ExpandProperty Name"
		gpu_name = _runPowerShell(script)
		if not gpu_name:
			return None
		gpu_name = gpu_name[:30]
		return gpu_name
	except Exception:
		pass
	return None


def get_process_count():
	try:
		output = _runWmic("process list brief")
		count = 0
		for line in output.splitlines():
			if line.strip() and "HandleCount" not in line:
				count += 1
		if count > 0:
			return _("{} process{}").format(count, "es" if count > 1 else "")
	except Exception:
		pass
	
	try:
		import psutil
		count = len(psutil.pids())
		return _("{} process{}").format(count, "es" if count > 1 else "")
	except Exception:
		pass
	
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
	def worker():
		try:
			items = []
			
			cpu = get_cpu_usage()
			items.append(("CPU: {}".format(cpu), "cpu"))
			
			ram = get_ram_usage()
			items.append(("RAM: {}".format(ram), "ram"))
			
			disk_list = get_disk_usage()
			if disk_list:
				for disk_item in disk_list:
					items.append(("Disk: {}".format(disk_item), "disk"))
			else:
				items.append(("Disk: ??", "disk"))
			
			disk_activity = get_disk_activity()
			if disk_activity:
				items.append(("Disk Activity: {}".format(disk_activity), "disk_activity"))
			
			network_speed = get_network_speed()
			if network_speed:
				items.append(("Network Speed: {}".format(network_speed), "network_speed"))
			else:
				network_status = get_network_status()
				items.append(("Network: {}".format(network_status), "network"))
			
			wifi = get_wifi_info()
			if wifi:
				signal = get_wifi_signal()
				if signal:
					items.append(("Wi-Fi: {} (Signal {})".format(wifi, signal), "wifi"))
				else:
					items.append(("Wi-Fi: {}".format(wifi), "wifi"))
			
			battery = get_battery_info()
			if battery:
				items.append(("Battery: {}".format(battery), "battery"))
			
			uptime = get_uptime()
			items.append(("Uptime: {}".format(uptime), "uptime"))
			
			processes = get_process_count()
			items.append(("Processes: {}".format(processes), "processes"))
			
			gpu = get_gpu_info()
			if gpu:
				items.append(("GPU: {}".format(gpu), "gpu"))
			
			activation = get_windows_activation_status()
			if activation:
				items.append(("Windows Activation: {}".format(activation), "activation"))
			else:
				items.append(("Windows Activation: Unknown", "activation"))
			
			windows = get_windows_version()
			items.append(("Windows: {}".format(windows), "windows"))
			
			core.callLater(0, callback, items)
		except Exception as e:
			log.error("Error collecting monitor data: {}".format(e))
			core.callLater(0, callback, [("Error collecting data", "error")])
	
	threading.Thread(target=worker, daemon=True).start()