# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import globalPluginHandler
import addonHandler
import wx
import os
import globalVars
import tones
from logHandler import log
import ui
from . import menu
from . import utils
from . import cmd_tools

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except:
	def _(x): return x

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "AbsoluteWindows"
	CONFIG_DIR = os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "AbsoluteWindows")
	CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

	def __init__(self):
		super().__init__()
		try:
			os.makedirs(self.CONFIG_DIR, exist_ok=True)
		except Exception as e:
			log.error(f"Could not create config directory: {e}")

		self.internetConnected = self._checkInternetConnected()
		self.uacEnabled = self._checkUACEnabled()
		self._lastDisabledAdapter = None

	def _checkInternetConnected(self):
		return utils.isInternetConnected()

	def _checkUACEnabled(self):
		return utils.isUACEnabled()

	def _buildMenuItems(self):
		items = []
		if self.internetConnected:
			items.append((_("Disconnect Internet"), self._toggleInternet))
		else:
			items.append((_("Connect Internet"), self._toggleInternet))
		items.append((_("Show Wi-Fi Password"), self._showWifiPassword))
		items.append((_("System Tray"), self._openSystemTray))
		if self.uacEnabled:
			items.append((_("Disable User Account Control"), self._toggleUAC))
		else:
			items.append((_("Enable User Account Control"), self._toggleUAC))
		items.append((_("Kill Not Responding Apps"), self._killNotResponding))
		items.append((_("Startup Manager"), self._showStartupManager))
		items.append((_("Restart Windows Explorer"), self._restartExplorer))
		items.append((_("Open Services"), self._openServices))
		items.append((_("Manage Services"), self._manageServices))
		items.append((_("Run Cmd"), self._runCmdSubMenu))
		items.append((_("Drive Optimize"), self._optimizeDrive))
		items.append((_("Clean Prefetch & Recent"), self._cleanPrefetchRecent))
		items.append((_("Clean System files"), self._cleanSystemFiles))
		items.append((_("Clean Temp"), self._cleanTemp))
		items.append((_("Clean Windows Run History"), self._cleanRunHistory))
		items.append((_("Empty Recycle Bin"), self._emptyRecycleBin))
		items.append((_("Clear Ram"), self._clearRam))

		return items

	def _buildCmdSubMenuItems(self):
		log.info("_buildCmdSubMenuItems called")
		return [
			(_("Run DISM"), self._runDism),
			(_("Run SFC Scannow"), self._runSfcScannow),
			(_("Run Chkdsk on C:"), self._runChkdsk),
			(_("Run Disk Cleanup"), self._runDiskCleanup),
			(_("Power Diagnostic (Battery Report)"), self._runPowerDiagnostic),
			(_("Check Disk Status"), self._runDiskStatus)
		]

	def _runCmdSubMenu(self, menuInstance):
		log.info("_runCmdSubMenu called")
		menuInstance.Close()
		wx.CallAfter(menu.showAbsoluteWindowsMenu, self._buildCmdSubMenuItems, self.CONFIG_PATH)

	def _toggleInternet(self, menuInstance):
		if self.internetConnected:
			adapter = utils.get_active_adapter_name()
			if not adapter:
				log.error("No active adapter found to disconnect")
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
				log.error("No disabled adapter found to enable")
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
		success = utils.disableUAC() if self.uacEnabled else utils.enableUAC()
		if success:
			self.uacEnabled = not self.uacEnabled
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
		count = utils.kill_not_responding_apps()
		if count > 0:
			ui.message(_("Terminated {count} not responding application(s).").format(count=count))
			tones.beep(440, 100)
		else:
			ui.message(_("No not responding applications found."))
			tones.beep(440, 100)

	def _restartExplorer(self, menuInstance):
		if utils.restart_explorer():
			tones.beep(440, 100)
			ui.message(_("Windows Explorer has been restarted."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to restart Windows Explorer."))

	def _runSfcScannow(self, menuInstance):
		log.info("_runSfcScannow called")
		success, errorMsg = cmd_tools.run_sfc_scannow(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("SFC Scannow report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDism(self, menuInstance):
		log.info("_runDism called")
		success, errorMsg = cmd_tools.run_dism(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("DISM report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runChkdsk(self, menuInstance):
		log.info("_runChkdsk called")
		success, errorMsg = cmd_tools.run_chkdsk(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Chkdsk report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskCleanup(self, menuInstance):
		log.info("_runDiskCleanup called")
		success, errorMsg = cmd_tools.run_disk_cleanup(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk Cleanup report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runPowerDiagnostic(self, menuInstance):
		log.info("_runPowerDiagnostic called")
		success, errorMsg = cmd_tools.run_power_diagnostic(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Battery report will open in your browser."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskStatus(self, menuInstance):
		log.info("_runDiskStatus called")
		success, errorMsg = cmd_tools.run_disk_status(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk status report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _cleanSystemFiles(self, menuInstance):
		log.info("_cleanSystemFiles called")
		success = utils.run_disk_cleanup_silent()
		if success:
			tones.beep(440, 100)
			ui.message(_("System cleanup started. Window may open briefly."))
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
		success = utils.empty_recycle_bin()
		if success:
			tones.beep(440, 100)
			ui.message(_("Recycle bin emptied."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to empty recycle bin."))

	def _clearRam(self, menuInstance):
		log.info("_clearRam called")
		freed_bytes = utils.clear_ram_cache()
		if freed_bytes > 0:
			freed_mb = freed_bytes / (1024 * 1024)
			tones.beep(440, 100)
			ui.message(_("Cleared {:.1f} MB of RAM cache.").format(freed_mb))
		elif freed_bytes == 0:
			tones.beep(440, 100)
			ui.message(_("RAM cache cleared or no significant cache found."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clear RAM cache."))

	def _openSystemTray(self, menuInstance):
		utils.open_system_tray()
		menuInstance.Close()

	def _showStartupManager(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.StartupManagerDialog, self.CONFIG_DIR)

	def _optimizeDrive(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.DriveOptimizeDialog, self.CONFIG_DIR)

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

	def script_showAbsoluteWindowsMenu(self, gesture):
		menu.showAbsoluteWindowsMenu(self._buildMenuItems, self.CONFIG_PATH)

	__gestures = {
		"kb:alt+windows+w": "showAbsoluteWindowsMenu"
	}