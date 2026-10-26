![NVDA Logo](https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico)

# AbsoluteWindows

Professional Windows Maintenance & Control Suite

**author:** chai chaimee

**url:** https://github.com/chaichaimee/AbsoluteWindows

## Introduction

AbsoluteWindows puts the Windows tools you reach for most behind two simple keyboard shortcuts. One shortcut opens a single accessible menu where you can switch the internet or Bluetooth on and off, eject a USB drive, clean temporary files, run system repair reports, manage startup items and services, start a Windows Defender scan, and much more, without hunting through Settings, the Control Panel or the command line.

A second shortcut closes stuck programs or ejects a USB drive instantly, and a built-in System Monitor reads out the health of your computer at a glance. Every action gives clear spoken feedback and a short beep: a higher beep when it worked and a lower beep when it failed.

## Hot Keys

**ALT+Windows+W**

- Single Tap : Open AbsoluteWindows Menu
- Double Tap : System Monitor

**ALT+Windows+Z**

- Single Tap : Kill Not Responding Apps
- Double Tap : Safely Remove USB

## Features

### Using the Menu

The menu is a plain list. Focus lands on the first item, so NVDA reads it straight away.

- Up Arrow and Down Arrow : move through the list. The selection stops at the first and last item instead of wrapping around.
- Home and End : jump to the first or last item.
- Type a letter : jump to the next item that starts with that letter.
- Enter : run the selected item.
- Escape : go back one level when you are inside a submenu, or close the menu when you are at the top level.

Two items, Run Cmd and Maintenance Tools, open submenus of their own. Toggle items such as Connect Internet and Disconnect Internet keep the menu open and update their own label after they run; most other items close the menu first.

Menu order: System Tray, Connect or Disconnect Internet, Toggle Bluetooth, Show Wi-Fi Password, Safely Remove USB, Restart Windows Audio Service, Quick Switch Audio Device, Enable or Disable User Account Control, Enable or Disable Search Web Results, Restart to BIOS/UEFI Settings, Kill Not Responding Apps, Restart Windows Explorer, Control Panel, Programs and Features, Volume Mixer, Sound setting, Folder Option, Startup Manager, Open Services, Manage Services, Environment Variables, Run Cmd, Maintenance Tools, Regedit, Windows Defender, Windows Defender Full Scan Low, Microsoft Windows Malicious Software Removal Tool, Optimize and defragment drive, Disk Cleanup, Clean Prefetch & Recent, Clean System files, Clean Temp, Clean Windows Run History, Empty Recycle Bin and Clear Ram.

### System Tray

Opens the notification area (system tray) overflow and expands it, so you can move through the tray icons with the arrow keys. This does the same as pressing Windows+B and then Space.

### Connect or Disconnect Internet

The menu item reads Disconnect Internet when you are online and Connect Internet when you are offline. Your connection is checked each time the menu is built, and the result is remembered for a few seconds.

Disconnect Internet:

1. Choose Disconnect Internet.
2. AbsoluteWindows finds your active network adapter.
3. Approve the Windows permission prompt (UAC).
4. The adapter is disabled and you hear "Internet disconnected."

Connect Internet re-enables the adapter that was disconnected earlier. If AbsoluteWindows was restarted since then, it re-enables the first disabled network adapter it finds. If no suitable adapter exists, you are told so.

### Toggle Bluetooth

Switches the Bluetooth radio on when it is off and off when it is on, and announces "Bluetooth turned on." or "Bluetooth turned off." If no Bluetooth radio can be found or changed, you are told so.

### Show Wi-Fi Password

Copies the saved password of the Wi-Fi network you are connected to straight to the clipboard, so you can paste it where you need it. The password is not read aloud.

1. Connect to the Wi-Fi network.
2. Open the menu and choose Show Wi-Fi Password.
3. You hear "Wi-Fi password for" followed by the network name, "copied to clipboard."
4. Paste the password with Control+V.

If the network is open, you hear that it has no password. If no Wi-Fi network is connected, you are told so.

### Safely Remove USB

Ejects a removable USB drive so it can be unplugged without losing data. It works from the menu item and from the double tap of ALT+Windows+Z. Only removable drives are considered.

- One drive connected : it is ejected immediately and you hear "USB drive" followed by the drive letter, "ejected safely." No dialog appears.
- More than one drive connected : a list opens with the columns Drive and Label. Move to the drive you want and press Enter to eject it. The list refreshes after each eject and closes by itself when no drives remain. Escape closes the list.
- No drive connected : you hear "No USB drives found."

### Restart Windows Audio Service

Stops and starts the Windows Audio service. Use it when sound disappears or stops responding. Windows asks for permission first. You hear "Windows Audio Services restarted successfully." or a failure message.

### Quick Switch Audio Device

Switches your default sound output to the next playback device in the list of active devices, and goes back to the first device after the last one. The new device is set for normal use, multimedia and communications, and its name is announced.

1. Open the menu and choose Quick Switch Audio Device.
2. Listen for "Switched to" followed by the device name.
3. Repeat the same steps to move on to the next device.

At least two active playback devices are needed. With only one, you hear "Only one playback device is available."

### User Account Control

The menu item reads Disable User Account Control when UAC is on and Enable User Account Control when it is off. Choosing it asks for Windows permission, changes the setting and keeps the menu open with the updated label.

Windows applies the change only after a restart. AbsoluteWindows announces this after the change.

### Search Web Results

Turns web results in Windows Search off or on. The menu item reads Disable Search Web Results or Enable Search Web Results depending on the current state. After the change, Windows Explorer is restarted automatically so the setting takes effect, and the menu stays open with the updated label.

### Restart to BIOS/UEFI Settings

Restarts the computer straight into the firmware (BIOS/UEFI) setup screen. Windows asks for permission first.

The computer restarts immediately. Save your work and close your programs before choosing this item. If the system does not support the feature, you hear that it may not be supported.

### Kill Not Responding Apps

Opens a list of the application windows currently open on the desktop. Each entry shows the window title followed by its program name in square brackets. System components and Windows shell windows are left out of the list.

1. Press ALT+Windows+Z once, or choose Kill Not Responding Apps from the menu.
2. Move to the window of the frozen program in the list.
3. Press Alt+K to activate the Kill Process of Selected Window button, or double-click the entry. A right-click menu with Kill Process is also available.
4. The program is ended immediately and you hear "Process terminated." The list refreshes.
5. Press Escape or choose Close to leave the dialog.

File Explorer windows are asked to close instead of being ended, so the desktop keeps working. Critical Windows processes and NVDA itself are protected and cannot be ended. If Windows denies access to a process, you are told so.

### Restart Windows Explorer

Restarts Windows Explorer. Use it when the taskbar, desktop or File Explorer stops responding. You hear "Windows Explorer has been restarted." when it is done.

### Quick Access to Windows Tools

These menu items open common Windows tools directly:

- Control Panel : opens the classic Control Panel.
- Programs and Features : opens the list of installed programs for uninstalling.
- Volume Mixer : opens the classic Volume Mixer with a volume control for each application.
- Sound setting : opens the classic Sound settings with the playback and recording devices.
- Folder Option : opens Folder Options (File Explorer Options) and brings it to the front.
- Open Services : opens the Windows Services console.
- Environment Variables : opens the Environment Variables window.
- Regedit : opens the Registry Editor.
- Optimize and defragment drive : opens the Optimize Drives window.
- Disk Cleanup : opens the Windows Disk Cleanup tool.

If a tool cannot be opened, you hear a short message saying which one failed.

### Startup Manager

Shows the programs that start with Windows and lets you turn them off. The list has the columns Name, Type, Status and Location, and covers the Run entries of the current user and of the whole computer, plus the Startup folder of the current user and of all users.

1. Choose Startup Manager from the menu.
2. Move to the program you want to change.
3. Choose Disable Selected to stop it from starting with Windows. A shortcut or program file in a Startup folder is moved into a StartupBackup folder in the add-on settings folder instead of being deleted.
4. Choose Enable Selected to put a disabled item back. If the item is already in that state, a message tells you so.
5. Press Escape or choose Close to leave the dialog.

### Manage Services

A safe, guided way to turn off Windows background services that most people do not need. The list shows a ready-made set of services, with the columns Display Name, Startup Type, Status and Safety. Each service is rated Safe or Caution. Services that are not installed on your computer are shown as Not installed and cannot be changed.

- Safe : no known effect on speech, sound, braille or other accessibility use.
- Caution : the service may be needed for printing and braille embossers, Start menu and File Explorer search, Windows security updates, troubleshooters, touch keyboard and voice typing, Xbox controllers, smart card sign-in, or scanners and cameras.

Buttons: Disable Selected, Enable Selected, Disable all, Enable all, Refresh and Close. You can select several services at once. The same actions are in a right-click menu, which also opens with the Applications key or Shift+F10, together with Show service details.

How to disable services:

1. Choose Manage Services and wait for "services listed" to be announced.
2. Select one or more services. Press Enter on a row, or choose Show service details, to read the service name, display name, startup type, status, any caution note and the description.
3. Choose Disable Selected. If any selected service is rated Caution, a warning lists the reasons and you confirm before anything changes.
4. Approve the single Windows permission prompt. It covers every selected service.
5. Listen for the result, for example "3 services changed." The list refreshes by itself.

Disable all only touches services rated Safe and asks for confirmation. Before a service is disabled, its original startup type is saved, and Enable puts back exactly that type. When none was saved, a default is used. Services that are started automatically are also started again when enabled. The audio services, themes, text input, Bluetooth and a few core Windows services are protected and are never changed.

### Windows Defender Tools

- Windows Defender : opens the Windows Security threat protection settings.
- Windows Defender Full Scan Low : starts a full Windows Defender scan in the background at low priority, so your computer stays responsive while it runs. Windows asks for permission first.
- Microsoft Windows Malicious Software Removal Tool : opens the tool and brings its window to the front.

### Cleaning Tools

- Clean Temp : deletes the files and folders in your Temp folder and in the Windows Temp folder, skipping anything that is in use. You hear how many items were removed.
- Clean Prefetch & Recent : deletes the Windows Prefetch files and the files in your Recent items folder, and announces the number removed.
- Clean System files : starts the Windows Disk Cleanup with its saved settings in the background. Windows asks for permission first.
- Clean Windows Run History : clears the list of commands remembered by the Run dialog and announces how many were removed.
- Empty Recycle Bin : empties the Recycle Bin without asking for confirmation and announces how many items were removed, or that it was already empty.
- Clear Ram : trims the memory held by running programs, other than NVDA and core system processes, and announces how many megabytes were freed, or that the cache is already clean.

### Run Cmd Submenu

Runs Windows repair and diagnostic commands for you. Windows asks for permission first. A command window opens and stays open until you press a key. When the work is done, the result is saved as a text report in the add-on settings folder and opened in Notepad.

- Run DISM : checks and repairs the Windows image. This can take a long time.
- DISM Get International Settings : reports the language, locale and keyboard settings of Windows.
- Run SFC Scannow : scans and repairs protected system files. It first makes sure the service it depends on is available.
- Run Chkdsk on C: : on the system drive, Windows normally only schedules the check for the next restart. Restart Windows to see the real scan results. The report includes whether a check is pending.
- Run Disk Cleanup : runs Disk Cleanup and reports the free space on C: before and after.
- Power Diagnostic (Battery Report) : creates a battery health report and opens it in your web browser.
- Check Disk Status : lists each physical disk with its name, media type, health status and size.
- Backup Open With : see Backup and Restore Open With below.
- Restore Open With : see Backup and Restore Open With below.

### Backup and Restore Open With

Saves and restores the programs you have chosen to open each file type, for example which player opens your music files. It works for your own Windows user account and needs no permission prompt.

To back up:

1. Open the menu, choose Run Cmd, then Backup Open With.
2. Wait for the confirmation. The backup is saved in a folder named with the date and time inside the add-on settings folder.

To restore:

1. Open the menu, choose Run Cmd, then Restore Open With.
2. A list of your saved backups appears, newest first. If there are none, the list says "No Open With backups found."
3. Choose the backup you want and press Enter.
4. After you hear that the associations were restored, restart Windows Explorer from the menu, or sign out and back in, for the change to take effect.

A backup restores reliably only on the same Windows installation and the same user account. It does not carry over after Windows is reinstalled.

### Maintenance Tools Submenu

- Update All Packages (winget upgrade) : updates every installed program that winget can update, silently and with the license agreements accepted. It runs with your own user rights, and the report opens in Notepad when it finishes.
- List Installed Packages (winget list) : saves the list of installed packages to a report and opens it in Notepad.
- Defragment Windows Search Database : stops the Windows Search service, compacts its index database, then starts the service again. Windows asks for permission first, and a report opens when it finishes.
- Run Windows Defender Full Scan : starts a full Windows Defender scan in the background at normal priority.
- Clear URL Cache : clears the Temporary Internet Files cache of the current user and opens a short report.

### System Monitor

A read-only snapshot of how your computer is doing. Press ALT+Windows+W twice, and after a short "Loading system information..." message a list opens. Move through it with the arrow keys and press Escape to close it.

- CPU : current processor load.
- RAM : memory used and total, with a percentage.
- Disk : used and total space for each fixed drive.
- Disk Activity : read and write speed, when available.
- Network Speed : download and upload speed, or the network status Connected or Disconnected when no speed is available.
- Wi-Fi : the connected network name and its signal quality (Excellent, Good, Fair, Weak or Very Weak).
- Battery : charge percentage and whether it is charging, fully charged, discharging or low. Shown only on computers with a battery.
- Uptime : how long Windows has been running.
- Processes : the number of running processes.
- GPU : the name of the graphics adapter.
- Windows Activation : Activated or Not Activated.
- Windows : the Windows edition, bit version and build.

### Network Usage

Most features work entirely on your own computer. Two things use the network:

- Checking whether you are online, for the Connect and Disconnect Internet item and the System Monitor, sends a single test ping to the public address 8.8.8.8.
- Update All Packages (winget upgrade) contacts the winget package sources to find and download updates.

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

Your support means the world. Let's build something great together

© 2026 Chai Chaimee NVDA Add-on Released under GNU GPL
