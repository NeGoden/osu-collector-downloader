#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивание коллекций с osucollector.com с зеркал osu!"""

import os
import re
import sys
import time
import zipfile
from email.message import Message

import requests

API = "https://osucollector.com/api/collections/{cid}"

# Зеркала в порядке надёжности: {sid} -> id битмапсета.
# Порядок проверен 18.11.2026: catboy/chimu/nerinyan из РФ отдают 403/404/HTML.
MIRRORS = [
    "https://beatconnect.io/b/{sid}/",
    "https://osu.direct/api/d/{sid}",
    "https://dl.sayobot.cn/beatmaps/download/novideo/{sid}",
    "https://catboy.best/d/{sid}",
    "https://api.nerinyan.moe/d/{sid}",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


def fetch_collection(cid):
    r = requests.get(API.format(cid=cid), timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def filename_from_headers(resp, sid):
    """Имя файла из Content-Disposition (там уже есть «id артист - название.osz»)."""
    cd = resp.headers.get("Content-Disposition")
    if cd:
        msg = Message()
        msg["Content-Disposition"] = cd
        name = msg.get_filename()
        if name:
            return name
    return f"{sid}.osz"


def safe_filename(name, sid):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "", name).replace("\x00", "").strip().strip(".")
    if not name.lower().endswith(".osz"):
        name += ".osz"
    stem = name[:-4].strip()
    if not stem:
        stem = str(sid)
    if len(stem) > 170:
        stem = stem[:170].rstrip(" .")
    return stem + ".osz"


def is_valid_osz(path, deep=True):
    """Настоящий ли это .osz: ZIP и внутри есть хотя бы один .osu."""
    try:
        if os.path.getsize(path) < 1024:
            return False
        with open(path, "rb") as f:
            if f.read(2) != b"PK":
                return False
        if not deep:
            return True
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if not any(n.lower().endswith(".osu") for n in names):
                return False
            return z.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def existing_sets(out_dir):
    """id битмапсетов, которые уже лежат в папке и при этом целые."""
    done = set()
    try:
        names = os.listdir(out_dir)
    except OSError:
        return done
    for name in names:
        if not name.lower().endswith(".osz"):
            continue
        m = re.match(r"^(\d+)", name)
        if m and is_valid_osz(os.path.join(out_dir, name), deep=False):
            done.add(int(m.group(1)))
    return done


def remove_broken(out_dir):
    """Удаляет .osz, которые на самом деле не архивы (HTML-заглушки зеркал)."""
    removed = 0
    try:
        names = os.listdir(out_dir)
    except OSError:
        return 0
    for name in names:
        if not name.lower().endswith(".osz"):
            continue
        path = os.path.join(out_dir, name)
        if not is_valid_osz(path, deep=False):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed


def download_set(sid, out_dir):
    """Возвращает (ok, имя файла)."""
    for tpl in MIRRORS:
        url = tpl.format(sid=sid)
        tmp = None
        try:
            with requests.get(url, stream=True, timeout=(15, 60),
                              headers=HEADERS, allow_redirects=True) as r:
                if r.status_code != 200:
                    continue
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "html" in ctype or "json" in ctype:
                    continue  # страница ошибки / заглушка вместо файла
                name = safe_filename(filename_from_headers(r, sid), sid)
                final = os.path.join(out_dir, name)
                tmp = final + ".part"
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                if size < 1024 or not is_valid_osz(tmp):
                    continue
                os.replace(tmp, final)
                tmp = None
                return True, name
        except Exception:
            continue
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return False, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    clean = "--clean" in sys.argv[1:]
    if args:
        raw = args[0].strip()
    else:
        try:
            raw = input("ID коллекции с osucollector.com: ").strip()
        except EOFError:
            print("Укажи ID аргументом: python download.py <ID>")
            sys.exit(1)

    m = re.search(r"(\d+)", raw)
    if not m:
        print("Не понял ID коллекции.")
        sys.exit(1)
    cid = m.group(1)

    print("Получаю данные коллекции...")
    data = fetch_collection(cid)
    name = data.get("name", cid)
    sets = data.get("beatmapsets", [])
    ids = [s["id"] for s in sets]
    print(f"Коллекция: {name} | битмапсетов: {len(ids)}")

    out_dir = os.path.join(os.getcwd(), "collections", name)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Сохраняю в: {out_dir}")

    if clean:
        n = remove_broken(out_dir)
        if n:
            print(f"Удалено битых .osz: {n}")

    done = existing_sets(out_dir)
    if done:
        print(f"Уже скачано (годных): {len(done)}")

    ok = 0
    skipped = 0
    failed = []
    for i, sid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {sid} ...", end=" ", flush=True)
        if sid in done:
            skipped += 1
            print("уже есть")
            continue
        success, fname = download_set(sid, out_dir)
        if success:
            ok += 1
            print(f"OK  {fname}")
        else:
            failed.append(sid)
            print("FAIL (нет на зеркалах)")
        time.sleep(0.2)

    print(f"\nГотово: скачано {ok}, было {skipped}, ошибок {len(failed)} из {len(ids)}")
    if failed:
        print("Не удалось: " + ", ".join(str(x) for x in failed))
        with open(os.path.join(out_dir, "_failed.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(str(x) for x in failed) + "\n")

    input("Нажми Enter для выхода...")


if __name__ == "__main__":
    main()
