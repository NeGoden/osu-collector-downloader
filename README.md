# osu-collector-downloader

Скачивание коллекций с [osucollector.com](https://osucollector.com) с зеркал osu!.

## Что делает

- Получает список битмапсетов из коллекции по её ID.
- Скачивает каждый `.osz` с зеркал (catboy.best, nerinyan.moe, chimu.moe).
- Называет файлы по названию битмапсета с osu.ppy.sh.
- Сохраняет в папку `collections/<имя коллекции>/`.

## Использование

```bash
python download.py <ID коллекции>
```

Если ID не указан — скрипт запросит его интерактивно.

## Зависимости

- Python 3
- `requests`

```bash
pip install requests
```
