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

SRC_SOURCES = os.path.join(ADDON_PATH, "resources", "sources.xml")

KODI_USERDATA = xbmcvfs.translatePath("special://home/userdata")
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
        else:
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


def wait_for_skin():
    log("Warte auf Skin-Verfügbarkeit...")

    for i in range(30):  # max ~30 Sekunden warten
        if xbmc.getCondVisibility("System.HasAddon(skin.bingie)"):
            log("Skin ist verfügbar.")
            return True
        xbmc.sleep(1000)

    log("Skin wurde nicht rechtzeitig geladen!", xbmc.LOGERROR)
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
    xbmcgui.Dialog().notification(
    "LeoWizard",
    "Bitte nichts klicken...\nSetup wird abgeschlossen",
    xbmcgui.NOTIFICATION_INFO,
    10000
)

    # Kodi erstmal stabil hochfahren lassen
    xbmc.sleep(10000)

    # Addons neu einlesen
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(5000)

    # sources.xml wiederherstellen
    safe_copy(SRC_SOURCES, DEST_SOURCES, "sources.xml")

    # Warten bis Skin wirklich verfügbar ist
    if not wait_for_skin():
        xbmcgui.Dialog().notification(
            "LeoWizard",
            "Skin konnte nicht geladen werden!",
            xbmcgui.NOTIFICATION_ERROR,
            4000
        )
        return

    # Skin + Sprache setzen
    set_setting("lookandfeel.skin", "skin.bingie")
    xbmc.sleep(1000)
    xbmc.executebuiltin("SendClick(yesnodialog,11)")
    set_setting("locale.language", "resource.language.de_de")

    xbmc.sleep(2000)
    xbmc.executebuiltin("ReloadSkin()")

    # Flag zurücksetzen
    ADDON.setSettingBool(SETTING_RESTORE_PENDING, False)
    log("Finalisierung abgeschlossen.")

    xbmcgui.Dialog().ok(
    "LeoWizard",
    "FERTIG!\nDein Kodi ist jetzt komplett eingerichtet.\nViel Spaß!"
)


if __name__ == "__main__":
    finalize_restore()