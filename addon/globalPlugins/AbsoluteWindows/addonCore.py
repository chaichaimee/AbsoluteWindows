# addonCore.py

import globalPluginHandler
import addonHandler
import wx
import os
import core
import globalVars
import tones
import subprocess
import ctypes
import threading
import time
from ctypes import wintypes
from logHandler import log
import ui
from scriptHandler import script
from . import menu
from . import utils
from . import cmd_tools
from . import kill_dialog
from . import sys_monitor
from . import audio_device

addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "Absolute Windows"

	CONFIG_DIR = os.path.join(globalVars.appArgs.configPath, "ChaiChaimee", "AbsoluteWindows")
	CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

	# Cache for internet status
	_internetCache = None
	_internetCacheTime = 0
	_internetCacheTTL = 5  # seconds

	def __init__(self):
		super().__init__()
		log.info("AbsoluteWindows add-on initializing...")
		log.info(f"NVDA language: {globalVars.appArgs.language}")

		try:
			os.makedirs(self.CONFIG_DIR, exist_ok=True)
		except Exception as e:
			log.error(f"Could not create config directory: {e}")

		self._lastDisabledAdapter = None
		self._lastTapTime = 0
		self._tapCount = 0
		self._tapThreshold = 0.5
		self._lastTapTimeZ = 0
		self._tapCountZ = 0

	def terminate(self):
		pass

	def _checkInternetConnected(self):
		now = time.time()
		if (self._internetCache is not None and 
			now - self._internetCacheTime < self._internetCacheTTL):
			return self._internetCache
		self._internetCache = utils.isInternetConnected()
		self._internetCacheTime = now
		return self._internetCache

	def _restartSystem(self):
		utils.force_restart_now()

	def _buildMenuItems(self):
		current_internet_state = self._checkInternetConnected()
		items = []

		items.append((_("System Tray"), self._openSystemTray))

		if current_internet_state:
			items.append((_("Disconnect Internet"), self._toggleInternet))
		else:
			items.append((_("Connect Internet"), self._toggleInternet))

		items.append((_("Toggle Bluetooth"), self._toggleBluetooth))
		items.append((_("Show Wi-Fi Password"), self._showWifiPassword))

		items.append((_("Safely Remove USB"), self._showUsbEject))
		items.append((_("Restart Windows Audio Service"), self._restartAudio))
		items.append((_("Quick Switch Audio Device"), self._quickSwitchAudioDevice))

		is_uac_enabled = utils.isUACEnabled()
		if is_uac_enabled:
			items.append((_("Disable User Account Control"), self._toggleUAC))
		else:
			items.append((_("Enable User Account Control"), self._toggleUAC))

		if utils.isSearchWebResultsDisabled():
			items.append((_("Enable Search Web Results"), self._toggleSearchWebResults))
		else:
			items.append((_("Disable Search Web Results"), self._toggleSearchWebResults))

		items.append((_("Restart to BIOS/UEFI Settings"), self._bootToUEFI))

		items.append((_("Kill Not Responding Apps"), self._killNotResponding))
		items.append((_("Restart Windows Explorer"), self._restartExplorer))
		items.append((_("Control Panel"), self._openControlPanel))
		items.append((_("Programs and Features"), self._openProgramsAndFeatures))
		items.append((_("Volume Mixer"), self._openVolumeMixer))
		items.append((_("Sound setting"), self._openSoundSettings))
		items.append((_("Folder Option"), self._openFolderOptions))
		items.append((_("Startup Manager"), self._showStartupManager))
		items.append((_("Open Services"), self._openServices))
		items.append((_("Manage Services"), self._manageServices))
		items.append((_("Environment Variables"), self._openEnvironmentVariables))
		items.append((_("Run Cmd"), self._runCmdSubMenu))
		items.append((_("Maintenance Tools"), self._runMaintenanceToolsSubMenu))
		items.append((_("Regedit"), self._openRegedit))
		items.append((_("Windows Defender"), self._openWindowsDefender))
		items.append((_("Windows Defender Full Scan Low"), self._runDefenderFullScanLow))
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
			(_("DISM Get International Settings"), self._runDismGetIntl),
			(_("Run SFC Scannow"), self._runSfcScannow),
			(_("Run Chkdsk on C:"), self._runChkdsk),
			(_("Run Disk Cleanup"), self._runDiskCleanup),
			(_("Power Diagnostic (Battery Report)"), self._runPowerDiagnostic),
			(_("Check Disk Status"), self._runDiskStatus),
			(_("Backup Open With"), self._showBackupOpenWith),
			(_("Restore Open With"), self._showRestoreOpenWith)
		]

	def _runCmdSubMenu(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.showAbsoluteWindowsMenu, self._buildCmdSubMenuItems, self.CONFIG_PATH)

	def _buildMaintenanceSubMenuItems(self):
		return [
			(_("Update All Packages (winget upgrade)"), self._runWingetUpgradeAll),
			(_("List Installed Packages (winget list)"), self._runWingetList),
			(_("Defragment Windows Search Database"), self._runSearchDatabaseDefrag),
			(_("Run Windows Defender Full Scan"), self._runDefenderFullScan),
			(_("Clear URL Cache"), self._runClearUrlCache)
		]

	def _runMaintenanceToolsSubMenu(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.showAbsoluteWindowsMenu, self._buildMaintenanceSubMenuItems, self.CONFIG_PATH)

	def _runWingetUpgradeAll(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_winget_upgrade_all(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Package upgrade report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runWingetList(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_winget_list(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Installed packages report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runSearchDatabaseDefrag(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_search_database_defrag(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Search database defragmentation started."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDefenderFullScan(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_defender_full_scan(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Defender full scan started."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runClearUrlCache(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_clear_url_cache(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("URL cache clearing started."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _showBackupOpenWith(self, menuInstance):
		# Backup/restore was previously implemented via DISM's
		# Export/Import-DefaultAppAssociations XML mechanism. Per Microsoft's own
		# documentation, that mechanism is designed to seed *new* user profiles at
		# first logon (or an offline WIM image), not to reapply associations to the
		# already-active profile on a live system. On a live system, Import silently
		# reports success while the individually chosen "Open With" program for an
		# existing file type is not actually restored - exactly the symptom
		# reported. cmd_tools now backs up/restores the live per-user association
		# state directly via the FileExts registry key instead. See cmd_tools.py.
		menuInstance.Close()
		ui.message(_("Backing up Open With associations, please wait..."))

		def task():
			success, result = cmd_tools.run_backup_open_with(self.CONFIG_DIR)
			wx.CallAfter(self._onBackupOpenWithFinished, success, result)
		threading.Thread(target=task, daemon=True).start()

	def _onBackupOpenWithFinished(self, success, result):
		if success:
			tones.beep(440, 100)
			ui.message(_("Open With associations backed up successfully. Note: this restores reliably only on this same Windows installation and user account, not after a Windows reinstall."))
		else:
			tones.beep(220, 200)
			ui.message(result)

	def _buildRestoreOpenWithItems(self):
		backups = utils.list_open_with_backups(self.CONFIG_DIR)
		if not backups:
			return [(_("No Open With backups found"), None)]
		return [(folderName, self._makeRestoreOpenWithCallback(regPath)) for folderName, regPath in backups]

	def _showRestoreOpenWith(self, menuInstance):
		menuInstance.Close()
		wx.CallAfter(menu.showAbsoluteWindowsMenu, self._buildRestoreOpenWithItems, self.CONFIG_PATH)

	def _makeRestoreOpenWithCallback(self, regPath):
		def callback(menuInstance):
			menuInstance.Close()
			self._runRestoreOpenWith(regPath)
		return callback

	def _runRestoreOpenWith(self, regPath):
		ui.message(_("Restoring Open With associations, please wait..."))

		def task():
			success, errorMsg = cmd_tools.run_restore_open_with(self.CONFIG_DIR, regPath)
			wx.CallAfter(self._onRestoreOpenWithFinished, success, errorMsg)
		threading.Thread(target=task, daemon=True).start()

	def _onRestoreOpenWithFinished(self, success, errorMsg):
		if success:
			tones.beep(440, 100)
			ui.message(_("Open With associations restored. Restart Windows Explorer or sign out and back in for the change to take effect."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _openSystemTray(self, menuInstance):
		menuInstance.Close()
		utils.open_system_tray()
		def press_space_to_expand():
			user32 = ctypes.windll.user32
			VK_SPACE = 0x20
			KEYEVENTF_KEYUP = 0x0002
			user32.keybd_event(VK_SPACE, 0, 0, 0)
			user32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)
		core.callLater(200, press_space_to_expand)

	def _toggleInternet(self, menuInstance):
		if self._checkInternetConnected():
			adapter = utils.get_active_adapter_name()
			if not adapter:
				tones.beep(220, 200)
				ui.message(_("No active network adapter found."))
				return
			success = utils.disable_adapter(adapter)
			if success:
				self._lastDisabledAdapter = adapter
				self._internetCache = False
				self._internetCacheTime = time.time()
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
				self._internetCache = True
				self._internetCacheTime = time.time()
				tones.beep(440, 100)
				ui.message(_("Internet connected."))
			else:
				tones.beep(220, 200)
				ui.message(_("Failed to connect internet."))
		menuInstance.refreshList()

	def _toggleBluetooth(self, menuInstance):
		menuInstance.Close()
		success, msg = utils.toggle_bluetooth()
		if success:
			tones.beep(440, 100)
		else:
			tones.beep(220, 200)
		ui.message(msg)

	def _restartAudio(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Restarting Audio Services, please wait..."))
		if utils.restart_audio_services():
			tones.beep(440, 100)
			ui.message(_("Windows Audio Services restarted successfully."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to restart Windows Audio Services."))

	def _quickSwitchAudioDevice(self, menuInstance):
		menuInstance.Close()

		def task():
			success, result = audio_device.cycle_default_playback_device()
			wx.CallAfter(self._onAudioSwitchFinished, success, result)
		threading.Thread(target=task, daemon=True).start()

	def _onAudioSwitchFinished(self, success, result):
		if success:
			tones.beep(440, 100)
			ui.message(_("Switched to {device}.").format(device=result))
		else:
			tones.beep(220, 200)
			ui.message(result)

	def _showUsbEject(self, menuInstance):
		menuInstance.Close()
		self._handleUsbEjectRequest()

	def _handleUsbEjectRequest(self):
		"""Shared entry point for both the 'Safely Remove USB' menu item and the
		alt+windows+z double-tap gesture. A single connected removable drive is
		ejected immediately (same feedback as a manual eject: beep + ui.message,
		no dialog); with more than one, the selection dialog is shown instead."""
		drives = utils.get_usb_drives()
		if len(drives) == 1:
			item = drives[0]

			def task():
				success = utils.eject_usb(item['letter'])
				wx.CallAfter(self._onQuickUsbEjectFinished, success, item)
			threading.Thread(target=task, daemon=True).start()
		elif len(drives) > 1:
			wx.CallAfter(menu.UsbEjectDialog, self.CONFIG_DIR)
		else:
			tones.beep(220, 200)
			ui.message(_("No USB drives found."))

	def _onQuickUsbEjectFinished(self, success, item):
		if success:
			tones.beep(440, 100)
			ui.message(_("USB drive {drive} ejected safely.").format(drive=item['letter']))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to eject {drive}.").format(drive=item['letter']))

	def _bootToUEFI(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Restarting to BIOS/UEFI, please wait..."))
		success = utils.boot_to_uefi_firmware()
		if success:
			tones.beep(440, 100)
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to restart to BIOS. Your system may not support this feature via Windows."))

	def _toggleUAC(self, menuInstance):
		# utils.disableUAC()/enableUAC() shell out to reg.exe under an elevated
		# ShellExecuteW "runas" call and then sleep briefly to verify the write,
		# so this must not run on the main thread (Section 5.1) - the previous
		# version did, and also had a malformed reg.exe command line (see
		# utils._setUACRegistry) that made every toggle attempt fail silently
		# and near-instantly regardless of UAC's actual state.
		def task():
			current_state = utils.isUACEnabled()
			if current_state:
				success = utils.disableUAC()
			else:
				success = utils.enableUAC()
			wx.CallAfter(self._onUACToggleFinished, menuInstance, success)
		threading.Thread(target=task, daemon=True).start()

	def _onUACToggleFinished(self, menuInstance, success):
		if success:
			tones.beep(440, 100)
			# Changing EnableLUA only takes effect after a restart - Windows keeps
			# enforcing the old UAC state until then, per Microsoft's own guidance.
			ui.message(_("User Account Control changed. Restart Windows for the change to take effect."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to toggle UAC."))
		menuInstance.refreshList()

	def _toggleSearchWebResults(self, menuInstance):
		success, isDisabled = utils.toggleSearchWebResults()
		if not success:
			tones.beep(220, 200)
			ui.message(_("Failed to toggle search web results."))
			menuInstance.refreshList()
			return
		tones.beep(440, 100)
		if isDisabled:
			ui.message(_("Search web results disabled. Restarting Explorer to apply changes..."))
		else:
			ui.message(_("Search web results enabled. Restarting Explorer to apply changes..."))
		menuInstance.refreshList()

		# restart_explorer() performs blocking subprocess calls (taskkill/start with
		# timeouts), so it must run off the main thread per Section 5.1, not
		# synchronously here like the original engine.py draft did.
		def task():
			utils.restart_explorer()
		threading.Thread(target=task, daemon=True).start()

	def _showWifiPassword(self, menuInstance):
		menuInstance.Close()

		def task():
			ssid, password = utils.get_current_wifi_password()
			wx.CallAfter(self._onWifiPasswordChecked, ssid, password)
		threading.Thread(target=task, daemon=True).start()

	def _onWifiPasswordChecked(self, ssid, password):
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
		menuInstance.Close()
		ui.message(_("Restarting Windows Explorer, please wait..."))

		def task():
			success = utils.restart_explorer()
			wx.CallAfter(self._onRestartExplorerFinished, success)
		threading.Thread(target=task, daemon=True).start()

	def _onRestartExplorerFinished(self, success):
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Explorer has been restarted."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to restart Windows Explorer."))

	def _runSfcScannow(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_sfc_scannow(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("SFC Scannow report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDism(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_dism(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("DISM report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDismGetIntl(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_dism_get_intl(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("DISM international settings report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runChkdsk(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_chkdsk(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Chkdsk report will open when complete. On the system drive this normally only schedules a check for the next restart rather than running it immediately - that is expected."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskCleanup(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_disk_cleanup(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk Cleanup report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runPowerDiagnostic(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_power_diagnostic(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Battery report will open in your browser."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _runDiskStatus(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_disk_status(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Disk status report will open when complete."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _cleanSystemFiles(self, menuInstance):
		menuInstance.Close()
		success = utils.run_disk_cleanup_silent()
		if success:
			tones.beep(440, 100)
			ui.message(_("System cleanup started."))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to start system cleanup."))

	def _cleanTemp(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Cleaning temporary files, please wait..."))

		def task():
			success, deletedCount = utils.cleanTempFolders()
			wx.CallAfter(self._onCleanTempFinished, success, deletedCount)
		threading.Thread(target=task, daemon=True).start()

	def _onCleanTempFinished(self, success, deletedCount):
		if success:
			tones.beep(440, 100)
			ui.message(_("Temporary files cleaned. {count} items removed.").format(count=deletedCount))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clean temporary files."))

	def _cleanRunHistory(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Clearing Windows Run history, please wait..."))

		def task():
			success, deletedCount = utils.cleanRunHistory()
			wx.CallAfter(self._onCleanRunHistoryFinished, success, deletedCount)
		threading.Thread(target=task, daemon=True).start()

	def _onCleanRunHistoryFinished(self, success, deletedCount):
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Run history cleared. {count} items removed.").format(count=deletedCount))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clear Run history."))

	def _emptyRecycleBin(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Emptying Recycle Bin, please wait..."))

		def task():
			success, resultMessage = utils.empty_recycle_bin()
			wx.CallAfter(self._onEmptyRecycleBinFinished, success, resultMessage)
		threading.Thread(target=task, daemon=True).start()

	def _onEmptyRecycleBinFinished(self, success, resultMessage):
		if success:
			tones.beep(440, 100)
		else:
			tones.beep(220, 200)
		ui.message(resultMessage)

	def _clearRam(self, menuInstance):
		menuInstance.Close()
		ui.message(_("Clearing RAM cache, please wait..."))

		def task():
			freedBytes = utils.clear_ram_cache()
			wx.CallAfter(self._onClearRamFinished, freedBytes)
		threading.Thread(target=task, daemon=True).start()

	def _onClearRamFinished(self, freedBytes):
		if freedBytes > 0:
			freedMb = freedBytes / (1024 * 1024)
			tones.beep(440, 100)
			ui.message(_("Cleared {:.1f} MB of RAM cache.").format(freedMb))
		elif freedBytes == 0:
			tones.beep(440, 100)
			ui.message(_("RAM cache is already clean."))
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
		menuInstance.Close()
		try:
			subprocess.Popen("services.msc", shell=True)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open services.msc: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Services."))

	def _cleanPrefetchRecent(self, menuInstance):
		menuInstance.Close()
		success, resultData = utils.clean_prefetch_recent()
		if success:
			tones.beep(440, 100)
			ui.message(_("Prefetch and recent files cleaned. {count} items removed.").format(count=resultData))
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to clean: {errorMsg}").format(errorMsg=resultData))

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
			core.callLater(300, self._bringMrtToFront)
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
			result = ctypes.windll.shell32.ShellExecuteW(None, "open", "cleanmgr.exe", None, None, 1)
			if result > 32:
				tones.beep(440, 100)
			else:
				result2 = ctypes.windll.shell32.ShellExecuteW(None, "open", "cleanmgr.exe", "/sagerun:1", None, 1)
				if result2 > 32:
					tones.beep(440, 100)
				else:
					raise RuntimeError(f"ShellExecuteW failed with code {result2}")
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

	def _openFolderOptions(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "control.exe", "/name Microsoft.FolderOptions", None, 1)
			tones.beep(440, 100)
			core.callLater(200, self._bringFolderOptionsToFront, 15)
		except Exception as e:
			log.error(f"Failed to open Folder Options: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Folder Options."))

	def _bringFolderOptionsToFront(self, retries=15, delayMs=200):
		try:
			user32 = ctypes.windll.user32
			targetTitles = [_("Folder Options"), _("File Explorer Options")]
			foundHwnd = None

			EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
			def enumCallback(hwnd, lParam):
				nonlocal foundHwnd
				if not user32.IsWindowVisible(hwnd):
					return 1

				classBuf = ctypes.create_unicode_buffer(256)
				user32.GetClassNameW(hwnd, classBuf, 256)
				className = classBuf.value

				if className not in ("#32770", "CabinetWClass"):
					return 1

				bufLength = user32.GetWindowTextLengthW(hwnd) + 1
				if bufLength > 1:
					buf = ctypes.create_unicode_buffer(bufLength)
					user32.GetWindowTextW(hwnd, buf, bufLength)
					title = buf.value
					for target in targetTitles:
						if target in title or title in target:
							foundHwnd = hwnd
							return 0
				return 1

			enumFunc = EnumWindowsProc(enumCallback)
			user32.EnumWindows(enumFunc, 0)

			if foundHwnd:
				VK_MENU = 0x12
				KEYEVENTF_EXTENDEDKEY = 0x0001
				KEYEVENTF_KEYUP = 0x0002

				user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)

				foregroundHwnd = user32.GetForegroundWindow()
				foregroundThread = user32.GetWindowThreadProcessId(foregroundHwnd, None)
				targetThread = user32.GetWindowThreadProcessId(foundHwnd, None)

				if foregroundThread and targetThread and foregroundThread != targetThread:
					user32.AttachThreadInput(targetThread, foregroundThread, True)
					user32.SetWindowPos(foundHwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
					user32.SetForegroundWindow(foundHwnd)
					user32.BringWindowToTop(foundHwnd)
					user32.ShowWindow(foundHwnd, 5)
					user32.AttachThreadInput(targetThread, foregroundThread, False)
				else:
					user32.SetWindowPos(foundHwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
					user32.SetForegroundWindow(foundHwnd)
					user32.ShowWindow(foundHwnd, 5)

				user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

				log.debug("Folder Options forced to foreground using Alt hack.")
				core.callLater(1500, self._removeTopmost, foundHwnd)
			else:
				if not foundHwnd and retries > 0:
					log.debug(f"Folder Options not found, retrying... ({retries} left)")
					core.callLater(delayMs, self._bringFolderOptionsToFront, retries-1, delayMs)
				else:
					log.debug("Folder Options window not found after retries.")
		except Exception as e:
			log.debug(f"Failed to bring Folder Options to front: {e}")

	def _removeTopmost(self, hwnd):
		try:
			ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0002 | 0x0001)
			log.debug("Removed TOPMOST from Folder Options.")
		except Exception as e:
			log.debug(f"Failed to remove TOPMOST: {e}")

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

	def _runDefenderFullScanLow(self, menuInstance):
		menuInstance.Close()
		success, errorMsg = cmd_tools.run_defender_full_scan_low(self.CONFIG_DIR)
		if success:
			tones.beep(440, 100)
			ui.message(_("Windows Defender Full Scan started at low priority."))
		else:
			tones.beep(220, 200)
			ui.message(errorMsg)

	def _openControlPanel(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "control.exe", None, None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Control Panel: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Control Panel."))

	def _openProgramsAndFeatures(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "control.exe", "appwiz.cpl", None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Programs and Features: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Programs and Features."))

	def _openVolumeMixer(self, menuInstance):
		menuInstance.Close()
		try:
			# sndvol.exe is the classic per-application Volume Mixer, distinct from
			# mmsys.cpl (the Sound control panel opened below), which only exposes
			# playback/recording device tabs and has no per-app mixer view.
			ctypes.windll.shell32.ShellExecuteW(None, "open", "sndvol.exe", None, None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Volume Mixer: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Volume Mixer."))

	def _openSoundSettings(self, menuInstance):
		menuInstance.Close()
		try:
			ctypes.windll.shell32.ShellExecuteW(None, "open", "control.exe", "mmsys.cpl", None, 1)
			tones.beep(440, 100)
		except Exception as e:
			log.error(f"Failed to open Sound Settings: {e}")
			tones.beep(220, 200)
			ui.message(_("Could not open Sound Settings."))

	def _buildMonitorItems(self):
		return sys_monitor.get_monitor_items()

	def _showSystemMonitor(self):
		menu.showSystemMonitorMenu(self._buildMonitorItems, self.CONFIG_PATH)

	def _handleTapAction(self):
		if self._tapCount == 1:
			menu.showAbsoluteWindowsMenu(self._buildMenuItems, self.CONFIG_PATH)
		elif self._tapCount >= 2:
			tones.beep(880, 150)
			self._showSystemMonitor()
		self._tapCount = 0

	@script(
		description=_("Show Absolute Windows menu (single tap) or System Monitor (double tap)"),
		gesture="kb:alt+windows+w",
		category=scriptCategory
	)
	def script_showAbsoluteWindowsMenu(self, gesture):
		currentTime = time.time()

		if currentTime - self._lastTapTime > self._tapThreshold:
			self._tapCount = 0

		self._tapCount += 1
		self._lastTapTime = currentTime

		wx.CallLater(int(self._tapThreshold * 1000), self._handleTapAction)

	@script(
		description=_("Kill Not Responding Apps (single tap) or Safely Remove USB (double tap)"),
		gesture="kb:alt+windows+z",
		category=scriptCategory
	)
	def script_altWindowsZ(self, gesture):
		currentTime = time.time()

		if currentTime - self._lastTapTimeZ > self._tapThreshold:
			self._tapCountZ = 0

		self._tapCountZ += 1
		self._lastTapTimeZ = currentTime

		wx.CallLater(int(self._tapThreshold * 1000), self._handleTapActionZ)

	def _handleTapActionZ(self):
		if self._tapCountZ == 1:
			wx.CallAfter(kill_dialog.show_kill_dialog)
		elif self._tapCountZ >= 2:
			tones.beep(880, 150)
			self._handleUsbEjectRequest()
		self._tapCountZ = 0


