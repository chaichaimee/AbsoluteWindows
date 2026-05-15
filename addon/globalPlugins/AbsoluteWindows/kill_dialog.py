# kill_dialog.py

import wx
import ctypes
from ctypes import wintypes, WINFUNCTYPE, c_int
import winUser
import winKernel
import appModuleHandler
import ui
import tones
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except:
	def _(x): return x

PROCESS_TERMINATE = 0x0001
WM_CLOSE = 0x0010

CRITICAL_PROCESSES = [
	"System", "Idle", "Memory Compression",
	"csrss.exe", "winlogon.exe", "services.exe",
	"lsass.exe", "wininit.exe", "nvda.exe"
]

EXCLUDED_PROCESSES = (
	"textinputhost.exe",
	"shellexperiencehost.exe",
	"startmenuexperiencehost.exe",
	"searchapp.exe",
	"applicationframehost.exe",
	"lockapp.exe",
	"systemsettings.exe",
)

class KillDialog(wx.Dialog):
	_instance = None

	@classmethod
	def get_instance(cls, parent=None):
		if cls._instance is None or not cls._instance:
			cls._instance = cls(parent)
		else:
			try:
				cls._instance.Raise()
				cls._instance.SetFocus()
				cls._instance.Show()
			except:
				cls._instance = cls(parent)
		return cls._instance

	def __init__(self, parent=None):
		super().__init__(parent, title=_("Kill Not Responding Apps"), size=(600, 400),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP)
		self.windowList = []
		self._buildUI()
		self.refreshWindowList()
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Centre()
		self.Raise()
		self.Show()
		self.SetFocus()

	def _buildUI(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
		sizer.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)

		btnSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.killBtn = wx.Button(panel, label=_("&Kill Process of Selected Window"))
		self.closeBtn = wx.Button(panel, label=_("Close"))
		btnSizer.Add(self.killBtn, 0, wx.ALL, 5)
		btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
		sizer.Add(btnSizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)

		self.killBtn.Bind(wx.EVT_BUTTON, self.onKillProcess)
		self.closeBtn.Bind(wx.EVT_BUTTON, self.onClose)
		self.listBox.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, self.onDoubleClick)

	def onDoubleClick(self, event):
		self.onKillProcess(event)

	def refreshWindowList(self):
		self.windowList = []
		
		EnumWindowsProc = WINFUNCTYPE(c_int, wintypes.HWND, wintypes.LPARAM)
		
		@EnumWindowsProc
		def enumCallback(hwnd, lParam):
			if not winUser.isWindowVisible(hwnd) or not winUser.isWindowEnabled(hwnd):
				return 1
			title = winUser.getWindowText(hwnd)
			if not title:
				return 1
			pid = winUser.getWindowThreadProcessID(hwnd)[0]
			processName = appModuleHandler.getAppNameFromProcessID(pid, True)
			if not processName:
				processName = f"PID:{pid}"
			
			if processName.lower() in CRITICAL_PROCESSES:
				log.debug(f"Skipping critical process: {processName}")
				return 1
			
			if processName.lower() in EXCLUDED_PROCESSES:
				log.debug(f"Skipping excluded process: {processName}")
				return 1
			
			log.debug(f"Adding window: title={title}, process={processName}, pid={pid}")
			self.windowList.append((hwnd, pid, title, processName))
			return 1

		winUser.user32.EnumWindows(enumCallback, 0)

		self.listBox.Clear()
		for (hwnd, pid, title, pname) in self.windowList:
			self.listBox.Append(f"{title} [{pname}]")
		if self.listBox.GetCount() > 0:
			self.listBox.SetSelection(0)
			self.listBox.SetFocus()
		self._updateButtons()
		log.info(f"Refresh: found {len(self.windowList)} windows")

	def _updateButtons(self):
		hasSelection = (self.listBox.GetSelection() != wx.NOT_FOUND)
		self.killBtn.Enable(hasSelection)

	def _getSelectedWindow(self):
		idx = self.listBox.GetSelection()
		if idx == wx.NOT_FOUND or idx >= len(self.windowList):
			return None
		return self.windowList[idx]

	def _closeWindow(self, hwnd):
		winUser.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
		return True

	def onKillProcess(self, event):
		selected = self._getSelectedWindow()
		if not selected:
			ui.message(_("No window selected."))
			tones.beep(220, 200)
			return
		hwnd, pid, title, pname = selected
		log.info(f"Killing: PID={pid}, name={pname}, title={title}")

		if pname.lower() in CRITICAL_PROCESSES:
			ui.message(_("Cannot kill system process: {}").format(pname))
			tones.beep(220, 200)
			return

		if pname.lower() == "explorer.exe":
			log.info(f"Sending WM_CLOSE to explorer window: {title}")
			if self._closeWindow(hwnd):
				tones.beep(440, 100)
				ui.message(_("Window closed."))
				self.refreshWindowList()
				if self.listBox.GetCount() > 0:
					self.listBox.SetFocus()
			else:
				tones.beep(220, 200)
				ui.message(_("Failed to close window."))
			return

		handle = winKernel.kernel32.OpenProcess(PROCESS_TERMINATE, 0, pid)
		if not handle:
			log.error(f"OpenProcess failed for PID {pid}")
			ui.message(_("Cannot open process. Access denied."))
			tones.beep(220, 200)
			return

		success = winKernel.kernel32.TerminateProcess(handle, 0)
		winKernel.kernel32.CloseHandle(handle)

		if success:
			log.info(f"Terminated PID {pid}")
			tones.beep(440, 100)
			ui.message(_("Process terminated."))
			self.refreshWindowList()
			if self.listBox.GetCount() > 0:
				self.listBox.SetFocus()
		else:
			log.error(f"TerminateProcess failed for PID {pid}")
			tones.beep(220, 200)
			ui.message(_("Failed to terminate process. Insufficient privileges."))

	def onClose(self, event):
		self.Destroy()
		KillDialog._instance = None

	def onCharHook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def onContextMenu(self, event):
		pos = event.GetPosition()
		item = self.listBox.HitTest(pos)
		if item != wx.NOT_FOUND:
			self.listBox.SetSelection(item)
		else:
			item = self.listBox.GetSelection()
			if item == wx.NOT_FOUND:
				return
		menu = wx.Menu()
		killItem = menu.Append(wx.ID_ANY, _("Kill Process"))
		self.Bind(wx.EVT_MENU, lambda evt: self.onKillProcess(evt), killItem)
		self.listBox.PopupMenu(menu)
		menu.Destroy()

def show_kill_dialog():
	try:
		dlg = KillDialog.get_instance()
	except Exception as e:
		log.exception("Failed to open kill dialog")
		ui.message(_("Could not open kill dialog. See log for details."))
		tones.beep(220, 200)