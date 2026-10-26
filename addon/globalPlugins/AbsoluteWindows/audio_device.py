# audio_device.py

import ctypes
from ctypes import POINTER, byref, c_void_p, c_wchar_p, c_ushort, c_ulong
import comtypes
from comtypes import GUID, COMMETHOD, HRESULT, IUnknown, CoCreateInstance, CLSCTX_ALL
from logHandler import log
import addonHandler

addonHandler.initTranslation()
try:
	_ = addonHandler.getTranslation()
except Exception:
	def _(x): return x

CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IMMDeviceCollection = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
IID_IMMDevice = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
IID_IPropertyStore = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
CLSID_PolicyConfigClient = GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
IID_IPolicyConfig = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")

PKEY_Device_FriendlyName_fmtid = GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")
PKEY_Device_FriendlyName_pid = 14

E_RENDER = 0
DEVICE_STATE_ACTIVE = 0x1
E_ROLE_CONSOLE = 0
E_ROLE_MULTIMEDIA = 1
E_ROLE_COMMUNICATIONS = 2
STGM_READ = 0x00000000
VT_LPWSTR = 31


class PROPERTYKEY(ctypes.Structure):
	_fields_ = [("fmtid", GUID), ("pid", c_ulong)]


class PROPVARIANT(ctypes.Structure):
	_fields_ = [
		("vt", c_ushort),
		("wReserved1", c_ushort),
		("wReserved2", c_ushort),
		("wReserved3", c_ushort),
		("data", c_void_p),
	]


class IPropertyStore(IUnknown):
	_iid_ = IID_IPropertyStore
	_methods_ = [
		COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(c_ulong), "cProps")),
		COMMETHOD([], HRESULT, "GetAt", (["in"], c_ulong, "iProp"), (["out"], POINTER(PROPERTYKEY), "pkey")),
		COMMETHOD([], HRESULT, "GetValue", (["in"], POINTER(PROPERTYKEY), "key"), (["out"], POINTER(PROPVARIANT), "pv")),
		COMMETHOD([], HRESULT, "SetValue", (["in"], POINTER(PROPERTYKEY), "key"), (["in"], POINTER(PROPVARIANT), "propvar")),
		COMMETHOD([], HRESULT, "Commit"),
	]


class IMMDevice(IUnknown):
	_iid_ = IID_IMMDevice
	_methods_ = [
		COMMETHOD([], HRESULT, "Activate",
			(["in"], POINTER(GUID), "iid"),
			(["in"], c_ulong, "dwClsCtx"),
			(["in"], c_void_p, "pActivationParams"),
			(["out"], POINTER(c_void_p), "ppInterface")),
		COMMETHOD([], HRESULT, "OpenPropertyStore",
			(["in"], c_ulong, "stgmAccess"),
			(["out"], POINTER(POINTER(IPropertyStore)), "ppProperties")),
		COMMETHOD([], HRESULT, "GetId", (["out"], POINTER(c_wchar_p), "ppstrId")),
		COMMETHOD([], HRESULT, "GetState", (["out"], POINTER(c_ulong), "pdwState")),
	]


class IMMDeviceCollection(IUnknown):
	_iid_ = IID_IMMDeviceCollection
	_methods_ = [
		COMMETHOD([], HRESULT, "GetCount", (["out"], POINTER(c_ulong), "pcDevices")),
		COMMETHOD([], HRESULT, "Item",
			(["in"], c_ulong, "nDevice"),
			(["out"], POINTER(POINTER(IMMDevice)), "ppDevice")),
	]


class IMMDeviceEnumerator(IUnknown):
	_iid_ = IID_IMMDeviceEnumerator
	_methods_ = [
		COMMETHOD([], HRESULT, "EnumAudioEndpoints",
			(["in"], c_ulong, "dataFlow"),
			(["in"], c_ulong, "dwStateMask"),
			(["out"], POINTER(POINTER(IMMDeviceCollection)), "ppDevices")),
		COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
			(["in"], c_ulong, "dataFlow"),
			(["in"], c_ulong, "role"),
			(["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint")),
		COMMETHOD([], HRESULT, "GetDevice",
			(["in"], c_wchar_p, "pwstrId"),
			(["out"], POINTER(POINTER(IMMDevice)), "ppDevice")),
	]


class IPolicyConfig(IUnknown):
	_iid_ = IID_IPolicyConfig
	_methods_ = [
		COMMETHOD([], HRESULT, "GetMixFormat",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["out"], POINTER(c_void_p), "ppFormat")),
		COMMETHOD([], HRESULT, "GetDeviceFormat",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "bDefault"),
			(["out"], POINTER(c_void_p), "ppFormat")),
		COMMETHOD([], HRESULT, "ResetDeviceFormat", (["in"], c_wchar_p, "pszDeviceName")),
		COMMETHOD([], HRESULT, "SetDeviceFormat",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_void_p, "pEndpointFormat"),
			(["in"], c_void_p, "pMixFormat")),
		COMMETHOD([], HRESULT, "GetProcessingPeriod",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "bDefault"),
			(["out"], POINTER(ctypes.c_longlong), "pmftDefaultPeriod"),
			(["out"], POINTER(ctypes.c_longlong), "pmftMinimumPeriod")),
		COMMETHOD([], HRESULT, "SetProcessingPeriod",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], POINTER(ctypes.c_longlong), "pmftPeriod")),
		COMMETHOD([], HRESULT, "GetShareMode",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["out"], c_void_p, "pMode")),
		COMMETHOD([], HRESULT, "SetShareMode",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_void_p, "mode")),
		COMMETHOD([], HRESULT, "GetPropertyValue",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "bFxStore"),
			(["in"], POINTER(PROPERTYKEY), "key"),
			(["out"], POINTER(PROPVARIANT), "pv")),
		COMMETHOD([], HRESULT, "SetPropertyValue",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "bFxStore"),
			(["in"], POINTER(PROPERTYKEY), "key"),
			(["in"], POINTER(PROPVARIANT), "propvar")),
		COMMETHOD([], HRESULT, "SetDefaultEndpoint",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "role")),
		COMMETHOD([], HRESULT, "SetEndpointVisibility",
			(["in"], c_wchar_p, "pszDeviceName"),
			(["in"], c_ulong, "bVisible")),
	]


def _getDeviceFriendlyName(device):
	try:
		propertyStore = device.OpenPropertyStore(STGM_READ)
		propKey = PROPERTYKEY(PKEY_Device_FriendlyName_fmtid, PKEY_Device_FriendlyName_pid)
		propValue = propertyStore.GetValue(byref(propKey))
		if propValue.vt == VT_LPWSTR and propValue.data:
			name = ctypes.cast(propValue.data, c_wchar_p).value
			ctypes.windll.ole32.PropVariantClear(byref(propValue))
			return name
		ctypes.windll.ole32.PropVariantClear(byref(propValue))
	except Exception as e:
		log.debug(f"Could not read device friendly name: {e}")
	return _("Unknown Device")


def _listActivePlaybackDevices(deviceEnumerator):
	devices = []
	deviceCollection = deviceEnumerator.EnumAudioEndpoints(E_RENDER, DEVICE_STATE_ACTIVE)
	count = deviceCollection.GetCount()
	for i in range(count):
		device = deviceCollection.Item(i)
		deviceId = device.GetId()
		devices.append((deviceId, device))
	return devices


def cycle_default_playback_device():
	"""Switch to the next active playback device, cycling back to the first after the last.
	Returns (success, deviceNameOrErrorMessage)."""
	# Initialize a Multithreaded Apartment explicitly instead of comtypes.CoInitialize(),
	# which defaults to a Single-Threaded Apartment. An STA requires a Windows message
	# pump to service cross-thread COM calls; a plain Python thread has none, so STA
	# calls here can hang indefinitely. MTA avoids that requirement.
	COINIT_MULTITHREADED = 0x0
	ctypes.windll.ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
	try:
		deviceEnumerator = CoCreateInstance(CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator, clsctx=CLSCTX_ALL)
		policyConfig = CoCreateInstance(CLSID_PolicyConfigClient, interface=IPolicyConfig, clsctx=CLSCTX_ALL)

		devices = _listActivePlaybackDevices(deviceEnumerator)
		if len(devices) < 2:
			return False, _("Only one playback device is available.")

		currentDefault = deviceEnumerator.GetDefaultAudioEndpoint(E_RENDER, E_ROLE_MULTIMEDIA)
		currentId = currentDefault.GetId()

		currentIndex = 0
		for index, (deviceId, _device) in enumerate(devices):
			if deviceId == currentId:
				currentIndex = index
				break

		nextIndex = (currentIndex + 1) % len(devices)
		nextDeviceId, nextDevice = devices[nextIndex]

		policyConfig.SetDefaultEndpoint(nextDeviceId, E_ROLE_CONSOLE)
		policyConfig.SetDefaultEndpoint(nextDeviceId, E_ROLE_MULTIMEDIA)
		policyConfig.SetDefaultEndpoint(nextDeviceId, E_ROLE_COMMUNICATIONS)

		deviceName = _getDeviceFriendlyName(nextDevice)
		return True, deviceName
	except Exception as e:
		log.error(f"Failed to switch audio playback device: {e}")
		return False, _("Failed to switch audio device.")
	finally:
		ctypes.windll.ole32.CoUninitialize()
