# osu-collector-downloader

Скачивание коллекций с [osucollector.com](https://osucollector.com) с зеркал osu!.

## Скачать

Готовый файл для Windows (Python не нужен):

**[⬇ osu-collector-downloader.exe](https://github.com/NeGoden/osu-collector-downloader/releases/latest/download/osu-collector-downloader.exe)**

## Как пользоваться

1. Скачайте `osu-collector-downloader.exe` и запустите.
2. Введите ID коллекции с osucollector.com.
3. Дождитесь окончания загрузки.
4. Карты сохранятся в папку `collections` рядом с `.exe`.

> Windows SmartScreen может предупредить, что файл без цифровой подписи. Нажмите «Подробнее» → «Выполнить всё равно».

## Что делает

- Получает список битмапсетов из коллекции по её ID.
- Скачивает каждый `.osz` с зеркал (catboy.best, nerinyan.moe, chimu.moe).
- Называет файлы по названию битмапсета с osu.ppy.sh.
- Сохраняет в папку `collections/<имя коллекции>/`.

## Запуск из исходников

Нужен Python 3 и библиотека `requests`:

```bash
pip install requests
python download.py <ID коллекции>
```

Если ID не указан — скрипт запросит его интерактивно.

## Сборка .exe

```bash
pip install pyinstaller requests
pyinstaller --onefile --console --name osu-collector-downloader download.py
```
