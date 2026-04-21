import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import shutil
import json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))

SRC_GUISETTINGS = os.path.join(ADDON_PATH, "resources", "guisettings.xml")
SRC_SOURCES = os.path.join(ADDON_PATH, "resources", "sources.xml")

KODI_USERDATA = xbmcvfs.translatePath("special://home/userdata")
DEST_GUISETTINGS = os.path.join(KODI_USERDATA, "guisettings.xml")
DEST_SOURCES = os.path.join(KODI_USERDATA, "sources.xml")

SETTING_RESTORE_PENDING = "restore_pending"


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level)


def jsonrpc(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1
    }
    if params is not None:
        payload["params"] = params

    result = xbmc.executeJSONRPC(json.dumps(payload))
    return json.loads(result)


def safe_copy(src, dst, label):
    try:
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            log(f"{label} kopiert: {src} -> {dst}")
            return True
        log(f"{label} nicht gefunden: {src}", xbmc.LOGWARNING)
    except Exception as e:
        log(f"Fehler beim Kopieren von {label}: {e}", xbmc.LOGERROR)
    return False


def set_setting(setting_name, value):
    try:
        result = jsonrpc("Settings.SetSettingValue", {
            "setting": setting_name,
            "value": value
        })
        if "error" in result:
            log(f"Setting {setting_name} konnte nicht gesetzt werden: {result['error']}", xbmc.LOGERROR)
            return False
        log(f"Setting gesetzt: {setting_name} = {value}")
        return True
    except Exception as e:
        log(f"Fehler beim Setzen von {setting_name}: {e}", xbmc.LOGERROR)
        return False


def finalize_restore():
    try:
        if not ADDON.getSettingBool(SETTING_RESTORE_PENDING):
            log("restore_pending ist nicht gesetzt, nichts zu tun.", xbmc.LOGDEBUG)
            return
    except Exception as e:
        log(f"restore_pending konnte nicht gelesen werden: {e}", xbmc.LOGERROR)
        return

    log("Finalisierung nach Neustart gestartet.")

    xbmc.sleep(8000)

    # nur sources.xml behalten
    safe_copy(SRC_SOURCES, DEST_SOURCES, "sources.xml")

    # guisettings.xml komplett entfernt

    set_setting("lookandfeel.skin", "skin.bingie")
    set_setting("locale.language", "resource.language.de_de")

    xbmc.sleep(2000)
    xbmc.executebuiltin("ReloadSkin()")

    ADDON.setSettingBool(SETTING_RESTORE_PENDING, False)
    log("Finalisierung abgeschlossen, restore_pending entfernt.")

    xbmcgui.Dialog().notification(
        "LeoWizard",
        "Skin und Einstellungen wurden übernommen",
        xbmcgui.NOTIFICATION_INFO,
        4000
    )

if __name__ == "__main__":
    finalize_restore()