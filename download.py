#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивание коллекций с osucollector.com с зеркал osu!"""

import os
import sys
import time
import re
import requests

def fetch_title(sid):
    try:
        r = requests.get(f"https://osu.ppy.sh/beatmapsets/{sid}", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        m = re.search(r"<title>(.*?)</title>", r.text)
        if m:
            t = m.group(1).split("|")[0].strip().rstrip("·").strip()
            # убираем управляющие символы
            t = "".join(c for c in t if c.isprintable())
            return t or str(sid)
    except Exception:
        pass
    return str(sid)

MIRRORS = [
    "https://catboy.best/d/{sid}",
    "https://nerinyan.moe/d/{sid}",
    "https://chimu.moe/d/{sid}",
]

API = "https://osucollector.com/api/collections/{cid}"


def fetch_collection(cid):
    r = requests.get(API.format(cid=cid), timeout=30)
    r.raise_for_status()
    return r.json()


def download_set(sid, out_dir):
    for tpl in MIRRORS:
        url = tpl.format(sid=sid)
        try:
            r = requests.get(url, stream=True, timeout=60,
                             headers={"User-Agent": "osu-collector-dl/1.0"})
            if r.status_code != 200:
                continue
            # попробуем взять имя из заголовка Content-Disposition
            fname = f"{sid}.osz"
            title = fetch_title(sid)
            # очистка имени файла
            safe = re.sub(r'[\\\\/:*?"<>|]', "", title).strip()
            if safe:
                fname = f"{safe}.osz"
            path = os.path.join(out_dir, fname)
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(path) < 1000:
                os.remove(path)
                continue
            return True
        except Exception:
            continue
    return False


def main():
    if len(sys.argv) > 1:
        cid = sys.argv[1].strip()
    else:
        try:
            cid = input("ID коллекции с osucollector.com: ").strip()
        except EOFError:
            print("Укажи ID аргументом: python download.py <ID>")
            sys.exit(1)

    print("Получаю данные коллекции...")
    data = fetch_collection(cid)
    name = data.get("name", cid)
    sets = data.get("beatmapsets", [])
    ids = [s["id"] for s in sets]
    print(f"Коллекция: {name} | битмапсетов: {len(ids)}")

    out_dir = os.path.join(os.getcwd(), "collections", name)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Сохраняю в: {out_dir}")

    ok = 0
    for i, sid in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {sid} ...", end=" ", flush=True)
        if download_set(sid, out_dir):
            ok += 1
            print("OK")
        else:
            print("FAIL")
        time.sleep(0.3)

    print(f"\nГотово: {ok}/{len(ids)}")
    input("Нажми Enter для выхода...")


if __name__ == "__main__":
    main()
