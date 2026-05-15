# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import globalPluginHandler
import addonHandler
import wx
import os
import globalVars
import tones
import subprocess
import ctypes
from ctypes import wintypes
from logHandler import log
import ui
from scriptHandler import script
from . import menu
from . import utils
from . import cmd_tools
from . import kill_dialog

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except:
	def _(x): return x

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "Absolute Windows"

	CONFIG_DIR = os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "AbsoluteWindows")
	CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

	def __init__(self):
		super().__init__()
		try:
			os.makedirs(self.CONFIG_DIR, exist_ok=True)
		except Exception as e:
			log.error(f"Could not create config directory: {e}")

		self.internetConnected = self._checkInternetConnected()
		self._lastDisabledAdapter = None

	def terminate(self):
		pass

	def _checkInternetConnected(self):
		return utils.isInternetConnected()

	def _buildMenuItems(self):
		items = []
		if self.internetConnected:
			items.append((_("Disconnect Internet"), self._toggleInternet))
		else:
			items.append((_("Connect Internet"), self._toggleInternet))
		items.append((_("Show Wi-Fi Password"), self._showWifiPassword))
		is_uac_enabled = utils.isUACEnabled()
		if is_uac_enabled:
			items.append((_("Disable User Account Control"), self._toggleUAC))
		else:
			items.append((_("Enable User Account Control"), self._toggleUAC))
		items.append((_("Kill Not Responding Apps"), self._killNotResponding))
		items.append((_("Startup Manager"), self._showStartupManager))
		items.append((_("Restart Windows Explorer"), self._restartExplorer))
		items.append((_("Open Services"), self._openServices))
		items.append((_("Manage Services"), self._manageServices))
		items.append((_("Environment Variables"), self._openEnvironmentVariables))
		items.append((_("Run Cmd"), self._runCmdSubMenu))
		items.append((_("Regedit"), self._openRegedit))
		items.append((_("Windows Defender"), self._openWindowsDefender))
		items.append((_("Microsoft Windows Malicious Software Removal Tool"), self._openMaliciousSoftwareRemovalTool))
		items.append((_("Optimize and defragment drive"), self._optimizeDrive))
		items.append((_("Disk Cleanup"), self._openDiskCleanup))
		items.append((_("Clean Prefetch & Recent"), self._cleanPrefetchRecent))
		items.append((_("Clean System files"), self._cleanSystemFiles))
		items.append((_("Clean Temp"), self._cleanTemp))
		items.append((_("Clean Windows Run History"), self._cleanRunHistory))
		items.append((_("Empty Recycle Bin"), self._emptyRecycleBin))
		items.append((_("Clear Ram"), self._clearRam))
		return items

	def _buildCmdSubMenuItems(self):
		return [
			(_("Run DISM"), self._runDism),
			(_("Run SFC Scannow"), self._runSfcScannow),
			(_("Run Chkdsk on C:"), self._runChkdsk),
			(_("Run Disk Cleanup"), self._runDiskCleanup),
			(_("Power Diagnostic (Battery Report)"), self._runPowerDiagnostic),
			(_("Check Disk Status"), self._runDiskStatus)
		]

	def _runCmdSubMenu(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.showAbsoluteWindowsMenu, self._buildCmdSubMenuItems, self.CONFIG_PATH)

	def _toggleInternet(self, menuInstance):
		if self.internetConnected:
			adapter = utils.get_active_adapter_name()
			if not adapter:
				tones.beep(220, 200)
				ui.message(_("No active network adapter found."))
				return
			success = utils.disable_adapter(adapter)
			if success:
				self._lastDisabledAdapter = adapter
				self.internetConnected = False
				tones.beep(440, 100)
				ui.message(_("Internet disconnected."))
			else:
				tones.beep(220, 200)
				ui.message(_("Failed to disconnect internet."))
		else:
			adapter = self._lastDisabledAdapter
			if not adapter:
				adapter = utils.get_first_disabled_adapter()
			if not adapter:
				tones.beep(220, 200)
				ui.message(_("No disabled network adapter found."))
				return
			success = utils.enable_adapter(adapter)
			if success:
				self.internetConnected = True
				tones.beep(440, 100)
				ui.message(_("Internet connected."))
			else:
				tones.beep(220, 200)
				ui.message(_("Failed to connect internet."))
		menuInstance.refreshList()

	def _toggleUAC(self, menuInstance):
		current_state = utils.isUACEnabled()
		if current_state:
			success = utils.disableUAC()
		else:
			success = utils.enableUAC()
		if success:
			tones.beep(440, 100)
			ui.message(_("User Account Control toggled."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to toggle UAC."))
		menuInstance.refreshList()

	def _showWifiPassword(self, menuInstance):
		ssid, password = utils.get_current_wifi_password()
		if ssid:
			if password:
				utils.copy_to_clipboard(password)
				ui.message(_("Wi-Fi password for {ssid} copied to clipboard.").format(ssid=ssid))
				tones.beep(440, 100)
			else:
				ui.message(_("The Wi-Fi network '{ssid}' is open (no password).").format(ssid=ssid))
				tones.beep(440, 100)
		else:
			ui.message(_("No Wi-Fi network is currently connected."))
			tones.beep(220, 200)

	def _killNotResponding(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(kill_dialog.show_kill_dialog)

	def _restartExplorer(self, menuInstance):
		if utils.restart_explorer():
			tones.beep(440, 100)
			ui.message(_("Windows Explorer has been restarted."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to restart Windows Explorer."))

	def _runSfcScannow(self, menuInstance):
		success, errorMsg = cmd_tools.run_sfc_scannow(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("SFC Scannow report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDism(self, menuInstance):
		success, errorMsg = cmd_tools.run_dism(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("DISM report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runChkdsk(self, menuInstance):
		success, errorMsg = cmd_tools.run_chkdsk(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Chkdsk report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskCleanup(self, menuInstance):
		success, errorMsg = cmd_tools.run_disk_cleanup(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk Cleanup report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runPowerDiagnostic(self, menuInstance):
		success, errorMsg = cmd_tools.run_power_diagnostic(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Battery report will open in your browser."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskStatus(self, menuInstance):
		success, errorMsg = cmd_tools.run_disk_status(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk status report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _cleanSystemFiles(self, menuInstance):
		success = utils.run_disk_cleanup_silent()
		if success:
			tones.beep(440, 100)
			ui.message(_("System cleanup started."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to start system cleanup."))

	def _cleanTemp(self, menuInstance):
		success = utils.cleanTempFolders()
		if success:
			tones.beep(440, 100)
			ui.message(_("Temporary files cleaned."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clean temporary files."))

	def _cleanRunHistory(self, menuInstance):
		success = utils.cleanRunHistory()
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Run history cleared."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clear Run history."))

	def _emptyRecycleBin(self, menuInstance):
		success, msg = utils.empty_recycle_bin()
		if success:
			tones.beep(440, 100)
			ui.message(msg)
		else:
			tones.beep(220, 200)
			ui.message(msg)

	def _clearRam(self, menuInstance):
		freed_bytes = utils.clear_ram_cache()
		if freed_bytes > 0:
			freed_mb = freed_bytes / (1024 * 1024)
			tones.beep(440, 100)
			ui.message(_("Cleared {:.1f} MB of RAM cache.").format(freed_mb))
		elif freed_bytes == 0:
			tones.beep(440, 100)
			ui.message(_("RAM cache cleared."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clear RAM cache."))

	def _showStartupManager(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.StartupManagerDialog, self.CONFIG_DIR)

	def _optimizeDrive(self, menuInstance):
		menuInstance.Close()
		try:
			systemRoot = os.environ.get('SystemRoot', 'C:\\Windows')
			sysnativePath = os.path.join(systemRoot, 'Sysnative', 'dfrgui.exe')
			targetPath = sysnativePath if os.path.exists(sysnativePath) else os.path.join(systemRoot, 'System32', 'dfrgui.exe')
			if not os.path.exists(targetPath):
				raise FileNotFoundError(f"dfrgui.exe not found at {targetPath}")
			ctypes.windll.shell32.ShellExecuteW(None, "open", targetPath, None, None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Optimize Drives: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Optimize Drives."))

	def _manageServices(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.ManageServicesDialog, self.CONFIG_DIR)

	def _openServices(self, menuInstance):
		utils.open_services_mmc()
		menuInstance.Close()

	def _cleanPrefetchRecent(self, menuInstance):
		menuInstance.Close()
		success, msg = utils.clean_prefetch_recent()
		if success:
			tones.beep(440, 100)
			ui.message(_("Prefetch and recent files cleaned."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clean: {}").format(msg))

	def _openEnvironmentVariables(self, menuInstance):
		menuInstance.Close()
		try:
			subprocess.Popen(["rundll32.exe", "sysdm.cpl,EditEnvironmentVariables"])
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Environment Variables: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Environment Variables."))

	def _openMaliciousSoftwareRemovalTool(self, menuInstance):
		menuInstance.Close()
		try:
			systemRoot = os.environ.get('SystemRoot', 'C:\\Windows')
			sysnativePath = os.path.join(systemRoot, 'Sysnative', 'MRT.exe')
			targetPath = sysnativePath if os.path.exists(sysnativePath) else os.path.join(systemRoot, 'System32', 'MRT.exe')
			if not os.path.exists(targetPath):
				raise FileNotFoundError(f"MRT.exe not found at {targetPath}")
			ctypes.windll.shell32.ShellExecuteW(None, "open", targetPath, None, None, 1)
			tones.beep(440, 100)
			wx.CallLater(300, self._bringMrtToFront)
		except Exception as e:
			log.error(f"Failed to open Malicious Software Removal Tool: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Malicious Software Removal Tool."))

	def _bringMrtToFront(self):
		try:
			targetTitle = "Microsoft Windows Malicious Software Removal Tool"
			def enumWindowProc(hwnd, lParam):
				if ctypes.windll.user32.IsWindowVisible(hwnd):
					bufLength = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
					if bufLength > 0:
						buf = ctypes.create_unicode_buffer(bufLength)
						ctypes.windll.user32.GetWindowTextW(hwnd, buf, bufLength)
						if buf.value.startswith(targetTitle):
							setattr(enumWindowProc, "foundHwnd", hwnd)
							return 0
				return 1
			enumWindowProc.foundHwnd = None
			enumFunc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)(enumWindowProc)
			ctypes.windll.user32.EnumWindows(enumFunc, 0)
			if enumWindowProc.foundHwnd:
				ctypes.windll.user32.SetForegroundWindow(enumWindowProc.foundHwnd)
				ctypes.windll.user32.ShowWindow(enumWindowProc.foundHwnd, 1)
		except Exception as e:
			log.debug(f"Failed to bring MRT window to front: {e}")

	def _openDiskCleanup(self, menuInstance):
		menuInstance.Close()
		try:
			subprocess.Popen(["cleanmgr"])
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Disk Cleanup: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Disk Cleanup."))

	def _openRegedit(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "regedit.exe", None, None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Registry Editor: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Registry Editor."))

	def _openWindowsDefender(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "windowsdefender://Threatsettings", None, None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Windows Defender: {e}")
			try:
				systemRoot = os.environ.get('SystemRoot', 'C:\\Windows')
				sysnativePath = os.path.join(systemRoot, 'Sysnative', 'MSASCui.exe')
				defenderPath = sysnativePath if os.path.exists(sysnativePath) else os.path.join(systemRoot, 'System32', 'MSASCui.exe')
				if os.path.exists(defenderPath):
					ctypes.windll.shell32.ShellExecuteW(None, "open", defenderPath, None, None, 1)
					tones.beep(440, 100)
				else:
					raise FileNotFoundError("MSASCui.exe not found")
			except Exception as e2:
				log.error(f"Fallback also failed: {e2}")
				tones.beep(220, 200)
				ui.message(_("Could not open Windows Defender."))

	@script(
		description=_("Show Absolute Windows menu"),
		gesture="kb:alt+windows+w",
		category=scriptCategory
	)
	def script_showAbsoluteWindowsMenu(self, gesture):
		menu.showAbsoluteWindowsMenu(self._buildMenuItems, self.CONFIG_PATH)

	@script(
		description=_("Kill Not Responding Apps"),
		gesture="kb:alt+windows+z",
		category=scriptCategory
	)
	def script_altWindowsZ(self, gesture):
		wx.CallAfter(kill_dialog.show_kill_dialog)