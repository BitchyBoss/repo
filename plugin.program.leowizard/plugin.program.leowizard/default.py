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
    payload = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params is not None:
        payload["params"] = params
    return json.loads(xbmc.executeJSONRPC(json.dumps(payload)))


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


# 🔽 DOWNLOAD MIT EIGENEM PROGRESS (bleibt wie gehabt)
def download_file(url, dest_path):
    ensure_dir(os.path.dirname(dest_path))

    dialog = xbmcgui.DialogProgress()
    dialog.create("LeoWizard", "Lade Build herunter...")

    try:
        with urllib.request.urlopen(url) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0

            with open(dest_path, "wb") as out_file:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)

                    if total > 0:
                        percent = int(downloaded * 100 / total)
                        dialog.update(percent, f"{percent}% heruntergeladen")
                    else:
                        dialog.update(0, f"{downloaded // 1024} KB")

                    if dialog.iscanceled():
                        raise Exception("Abgebrochen")

        dialog.close()
        return True

    except Exception as e:
        dialog.close()
        log(f"Download Fehler: {e}", xbmc.LOGERROR)
        return False


# 🔽 EXTRACT (ohne extra progress → wir steuern außen)
def extract_build_zip(zip_path):
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        for member in zip_ref.namelist():

            if member.startswith("addons/"):
                rel = member.replace("addons/", "", 1)
                target = os.path.join(KODI_HOME, "addons", rel)

            elif member.startswith("addon_data/") or member.startswith("addondata/"):
                rel = member.replace("addon_data/", "", 1).replace("addondata/", "", 1)
                target = os.path.join(KODI_USERDATA, "addon_data", rel)

            else:
                continue

            if member.endswith("/"):
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zip_ref.open(member) as s, open(target, "wb") as t:
                    shutil.copyfileobj(s, t)


def addon_exists(addon_id):
    result = jsonrpc("Addons.GetAddons", {"properties": ["enabled"]})
    return any(a.get("addonid") == addon_id for a in result.get("result", {}).get("addons", []))


def disable_addon(addon_id):
    jsonrpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": False})


def remove_addon_files(addon_id):
    shutil.rmtree(os.path.join(KODI_HOME, "addons", addon_id), ignore_errors=True)
    shutil.rmtree(os.path.join(KODI_USERDATA, "addon_data", addon_id), ignore_errors=True)


def purge_blocked_addons():
    for addon_id in BLOCKED_ADDONS:
        if addon_exists(addon_id):
            disable_addon(addon_id)
            xbmc.sleep(300)
            remove_addon_files(addon_id)


def enable_all_addons():
    result = jsonrpc("Addons.GetAddons", {"enabled": False})
    for addon in result.get("result", {}).get("addons", []):
        jsonrpc("Addons.SetAddonEnabled", {"addonid": addon["addonid"], "enabled": True})


def copy_sources_xml():
    if os.path.exists(SRC_SOURCES):
        shutil.copyfile(SRC_SOURCES, DEST_SOURCES)


def cleanup():
    try:
        if os.path.exists(DOWNLOADED_ZIP):
            os.remove(DOWNLOADED_ZIP)
        shutil.rmtree(os.path.join(KODI_HOME, "addons", "packages"), ignore_errors=True)
    except:
        pass


def mark_restore_pending():
    ADDON.setSettingBool(SETTING_RESTORE_PENDING, True)


# 🚀 HAUPTABLAUF MIT PROGRESS
def run_wizard():
    progress = xbmcgui.DialogProgress()
    progress.create("LeoWizard", "Installation startet...")

    # 1
    progress.update(5, "Bereinige Addons...")
    purge_blocked_addons()

    # 2
    progress.update(15, "Lade Build...")
    if not download_file(BUILD_ZIP_URL, DOWNLOADED_ZIP):
        progress.close()
        xbmcgui.Dialog().ok("Fehler", "Download fehlgeschlagen.")
        return

    # 3
    progress.update(40, "Entpacke Build...")
    extract_build_zip(DOWNLOADED_ZIP)

    # 4
    progress.update(55, "Initialisiere Addons...")
    mark_restore_pending()
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(5000)

    # 5
    progress.update(70, "Aktiviere Addons...")
    enable_all_addons()
    xbmc.sleep(2000)

    # 6
    progress.update(80, "Entferne unerwünschte Addons...")
    disable_blocked_addons_if_present()
    xbmc.sleep(1000)

    # 7
    progress.update(90, "Übernehme Einstellungen...")
    copy_sources_xml()

    # 8
    progress.update(95, "Cleanup...")
    cleanup()

    progress.update(100, "Fertig!")
    xbmc.sleep(1000)
    progress.close()

    xbmcgui.Dialog().ok(
        "LeoWizard",
        "Installation abgeschlossen.\n\nKodi wird jetzt neu gestartet.\nBitte 10 Sekunden warten bevor du Kodi wieder öffnest!"
    )

    xbmc.sleep(1000)
    xbmc.executebuiltin("RestartApp")


if __name__ == "__main__":
    run_wizard()