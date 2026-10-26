# menu.py

import wx
import gui
import addonHandler
import tones
import os
import ctypes
import threading
from logHandler import log
import ui
from . import utils
from . import sys_monitor

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except Exception:
	def _(x): return x


def _flattenEntries(items):
	"""Filter out separator placeholders, keeping only real (label, callback) entries
	in their original order, since a list-based feature dialog has no visual concept
	of a separator line."""
	entries = []
	for entry in items:
		if entry is None:
			continue
		label, callback = entry
		if label is None:
			continue
		entries.append((label, callback))
	return entries


def _forceWindowForeground(hwnd):
	"""Force the given window handle to the foreground, above other windows such as
	File Explorer. NVDA's process is not always granted foreground rights by Windows
	on the first popup after startup (focus-stealing prevention), so a plain
	Raise()/SetFocus() can leave a freshly created dialog opened but hidden behind
	whichever window currently owns the foreground.

	Note: this deliberately does NOT use the Alt-keypress envelope technique used
	elsewhere in this add-on for bringing an *external* window (e.g. Folder Options)
	to the front. That trick simulates an actual Alt key press, which is safe for a
	foreign window that does not yet have our keyboard focus, but on one of our own
	freshly created dialogs it gets interpreted as a real Alt keystroke and switches
	keyboard focus into the dialog's title-bar system menu (Restore/Move/Close)
	instead of the intended control. AttachThreadInput bridging alone is sufficient
	and has no such side effect here."""
	try:
		user32 = ctypes.windll.user32
		if not hwnd:
			return

		foregroundHwnd = user32.GetForegroundWindow()
		foregroundThread = user32.GetWindowThreadProcessId(foregroundHwnd, None)
		targetThread = user32.GetWindowThreadProcessId(hwnd, None)

		if foregroundThread and targetThread and foregroundThread != targetThread:
			user32.AttachThreadInput(targetThread, foregroundThread, True)
			user32.SetForegroundWindow(hwnd)
			user32.BringWindowToTop(hwnd)
			user32.AttachThreadInput(targetThread, foregroundThread, False)
		else:
			user32.SetForegroundWindow(hwnd)
			user32.BringWindowToTop(hwnd)
	except Exception as e:
		log.debug(f"Failed to force window to foreground: {e}")


class FeatureListDialog(wx.Dialog):
	"""Accessible, keyboard-driven replacement for the native OS popup menu.

	Using a standard wx.ListBox instead of wx.Menu/TrackPopupMenu means:
	- Arrow-key navigation clamps at the first/last item instead of wrapping.
	- Home/End and native single-letter type-ahead search work automatically.
	- NVDA announces the first item directly on open instead of a generic
	  "Context menu" announcement, since focus lands on a real list item.
	"""

	def __init__(self, title, items, parentDialog=None, itemsFunc=None):
		super().__init__(gui.mainFrame, title=title, size=(500, 300),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.parentDialog = parentDialog
		self.itemsFunc = itemsFunc
		self.entries = _flattenEntries(items)

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.listBox = wx.ListBox(panel, choices=[label for label, _callback in self.entries], style=wx.LB_SINGLE)
		sizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 5)
		panel.SetSizer(sizer)

		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, self._onActivate)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onClose)

		if self.entries:
			self.listBox.SetSelection(0)

		self.Centre()
		self.Show()
		self.Raise()
		self._forceForeground()
		self.listBox.SetFocus()

	def _forceForeground(self):
		_forceWindowForeground(self.GetHandle())

	def _onCharHook(self, event):
		# Bound on the dialog (not the listBox) via EVT_CHAR_HOOK, which fires before
		# Windows' native dialog keyboard navigation (IsDialogMessage). Binding Enter
		# handling on the listBox's own EVT_KEY_DOWN instead let Windows silently
		# swallow the Return key as a "default button" dialog navigation keystroke
		# before our handler ever saw it, so activating any item did nothing at all.
		keyCode = event.GetKeyCode()
		if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._onActivate(event)
			return
		if keyCode == wx.WXK_ESCAPE:
			wx.CallAfter(self._goBackOrClose)
			return
		event.Skip()

	def _onActivate(self, event):
		selectionIndex = self.listBox.GetSelection()
		if selectionIndex == wx.NOT_FOUND:
			return
		label, callback = self.entries[selectionIndex]
		if isinstance(callback, list):
			wx.CallAfter(self._openSubMenu, label, callback)
			return
		if callback is None:
			# Informational, non-actionable item (e.g. System Monitor readouts).
			return
		# Defer to the next event loop iteration instead of calling the callback
		# synchronously inside the listBox's own key event handler. The callback
		# decides for itself whether to call menuInstance.Close() (dismiss the
		# menu) or menuInstance.refreshList() (stay open, e.g. after a toggle);
		# running that inside the currently-dispatching key event's call stack
		# risks wx silently dropping the rest of the handler when Close() destroys
		# the very listBox that is dispatching the event.
		wx.CallAfter(callback, self)

	def _openSubMenu(self, label, items):
		self.Hide()
		FeatureListDialog(label, items, parentDialog=self)

	def refreshList(self):
		"""Re-fetch items (via the itemsFunc supplied at construction) and repopulate
		the list in place, preserving the current selection where possible. Used by
		toggle-style items (e.g. Connect/Disconnect Internet) that update a label
		without dismissing the menu."""
		if self.itemsFunc is None:
			return
		previousSelection = self.listBox.GetSelection()
		items = self.itemsFunc()
		self.entries = _flattenEntries(items)
		self.listBox.Set([label for label, _callback in self.entries])
		if self.entries:
			newSelection = previousSelection if 0 <= previousSelection < len(self.entries) else 0
			self.listBox.SetSelection(newSelection)
		self.listBox.SetFocus()

	def Close(self, force=False):
		self._closeAll()

	def _goBackOrClose(self):
		if self.parentDialog is not None:
			self.Destroy()
			self.parentDialog.Show()
			self.parentDialog.Raise()
			self.parentDialog._forceForeground()
			self.parentDialog.listBox.SetFocus()
			return
		self.Destroy()

	def _closeAll(self):
		dialog = self
		while dialog is not None:
			nextDialog = dialog.parentDialog
			dialog.Destroy()
			dialog = nextDialog

	def _onClose(self, event):
		self._goBackOrClose()


def showAbsoluteWindowsMenu(itemsFunc, configPath):
	items = itemsFunc()
	FeatureListDialog(_("AbsoluteWindows"), items, itemsFunc=itemsFunc)


def showSystemMonitorMenu(itemsFunc, configPath):
	ui.message(_("Loading system information..."))

	def onDataReceived(items):
		if not items:
			ui.message(_("No data available"))
			return
		displayItems = [(label, None) for label, _tag in items]
		FeatureListDialog(_("System Information"), displayItems)

	sys_monitor.get_monitor_items_async(onDataReceived)


class UsbEjectDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(gui.mainFrame, title=_("Safely Remove USB"), size=(500, 300),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.usbItems = []

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.listCtrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.listCtrl.AppendColumn(_("Drive"), width=100)
		self.listCtrl.AppendColumn(_("Label"), width=350)
		sizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)
		panel.SetSizer(sizer)

		self.listCtrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onEject)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		self.Bind(wx.EVT_CLOSE, self.onClose)

		self.loadUsbDrives()

		self.Centre()
		self.Show()
		self.Raise()
		_forceWindowForeground(self.GetHandle())
		self.listCtrl.SetFocus()

	def loadUsbDrives(self):
		self.usbItems = utils.get_usb_drives()
		self.listCtrl.DeleteAllItems()
		for idx, item in enumerate(self.usbItems):
			self.listCtrl.InsertItem(idx, item['letter'])
			self.listCtrl.SetItem(idx, 1, item['name'])
		if self.usbItems:
			self.listCtrl.Select(0)
			self.listCtrl.Focus(0)

	def onEject(self, event):
		idx = self.listCtrl.GetFirstSelected()
		if idx == -1 or not self.usbItems:
			return
		item = self.usbItems[idx]

		# Deferred via wx.CallAfter for the same reason as FeatureListDialog: the
		# eject runs on a background thread and its completion handler may reload
		# the list or destroy this dialog, which should not happen synchronously
		# inside the currently-dispatching activation event.
		def task():
			success = utils.eject_usb(item['letter'])
			wx.CallAfter(self._onEjectFinished, success, item)
		threading.Thread(target=task, daemon=True).start()

	def _onEjectFinished(self, success, item):
		if success:
			tones.beep(440, 100)
			ui.message(_("USB drive {drive} ejected safely.").format(drive=item['letter']))
			self.loadUsbDrives()
			if not self.usbItems:
				self.Destroy()
				return
			self.listCtrl.SetFocus()
		else:
			tones.beep(220, 200)
			ui.message(_("Failed to eject {drive}.").format(drive=item['letter']))

	def onClose(self, event):
		self.Destroy()

	def onCharHook(self, event):
		keyCode = event.GetKeyCode()
		if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			wx.CallAfter(self.onEject, event)
			return
		if keyCode == wx.WXK_ESCAPE:
			wx.CallAfter(self.onClose, event)
			return
		event.Skip()


class StartupManagerDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(None, title=_("Startup Manager"), size=(600, 400),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.configDir = configDir
		self.startupItems = []
		self.backupDir = os.path.join(configDir, "StartupBackup")
		os.makedirs(self.backupDir, exist_ok=True)

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.listCtrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.listCtrl.AppendColumn(_("Name"), width=200)
		self.listCtrl.AppendColumn(_("Type"), width=100)
		self.listCtrl.AppendColumn(_("Status"), width=100)
		self.listCtrl.AppendColumn(_("Location"), width=200)
		sizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.enableBtn = wx.Button(panel, label=_("Enable Selected"))
		self.disableBtn = wx.Button(panel, label=_("Disable Selected"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		btnSizer.Add(self.enableBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.disableBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.Bind(wx.EVT_BUTTON, self.onEnable, self.enableBtn)
		self.Bind(wx.EVT_BUTTON, self.onDisable, self.disableBtn)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

		self.loadItems()

		self.Centre()
		self.Show()

	def loadItems(self):
		self.startupItems = utils.get_startup_items()
		self.listCtrl.DeleteAllItems()
		for idx, item in enumerate(self.startupItems):
			self.listCtrl.InsertItem(idx, item['name'])
			self.listCtrl.SetItem(idx, 1, item['type'])
			self.listCtrl.SetItem(idx, 2, item['status'])
			self.listCtrl.SetItem(idx, 3, item['location'])

	def getSelectedIndex(self):
		return self.listCtrl.GetFirstSelected()

	def onEnable(self, event):
		idx = self.getSelectedIndex()
		if idx == -1:
			wx.MessageBox(_("No item selected."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		item = self.startupItems[idx]
		if item['status'] == _("Enabled"):
			wx.MessageBox(_("Item already enabled."), _("Info"), wx.OK | wx.ICON_INFORMATION)
			return
		success = utils.enable_startup_item(item, self.backupDir)
		if success:
			self.loadItems()
		else:
			wx.MessageBox(_("Failed to enable item."), _("Error"), wx.OK | wx.ICON_ERROR)

	def onDisable(self, event):
		idx = self.getSelectedIndex()
		if idx == -1:
			wx.MessageBox(_("No item selected."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		item = self.startupItems[idx]
		if item['status'] == _("Disabled"):
			wx.MessageBox(_("Item already disabled."), _("Info"), wx.OK | wx.ICON_INFORMATION)
			return
		success = utils.disable_startup_item(item, self.backupDir)
		if success:
			self.loadItems()
		else:
			wx.MessageBox(_("Failed to disable item."), _("Error"), wx.OK | wx.ICON_ERROR)

	def onClose(self, event):
		self.Destroy()

	def onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			wx.CallAfter(self.onClose, event)
			return
		event.Skip()


class DriveOptimizeDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(None, title=_("Drive Optimize"), size=(500, 300),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.configDir = configDir

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.driveList = wx.ListBox(panel, style=wx.LB_SINGLE)
		sizer.Add(self.driveList, 1, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.optimizeBtn = wx.Button(panel, label=_("Optimize Selected"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		btnSizer.Add(self.optimizeBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.Bind(wx.EVT_BUTTON, self.onOptimize, self.optimizeBtn)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

		self.loadDrives()

		self.Centre()
		self.Show()

	def loadDrives(self):
		drives = utils.get_available_drives()
		for d in drives:
			self.driveList.Append(d)

	def onOptimize(self, event):
		sel = self.driveList.GetSelection()
		if sel == wx.NOT_FOUND:
			wx.MessageBox(_("Select a drive first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		drive = self.driveList.GetString(sel)

		def task():
			success, msg = utils.optimize_drive(drive)
			wx.CallAfter(self.onOptimizeFinished, success, msg)
		threading.Thread(target=task, daemon=True).start()
		self.optimizeBtn.Disable()
		ui.message(_("Optimizing drive, please wait..."))

	def onOptimizeFinished(self, success, msg):
		self.optimizeBtn.Enable()
		if success:
			wx.MessageBox(_("Optimization completed."), _("Success"), wx.OK | wx.ICON_INFORMATION)
		else:
			wx.MessageBox(_("Optimization failed: {}").format(msg), _("Error"), wx.OK | wx.ICON_ERROR)

	def onClose(self, event):
		self.Destroy()

	def onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			wx.CallAfter(self.onClose, event)
			return
		event.Skip()


class ManageServicesDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(None, title=_("Manage Services"), size=(950, 540),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.configDir = configDir
		self.services = []
		self._busy = False
		self._actionsMenu = None

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Multi-select on purpose: Disable Selected / Enable Selected act on every
		# highlighted row, not only the first one.
		self.listCtrl = wx.ListCtrl(panel, style=wx.LC_REPORT)
		# Kept short on purpose: NVDA reads every column of the highlighted row, so the
		# long description and caution note live in the details view (Enter on a row,
		# or "Show service details" in the right-click menu) instead of the list.
		# The first column is the display name, which NVDA reads without a header.
		self.listCtrl.AppendColumn(_("Display Name"), width=380)
		self.listCtrl.AppendColumn(_("Startup Type"), width=170)
		self.listCtrl.AppendColumn(_("Status"), width=90)
		self.listCtrl.AppendColumn(_("Safety"), width=90)
		sizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.disableBtn = wx.Button(panel, label=_("Disable Selected"))
		self.enableBtn = wx.Button(panel, label=_("Enable Selected"))
		self.disableAllBtn = wx.Button(panel, label=_("Disable all"))
		self.enableAllBtn = wx.Button(panel, label=_("Enable all"))
		self.refreshBtn = wx.Button(panel, label=_("Refresh"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		self._buttons = [self.disableBtn, self.enableBtn, self.disableAllBtn, self.enableAllBtn, self.refreshBtn]
		for button in self._buttons + [self.closeBtn]:
			btnSizer.Add(button, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.Bind(wx.EVT_BUTTON, self.onDisableSelected, self.disableBtn)
		self.Bind(wx.EVT_BUTTON, self.onEnableSelected, self.enableBtn)
		self.Bind(wx.EVT_BUTTON, self.onDisableAll, self.disableAllBtn)
		self.Bind(wx.EVT_BUTTON, self.onEnableAll, self.enableAllBtn)
		self.Bind(wx.EVT_BUTTON, self.onRefresh, self.refreshBtn)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		self.listCtrl.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
		self.listCtrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.onShowDescription)

		self.Centre()
		self.Show()
		self.Raise()
		_forceWindowForeground(self.GetHandle())
		self.listCtrl.SetFocus()
		self.loadServices()

	# ---- loading -------------------------------------------------------
	def loadServices(self):
		# Querying every service spawns several sc.exe processes, so it runs on a
		# background thread; doing it in the constructor (as the old version did)
		# froze NVDA's main thread while the dialog was opening.
		self._setBusy(True)
		ui.message(_("Loading services, please wait..."))

		def task():
			services = utils.get_service_states()
			wx.CallAfter(self._onServicesLoaded, services)
		threading.Thread(target=task, daemon=True).start()

	def _onServicesLoaded(self, services):
		if not self:
			return
		self.services = services
		self.listCtrl.DeleteAllItems()
		for idx, svc in enumerate(services):
			safetyLabel = _("Safe") if svc['safety'] == "safe" else _("Caution")
			self.listCtrl.InsertItem(idx, svc['display_name'])
			self.listCtrl.SetItem(idx, 1, svc['start_type'])
			self.listCtrl.SetItem(idx, 2, svc['status'])
			self.listCtrl.SetItem(idx, 3, safetyLabel)
		if services:
			self.listCtrl.Select(0)
			self.listCtrl.Focus(0)
		self._setBusy(False)
		self.listCtrl.SetFocus()
		ui.message(_("{count} services listed.").format(count=len(services)))

	def _setBusy(self, busy):
		self._busy = busy
		for button in self._buttons:
			button.Enable(not busy)

	# ---- selection helpers ----------------------------------------------
	def getSelectedServices(self):
		selected = []
		idx = self.listCtrl.GetFirstSelected()
		while idx != -1:
			selected.append(self.services[idx])
			idx = self.listCtrl.GetNextSelected(idx)
		return selected

	# ---- actions --------------------------------------------------------
	def onDisableSelected(self, event):
		if self._busy:
			return
		self._confirmAndApply(self.getSelectedServices(), "disable")

	def onEnableSelected(self, event):
		if self._busy:
			return
		self._confirmAndApply(self.getSelectedServices(), "enable")

	def onDisableAll(self, event):
		# "Disable all" only touches services rated Safe; Caution ones can affect
		# printing, search, troubleshooters, touch/voice input or security updates
		# and must be selected and confirmed one by one.
		if self._busy:
			return
		targets = [svc for svc in self.services if svc['safety'] == "safe"]
		self._confirmAndApply(targets, "disable", bulk=True)

	def onEnableAll(self, event):
		if self._busy:
			return
		self._confirmAndApply(list(self.services), "enable", bulk=True)

	def onRefresh(self, event):
		if self._busy:
			return
		self.loadServices()

	def onShowDescription(self, event):
		selected = self.getSelectedServices()
		if not selected:
			wx.MessageBox(_("Select a service first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		svc = selected[0]
		if svc['start_type_key'] == "missing":
			wx.MessageBox(_("{name} is not installed on this system.").format(name=svc['display_name']),
						  _("Service Details"), wx.OK | wx.ICON_INFORMATION)
			return
		lines = [
			_("Service name: {name}").format(name=svc['name']),
			_("Display name: {name}").format(name=svc['display_name']),
			_("Startup type: {value}").format(value=svc['start_type']),
			_("Status: {value}").format(value=svc['status']),
		]
		if svc['note']:
			lines.append(_("Caution: {note}").format(note=svc['note']))
		lines.append("")
		lines.append(svc['description'] or _("No description available."))
		wx.MessageBox("\n".join(lines), _("Service Details"), wx.OK | wx.ICON_INFORMATION)

	def _confirmAndApply(self, targets, action, bulk=False):
		if not targets:
			wx.MessageBox(_("Select a service first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		# Rows for services that are not installed on this machine cannot be changed.
		targets = [svc for svc in targets if svc['start_type_key'] != "missing"]
		if not targets:
			wx.MessageBox(_("The selected services are not installed on this system."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		if action == "disable":
			cautionTargets = [svc for svc in targets if svc['safety'] != "safe"]
			if bulk:
				prompt = _("Disable {count} services rated Safe? Services marked Caution are not included. A Windows permission prompt will appear.").format(count=len(targets))
			elif cautionTargets:
				details = "\n".join(f"{svc['name']}: {svc['note']}" for svc in cautionTargets)
				prompt = _("Some selected services are marked Caution:\n{details}\n\nDisable the selected services anyway?").format(details=details)
			else:
				prompt = None
			if prompt is not None:
				answer = wx.MessageBox(prompt, _("Confirm"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
				if answer != wx.YES:
					return
		self._setBusy(True)
		ui.message(_("Applying changes. A Windows permission prompt may appear."))

		def task():
			ok, payload = utils.apply_service_action(self.configDir, targets, action)
			wx.CallAfter(self._onApplyFinished, ok, payload)
		threading.Thread(target=task, daemon=True).start()

	def _onApplyFinished(self, ok, payload):
		if not self:
			return
		self._setBusy(False)
		if not ok:
			tones.beep(220, 200)
			ui.message(payload)
			self.listCtrl.SetFocus()
			return
		failed = [name for name, success in payload.items() if not success]
		changedCount = len(payload) - len(failed)
		if failed:
			tones.beep(220, 200)
			ui.message(_("{changed} changed, {failed} failed: {names}").format(
				changed=changedCount, failed=len(failed), names=", ".join(failed)))
		else:
			tones.beep(440, 100)
			ui.message(_("{changed} services changed.").format(changed=changedCount))
		self.loadServices()

	# ---- context menu (right click / Applications key / Shift+F10) --------
	def onContextMenu(self, event):
		position = event.GetPosition()
		if position != wx.DefaultPosition:
			itemIndex, _flags = self.listCtrl.HitTest(self.listCtrl.ScreenToClient(position))
			if itemIndex != wx.NOT_FOUND and not self.listCtrl.IsSelected(itemIndex):
				idx = self.listCtrl.GetFirstSelected()
				while idx != -1:
					self.listCtrl.Select(idx, False)
					idx = self.listCtrl.GetNextSelected(idx)
				self.listCtrl.Select(itemIndex)
				self.listCtrl.Focus(itemIndex)
		self._showActionsMenu()

	def _showActionsMenu(self):
		# Built from the add-on's own FeatureListDialog instead of PopupMenu, per the
		# project rule against native popup menus (freeze/watchdog risk).
		if self._actionsMenu:
			return
		items = [
			(_("Disable Selected"), self._menuAction(self.onDisableSelected)),
			(_("Enable Selected"), self._menuAction(self.onEnableSelected)),
			(_("Disable all"), self._menuAction(self.onDisableAll)),
			(_("Enable all"), self._menuAction(self.onEnableAll)),
			(_("Show service details"), self._menuAction(self.onShowDescription)),
			(_("Refresh"), self._menuAction(self.onRefresh)),
		]
		menuDialog = FeatureListDialog(_("Service Actions"), items)
		self._actionsMenu = menuDialog

		def onMenuDestroyed(event):
			if event.GetEventObject() is menuDialog:
				wx.CallAfter(self._restoreFocus)
			event.Skip()
		menuDialog.Bind(wx.EVT_WINDOW_DESTROY, onMenuDestroyed)

	def _menuAction(self, handler):
		def callback(menuInstance):
			menuInstance.Close()
			self._actionsMenu = None
			wx.CallAfter(handler, None)
		return callback

	def _restoreFocus(self):
		if not self:
			return
		self.Raise()
		_forceWindowForeground(self.GetHandle())
		self.listCtrl.SetFocus()

	# ---- keyboard / closing ---------------------------------------------
	def onCharHook(self, event):
		keyCode = event.GetKeyCode()
		if keyCode == wx.WXK_ESCAPE:
			wx.CallAfter(self.onClose, event)
			return
		appsKey = getattr(wx, "WXK_WINDOWS_MENU", None)
		isMenuKey = (keyCode == appsKey) or (keyCode == wx.WXK_F10 and event.ShiftDown())
		if isMenuKey and self.FindFocus() is self.listCtrl:
			wx.CallAfter(self._showActionsMenu)
			return
		event.Skip()

	def onClose(self, event):
		if self._actionsMenu:
			self._actionsMenu.Destroy()
		self._actionsMenu = None
		self.Destroy()
