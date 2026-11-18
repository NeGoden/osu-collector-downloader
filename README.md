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
- Скачивает каждый `.osz` с зеркал (beatconnect.io, osu.direct, dl.sayobot.cn, catboy.best, nerinyan).
- **Проверяет каждый файл**: это должен быть настоящий ZIP с `.osu` внутри. HTML-страницы и заглушки зеркал отбрасываются и качаются с другого зеркала, поэтому битых `.osz`, которые osu! не открывает, больше не будет.
- Имя файла берётся из ответа зеркала (`<id> Артист - Название.osz`).
- Сохраняет в папку `collections/<имя коллекции>/`.
- Пропускает уже скачанные целые файлы, поэтому повторный запуск продолжает загрузку, а не начинает заново.

## Если файлы уже битые

Раньше скрипт сохранял HTML-страницу NeriNyan вместо файла (ровно 2040 байт). Такие файлы osu! не читает.

Перекачать коллекцию и удалить мусор:

```bash
python download.py <ID> --clean
```

`--clean` удаляет из папки коллекции все `.osz`, которые не являются архивами.

## Запуск из исходников

Нужен Python 3 и библиотека `requests`:

```bash
pip install requests
python download.py <ID коллекции>
```

Если ID не указан — скрипт запросит его интерактивно. Можно вставить и полную ссылку на коллекцию —
ID из неё скрипт вытащит сам.

## Сборка .exe

```bash
pip install pyinstaller requests
pyinstaller --onefile --console --name osu-collector-downloader download.py
```
