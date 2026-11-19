#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивание коллекций с osucollector.com с зеркал osu!"""

import os
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from urllib.parse import unquote

import requests

API = "https://osucollector.com/api/collections/{cid}"

# Кандидаты-зеркала. Скорость каждого замеряется при запуске (и обновляется
# по ходу скачивания), файлы качаются с самого быстрого из доступных.
MIRRORS = [
    ("beatconnect", "https://beatconnect.io/b/{sid}/"),
    ("osu.direct", "https://osu.direct/api/d/{sid}"),
    ("sayobot", "https://dl.sayobot.cn/beatmaps/download/novideo/{sid}"),
    ("sayobot-txy", "https://txy1.sayobot.cn/beatmaps/download/novideo/{sid}"),
    ("catboy", "https://catboy.best/d/{sid}"),
    ("nerinyan", "https://api.nerinyan.moe/d/{sid}"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

# Замер: сколько байт и секунд максимум тратить на одно зеркало.
PROBE_BYTES = 3 * 1024 * 1024
PROBE_SECONDS = 6.0

_tls = threading.local()


def _session():
    """Одно соединение на поток: keep-alive экономит TLS-рукопожатие на каждом файле."""
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _tls.session = s
    return s


def fetch_collection(cid):
    r = _session().get(API.format(cid=cid), timeout=30)
    r.raise_for_status()
    return r.json()


def clean_name(name):
    """Чинит имя из заголовка: %20 -> пробел и UTF-8, принятый за latin-1."""
    name = unquote(name)
    try:
        name = name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return name


def filename_from_headers(resp, sid):
    """Имя файла из Content-Disposition (там уже есть «id артист - название.osz»)."""
    cd = resp.headers.get("Content-Disposition")
    if cd:
        msg = Message()
        msg["Content-Disposition"] = cd
        name = msg.get_filename()
        if name:
            return clean_name(name)
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


def fix_broken_names(out_dir):
    """Переименовывает уже скачанные файлы вида «123%20Artist%20-%20Title.osz»."""
    renamed = 0
    try:
        names = os.listdir(out_dir)
    except OSError:
        return 0
    for name in names:
        if not name.lower().endswith(".osz"):
            continue
        fixed = safe_filename(clean_name(name), "")
        if fixed == name:
            continue
        src = os.path.join(out_dir, name)
        dst = os.path.join(out_dir, fixed)
        if os.path.exists(dst):
            continue
        try:
            os.replace(src, dst)
            renamed += 1
        except OSError:
            pass
    return renamed


def _open_stream(url, timeout=(8, 45)):
    """Открывает поток .osz или возвращает None, если зеркало отдало не файл."""
    r = _session().get(url, stream=True, timeout=timeout, allow_redirects=True)
    if r.status_code != 200:
        r.close()
        return None
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "html" in ctype or "json" in ctype:
        r.close()
        return None
    return r


def measure_mirror(tpl, sids):
    """Скорость зеркала в МБ/с по первым битмапсетам. None — не работает."""
    best = None
    for sid in sids:
        url = tpl.format(sid=sid)
        t0 = time.perf_counter()
        got = 0
        try:
            r = _open_stream(url, timeout=(8, 12))
            if r is None:
                continue
            with r:
                for chunk in r.iter_content(65536):
                    if not chunk:
                        continue
                    got += len(chunk)
                    if got >= PROBE_BYTES or time.perf_counter() - t0 > PROBE_SECONDS:
                        break
        except Exception:
            continue
        dt = time.perf_counter() - t0
        if got >= 65536 and dt > 0:
            speed = (got / dt) / 1048576
            best = speed if best is None else max(best, speed)
            if got >= PROBE_BYTES:
                break
    return best


def measure_all(sids):
    """Замеряет все зеркала параллельно: {имя: МБ/с или None}."""
    result = {}
    with ThreadPoolExecutor(max_workers=len(MIRRORS)) as ex:
        futures = {
            ex.submit(measure_mirror, tpl, sids): name
            for name, tpl in MIRRORS
        }
        for fut in futures:
            name = futures[fut]
            try:
                result[name] = fut.result()
            except Exception:
                result[name] = None
    return result


def rank_mirrors(speeds):
    """Список (имя, шаблон) от быстрого к медленному; нерабочие — в конце."""
    tpls = dict(MIRRORS)
    order = sorted(
        MIRRORS,
        key=lambda m: (speeds.get(m[0]) is None, -(speeds.get(m[0]) or 0)),
    )
    return [(name, tpls[name]) for name, _ in order]


def show_speeds(speeds):
    rows = sorted(
        ((v, n) for n, v in speeds.items() if v is not None),
        reverse=True,
    )
    for speed, name in rows:
        print(f"  {name:<14} {speed:6.2f} МБ/с")
    dead = [n for n, v in speeds.items() if v is None]
    if dead:
        print(f"  не отвечают: {', '.join(dead)}")


def download_set(sid, out_dir, order, speeds, fails):
    """Качает сет с зеркал по порядку. Возвращает (ok, имя файла, скорость)."""
    for name, tpl in list(order):
        url = tpl.format(sid=sid)
        tmp = None
        t0 = time.perf_counter()
        try:
            r = _open_stream(url)
            if r is None:
                # Зеркало не отдало файл. Один сбой — не повод его выкидывать,
                # но после нескольких подряд отправляем в конец списка.
                fails[name] = fails.get(name, 0) + 1
                if fails[name] >= 3:
                    speeds[name] = None
                    order[:] = rank_mirrors(speeds)
                continue
            with r:
                fname = safe_filename(filename_from_headers(r, sid), sid)
                final = os.path.join(out_dir, fname)
                tmp = final + ".part"
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                dt = max(time.perf_counter() - t0, 0.001)
                speed = (size / dt) / 1048576
                if size < 1024 or not is_valid_osz(tmp):
                    fails[name] = fails.get(name, 0) + 1
                    if fails[name] >= 3:
                        speeds[name] = None
                        order[:] = rank_mirrors(speeds)
                    continue
                os.replace(tmp, final)
                tmp = None
                fails[name] = 0
                speeds[name] = speed  # реальная скорость этого файла
                order[:] = rank_mirrors(speeds)
                return True, fname, speed, name
        except Exception:
            fails[name] = fails.get(name, 0) + 1
            if fails[name] >= 3:
                speeds[name] = None
                order[:] = rank_mirrors(speeds)
            continue
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return False, None, 0.0, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    clean = "--clean" in sys.argv[1:]
    test_only = "--test" in sys.argv[1:]
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

    n = fix_broken_names(out_dir)
    if n:
        print(f"Исправлено имён файлов: {n}")

    if clean:
        n = remove_broken(out_dir)
        if n:
            print(f"Удалено битых .osz: {n}")

    done = existing_sets(out_dir)
    if done:
        print(f"Уже скачано (годных): {len(done)}")

    todo = [sid for sid in ids if sid not in done]
    if test_only:
        print("\nТестирую скорость зеркал...")
        speeds = measure_all(todo[:2] or ids[:2] or [210679])
        show_speeds(speeds)
        return
    if not todo:
        print("Всё уже скачано.")
        input("Нажми Enter для выхода...")
        return

    print("\nТестирую скорость зеркал...")
    speeds = measure_all(todo[:2])
    show_speeds(speeds)
    if all(v is None for v in speeds.values()):
        print("Ни одно зеркало не ответило, пробую всё равно...")
        speeds = {n: None for n, _ in MIRRORS}
    order = rank_mirrors(speeds)
    fails = {}
    print(f"\nКачаю с: {order[0][0]}\n")

    ok = 0
    skipped = len(done)
    failed = []
    for i, sid in enumerate(ids, 1):
        if sid in done:
            continue
        print(f"[{i}/{len(ids)}] {sid} ...", end=" ", flush=True)
        success, fname, speed, used = download_set(sid, out_dir, order, speeds, fails)
        if success:
            ok += 1
            print(f"OK  {speed:5.2f} МБ/с [{used}]  {fname}")
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
