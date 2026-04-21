import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import zipfile
import shutil
import json
import urllib.request

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))

BUILD_ZIP_URL = "https://github.com/leobitchy/leosystems-repo/releases/download/leoaddons/addons.zip"

TEMP_DIR = xbmcvfs.translatePath("special://temp/plugin.program.leowizard")
DOWNLOADED_ZIP = os.path.join(TEMP_DIR, "addons.zip")

SRC_SOURCES = os.path.join(ADDON_PATH, "resources", "sources.xml")

KODI_HOME = xbmcvfs.translatePath("special://home")
KODI_USERDATA = xbmcvfs.translatePath("special://home/userdata")
DEST_SOURCES = os.path.join(KODI_USERDATA, "sources.xml")

BLOCKED_ADDONS = [
    "plugin.video.xship",
    "plugin.video.global.xship_search"
]

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


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def show_busy():
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")
    xbmc.sleep(200)


def close_busy():
    xbmc.executebuiltin("Dialog.Close(busydialognocancel)")
    xbmc.sleep(200)


def download_file(url, dest_path):
    ensure_dir(os.path.dirname(dest_path))

    try:
        with urllib.request.urlopen(url) as response:
            with open(dest_path, "wb") as out_file:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    out_file.write(chunk)

        log(f"Build ZIP heruntergeladen: {dest_path}")
        return True

    except Exception as e:
        log(f"Fehler beim Download: {e}", xbmc.LOGERROR)
        return False


def extract_build_zip(zip_path):
    log("Entpacke Build...")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.namelist():

            if member.startswith("addons/"):
                rel_path = member.replace("addons/", "", 1)
                target_path = os.path.join(KODI_HOME, "addons", rel_path)

            elif member.startswith("addon_data/") or member.startswith("addondata/"):
                rel_path = member.replace("addon_data/", "", 1).replace("addondata/", "", 1)
                target_path = os.path.join(KODI_USERDATA, "addon_data", rel_path)

            else:
                continue

            if member.endswith("/"):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zip_ref.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)


def addon_exists(addon_id):
    try:
        result = jsonrpc("Addons.GetAddons", {
            "properties": ["name", "enabled"]
        })
        for addon in result.get("result", {}).get("addons", []):
            if addon.get("addonid") == addon_id:
                return True
    except Exception as e:
        log(f"Fehler bei Addon-Prüfung für {addon_id}: {e}", xbmc.LOGERROR)
    return False


def disable_addon(addon_id):
    try:
        result = jsonrpc("Addons.SetAddonEnabled", {
            "addonid": addon_id,
            "enabled": False
        })
        if "error" in result:
            log(f"Addon konnte nicht deaktiviert werden: {addon_id} - {result['error']}", xbmc.LOGERROR)
            return False
        log(f"Addon deaktiviert: {addon_id}")
        return True
    except Exception as e:
        log(f"Fehler beim Deaktivieren von {addon_id}: {e}", xbmc.LOGERROR)
        return False


def disable_blocked_addons_if_present():
    for addon_id in BLOCKED_ADDONS:
        if addon_exists(addon_id):
            disable_addon(addon_id)
        else:
            log(f"Blockiertes Addon nicht vorhanden: {addon_id}")


def remove_addon_files(addon_id):
    removed_anything = False

    addon_dir = xbmcvfs.translatePath(os.path.join("special://home", "addons", addon_id))
    addon_data_dir = xbmcvfs.translatePath(os.path.join("special://profile", "addon_data", addon_id))

    try:
        if os.path.exists(addon_dir):
            shutil.rmtree(addon_dir, ignore_errors=True)
            log(f"Addon-Ordner gelöscht: {addon_dir}")
            removed_anything = True
    except Exception as e:
        log(f"Fehler beim Löschen von {addon_dir}: {e}", xbmc.LOGERROR)

    try:
        if os.path.exists(addon_data_dir):
            shutil.rmtree(addon_data_dir, ignore_errors=True)
            log(f"Addon-Daten gelöscht: {addon_data_dir}")
            removed_anything = True
    except Exception as e:
        log(f"Fehler beim Löschen von {addon_data_dir}: {e}", xbmc.LOGERROR)

    return removed_anything


def purge_blocked_addons():
    log("Prüfe unerwünschte Addons...")

    for addon_id in BLOCKED_ADDONS:
        if not addon_exists(addon_id):
            continue

        disable_addon(addon_id)
        xbmc.sleep(500)
        remove_addon_files(addon_id)


def enable_all_addons():
    log("Aktiviere alle Addons...")

    result = jsonrpc("Addons.GetAddons", {"enabled": False})
    for addon in result.get("result", {}).get("addons", []):
        addonid = addon.get("addonid")
        if addonid:
            jsonrpc("Addons.SetAddonEnabled", {
                "addonid": addonid,
                "enabled": True
            })

    log("Alle Addons aktiviert.")


def copy_sources_xml():
    try:
        if os.path.exists(SRC_SOURCES):
            shutil.copyfile(SRC_SOURCES, DEST_SOURCES)
            log("sources.xml kopiert.")
    except Exception as e:
        log(f"Fehler beim Kopieren von sources.xml: {e}", xbmc.LOGERROR)


def cleanup_downloaded_zip():
    try:
        if os.path.exists(DOWNLOADED_ZIP):
            os.remove(DOWNLOADED_ZIP)
    except Exception as e:
        log(f"ZIP löschen fehlgeschlagen: {e}", xbmc.LOGERROR)


def cleanup_packages():
    packages_path = xbmcvfs.translatePath(os.path.join(KODI_HOME, "addons", "packages"))
    try:
        if os.path.exists(packages_path):
            shutil.rmtree(packages_path, ignore_errors=True)
    except Exception as e:
        log(f"Fehler beim Löschen von packages: {e}", xbmc.LOGERROR)


def mark_restore_pending():
    ADDON.setSettingBool(SETTING_RESTORE_PENDING, True)
    log("restore_pending gesetzt.")


def run_wizard():
    try:
        xbmcgui.Dialog().ok(
            "LeoWizard",
            "Während der Installation bitte nichts drücken.\n\n"
            "Zum Starten jetzt auf OK klicken und anschließend warten."
        )

        show_busy()

        log("Installiere Build... Bitte nichts klicken")

        purge_blocked_addons()
        xbmc.sleep(1000)

        log("Lade Build herunter...")
        if not download_file(BUILD_ZIP_URL, DOWNLOADED_ZIP):
            close_busy()
            xbmcgui.Dialog().ok("Fehler", "Download fehlgeschlagen.")
            return

        extract_build_zip(DOWNLOADED_ZIP)

        log("Initialisiere Addons...")
        mark_restore_pending()

        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(5000)

        enable_all_addons()
        xbmc.sleep(2000)

        log("Deaktiviere Konflikt-Addons...")
        disable_blocked_addons_if_present()
        xbmc.sleep(1000)

        log("Übernehme Quellen...")
        copy_sources_xml()

        log("Räume auf...")
        cleanup_downloaded_zip()
        cleanup_packages()

        close_busy()

        xbmcgui.Dialog().ok(
            "LeoWizard",
            "Installation abgeschlossen.\n\nKodi wird nach Klick auf OK neu gestartet.\n\nBitte die App danach ca. 10 Sekunden nicht öffnen."
        )

        xbmc.sleep(1000)
        xbmc.executebuiltin("RestartApp")

    except Exception as e:
        try:
            close_busy()
        except Exception:
            pass
        log(f"Fehler im Wizard: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Fehler", f"Installation fehlgeschlagen:\n{e}")


if __name__ == "__main__":
    run_wizard()