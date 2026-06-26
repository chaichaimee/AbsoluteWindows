# menu.py

import wx
import addonHandler
import tones
import os
import threading
import sys
import core
from logHandler import log
import ui
from . import utils
from . import sys_monitor

addonHandler.initTranslation()

_instance = None
_monitor_instance = None

class AbsoluteWindowsMenu(wx.Frame):
	def __init__(self, itemsFunc, configPath):
		super().__init__(None, title=_("AbsoluteWindows"), size=(400, 300),
						 style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
		self.itemsFunc = itemsFunc
		self.configPath = configPath
		self.currentItems = []

		panel = wx.Panel(self)
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
		vbox.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)
		panel.SetSizer(vbox)

		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimeout, self.timer)

		self.refreshList()

		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, self.onSelect)
		self.listBox.Bind(wx.EVT_CHAR_HOOK, self.onKey)

		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_ACTIVATE, self.onActivate)

		self.Show()
		self.Raise()
		self.RequestUserAttention()
		self.timer.Start(15000)

	def refreshList(self):
		rawItems = self.itemsFunc()
		self.currentItems = rawItems
		self.listBox.Clear()
		for label, _ in rawItems:
			self.listBox.Append(label)
		if self.listBox.GetCount() > 0:
			self.listBox.SetSelection(0)
		self.listBox.SetFocus()
		self.timer.Start(15000)

	def onActivate(self, event):
		if event.GetActive():
			self.refreshList()
		event.Skip()

	def onSelect(self, event):
		self.timer.Start(15000)
		idx = self.listBox.GetSelection()
		if idx != wx.NOT_FOUND:
			callback = self.currentItems[idx][1]
			if callback is not None:
				callback(self)

	def onKey(self, event):
		self.timer.Start(15000)
		key = event.GetKeyCode()
		if key == wx.WXK_RETURN:
			idx = self.listBox.GetSelection()
			if idx != wx.NOT_FOUND:
				callback = self.currentItems[idx][1]
				if callback is not None:
					callback(self)
		elif key == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def onTimeout(self, event):
		tones.beep(100, 100)
		self.Close()

	def onClose(self, event):
		global _instance
		_instance = None
		self.Destroy()


class SystemMonitorMenu(wx.Frame):
	def __init__(self, itemsFunc, configPath):
		super().__init__(None, title=_("System Monitor"), size=(500, 450),
						 style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
		self.itemsFunc = itemsFunc
		self.configPath = configPath
		self.currentItems = []
		self.updateScheduled = False
		self._firstLoad = True

		panel = wx.Panel(self)
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
		vbox.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)
		panel.SetSizer(vbox)

		self.closeTimer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimeout, self.closeTimer)

		self.listBox.Append(_("Loading system information..."))
		self.closeTimer.Start(30000)

		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, self.onSelect)
		self.listBox.Bind(wx.EVT_CHAR_HOOK, self.onKey)

		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_ACTIVATE, self.onActivate)

		self.Show()
		self.Raise()
		self.RequestUserAttention()

		core.callLater(50, self.scheduleRefresh)

	def scheduleRefresh(self):
		if self.updateScheduled:
			return
		self.updateScheduled = True
		sys_monitor.get_monitor_items_async(self.onDataReceived)

	def onDataReceived(self, items):
		self.updateScheduled = False
		if not self or not self.IsShown():
			return
		try:
			self.currentItems = items
			self.listBox.Clear()
			if items:
				for label, _ in items:
					self.listBox.Append(label)
				if self.listBox.GetCount() > 0:
					self.listBox.SetSelection(0)
					if self._firstLoad and items:
						self._firstLoad = False
						ui.message(items[0][0])
			else:
				self.listBox.Append(_("No data available"))
			self.listBox.SetFocus()
			self.closeTimer.Start(30000)
		except Exception as e:
			log.error("Error updating monitor display: {}".format(e))

	def refreshDisplay(self):
		if self.updateScheduled:
			return
		self.scheduleRefresh()

	def onActivate(self, event):
		if event.GetActive():
			self.refreshDisplay()
		event.Skip()

	def onSelect(self, event):
		self.closeTimer.Start(30000)
		idx = self.listBox.GetSelection()
		if idx != wx.NOT_FOUND and idx < len(self.currentItems):
			callback = self.currentItems[idx][1]
			if callback is not None and callable(callback):
				callback(self)

	def onKey(self, event):
		self.closeTimer.Start(30000)
		key = event.GetKeyCode()
		if key == wx.WXK_RETURN:
			idx = self.listBox.GetSelection()
			if idx != wx.NOT_FOUND and idx < len(self.currentItems):
				callback = self.currentItems[idx][1]
				if callback is not None and callable(callback):
					callback(self)
		elif key == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def onTimeout(self, event):
		tones.beep(100, 100)
		self.Close()

	def onClose(self, event):
		global _monitor_instance
		_monitor_instance = None
		self.Destroy()


def showAbsoluteWindowsMenu(itemsFunc, configPath):
	global _instance
	if _instance:
		_instance.Raise()
		_instance.RequestUserAttention()
		_instance.refreshList()
		_instance.timer.Start(15000)
	else:
		_instance = AbsoluteWindowsMenu(itemsFunc, configPath)


def showSystemMonitorMenu(itemsFunc, configPath):
	global _monitor_instance
	if _monitor_instance:
		_monitor_instance.Raise()
		_monitor_instance.RequestUserAttention()
		_monitor_instance.refreshDisplay()
		_monitor_instance.closeTimer.Start(30000)
	else:
		_monitor_instance = SystemMonitorMenu(itemsFunc, configPath)


class UsbEjectDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(None, title=_("Safely Remove USB"), size=(500, 300),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.usbItems = []

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.listCtrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.listCtrl.AppendColumn(_("Drive"), width=100)
		self.listCtrl.AppendColumn(_("Label"), width=350)
		sizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.ejectBtn = wx.Button(panel, label=_("Eject Selected"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		btnSizer.Add(self.ejectBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.Bind(wx.EVT_BUTTON, self.onEject, self.ejectBtn)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

		self.loadUsbDrives()

		self.Centre()
		self.Show()

	def loadUsbDrives(self):
		self.usbItems = utils.get_usb_drives()
		self.listCtrl.DeleteAllItems()
		for idx, item in enumerate(self.usbItems):
			self.listCtrl.InsertItem(idx, item['letter'])
			self.listCtrl.SetItem(idx, 1, item['name'])
		if not self.usbItems:
			self.listCtrl.InsertItem(0, _("No USB drives found"))

	def onEject(self, event):
		idx = self.listCtrl.GetFirstSelected()
		if idx == -1 or not self.usbItems:
			wx.MessageBox(_("Select a USB drive first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		item = self.usbItems[idx]
		self.ejectBtn.Disable()
		success = utils.eject_usb(item['letter'])
		if success:
			wx.MessageBox(_("USB drive {drive} ejected safely.").format(drive=item['letter']), _("Success"), wx.OK | wx.ICON_INFORMATION)
			self.loadUsbDrives()
		else:
			wx.MessageBox(_("Failed to eject {drive}.").format(drive=item['letter']), _("Error"), wx.OK | wx.ICON_ERROR)
		self.ejectBtn.Enable()

	def onClose(self, event):
		self.Destroy()

	def onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
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
		wx.MessageBox(_("Optimizing drive, please wait..."), _("Info"), wx.OK | wx.ICON_INFORMATION)

	def onOptimizeFinished(self, success, msg):
		self.optimizeBtn.Enable()
		if success:
			wx.MessageBox(_("Optimization completed."), _("Success"), wx.OK | wx.ICON_INFORMATION)
		else:
			wx.MessageBox(_("Optimization failed: {}").format(msg), _("Error"), wx.OK | wx.ICON_ERROR)

	def onClose(self, event):
		self.Destroy()


class ManageServicesDialog(wx.Dialog):
	def __init__(self, configDir):
		super().__init__(None, title=_("Manage Services"), size=(700, 500),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.configDir = configDir
		self.services = []

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.listCtrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.listCtrl.AppendColumn(_("Service Name"), width=200)
		self.listCtrl.AppendColumn(_("Display Name"), width=200)
		self.listCtrl.AppendColumn(_("Startup Type"), width=120)
		self.listCtrl.AppendColumn(_("Status"), width=80)
		sizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.disableBtn = wx.Button(panel, label=_("Disable Selected"))
		self.enableBtn = wx.Button(panel, label=_("Enable Selected"))
		self.refreshBtn = wx.Button(panel, label=_("Refresh"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		btnSizer.Add(self.disableBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.enableBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.refreshBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.Bind(wx.EVT_BUTTON, self.onDisable, self.disableBtn)
		self.Bind(wx.EVT_BUTTON, self.onEnable, self.enableBtn)
		self.Bind(wx.EVT_BUTTON, self.onRefresh, self.refreshBtn)
		self.Bind(wx.EVT_BUTTON, self.onClose, self.closeBtn)
		self.Bind(wx.EVT_CLOSE, self.onClose)

		self.loadServices()

		self.Centre()
		self.Show()

	def loadServices(self):
		self.services = utils.get_suggested_services()
		self.listCtrl.DeleteAllItems()
		for idx, svc in enumerate(self.services):
			self.listCtrl.InsertItem(idx, svc['name'])
			self.listCtrl.SetItem(idx, 1, svc['display_name'])
			self.listCtrl.SetItem(idx, 2, svc['start_type'])
			self.listCtrl.SetItem(idx, 3, svc['status'])

	def getSelectedIndex(self):
		return self.listCtrl.GetFirstSelected()

	def onDisable(self, event):
		idx = self.getSelectedIndex()
		if idx == -1:
			wx.MessageBox(_("Select a service first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		svc = self.services[idx]
		success, msg = utils.disable_service(svc['name'])
		if success:
			self.loadServices()
		else:
			wx.MessageBox(_("Failed to disable service: {}").format(msg), _("Error"), wx.OK | wx.ICON_ERROR)

	def onEnable(self, event):
		idx = self.getSelectedIndex()
		if idx == -1:
			wx.MessageBox(_("Select a service first."), _("Error"), wx.OK | wx.ICON_ERROR)
			return
		svc = self.services[idx]
		success, msg = utils.enable_service(svc['name'])
		if success:
			self.loadServices()
		else:
			wx.MessageBox(_("Failed to enable service: {}").format(msg), _("Error"), wx.OK | wx.ICON_ERROR)

	def onRefresh(self, event):
		self.loadServices()

	def onClose(self, event):
		self.Destroy()