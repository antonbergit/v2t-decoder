# v2t-decoder

Локальный пайплайн транскрибации диалога из видео звонков (`.mkv` / `.mp4`) с раздельной обработкой каналов и сборкой общего таймлайна в TXT/SRT.

## Итог проекта (v0.1.0)

Проект доведён до рабочего релизного baseline для целевого окружения:

- ✅ Phase 1: MVP pipeline (`main.py` + модули в `src/`)
- ✅ Phase 2: DEMO-стабилизация (`prompt/beam/vad`, фиксированная стратегия каналов)
- ✅ Phase 3: PRODUCTION chunking (фрагментация по времени + merge с global offset)
- ✅ Phase 4: Native deployment (без Docker, подтверждён рабочим запуском)

Релизный тег: **`v0.1.0`**

---

## Что умеет

- Прямой вход: `.mkv`, `.mp4`
- Локальная ASR: `faster-whisper`
- Режимы:
  - `demo` — обработка первых N секунд
  - `production` — обработка по временным чанкам
- Выходные файлы:
  - `dialog_timeline.txt`
  - `dialog_timeline.srt`
  - `processing.log.json` (машиночитаемый лог)

---

## Архитектура

- `main.py` — оркестрация пайплайна
- `src/config_loader.py` — загрузка YAML-конфига
- `src/ffmpeg_handler.py` — probe/extract через `ffmpeg`/`ffprobe`
- `src/whisper_handler.py` — обёртка над `faster-whisper`
- `src/dialog_builder.py` — merge сегментов S1/S2 в единый таймлайн
- `src/logger.py` — JSON stage logging
- `src/errors.py` — типизированные ошибки

---

## Быстрый старт (native)

### 1) Установить системные зависимости

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3 python3-venv python3-pip
```

### 2) Подготовить окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Запуск

```bash
./scripts/run_v2t.sh config.yaml
```

или

```bash
python3 main.py --config config.yaml
```

---

## Конфигурация

Основной файл: `config.yaml`

Ключевые параметры:

- `video_file` — путь к входному видео
- `mode` — `demo` / `production`
- `fragment_size_min` — размер production-чанка в минутах
- `max_video_duration_sec` — лимит длины обработки
- `whisper_model`, `device`, `language`, `initial_prompt`, `beam_size`, `vad_filter`
- `preferred_stream_index`, `s1_channel`, `s2_channel`
- `enable_channel_prescan` (опционально)

---

## Документация

- [doc/00.STATUS.MD](doc/00.STATUS.MD) — актуальный статус
- [doc/03.IMPLEMENTATION.MD](doc/03.IMPLEMENTATION.MD) — ход реализации по фазам
- [doc/04.TESTING.MD](doc/04.TESTING.MD) — результаты тестов
- [doc/05.DEPLOYMENT.MD](doc/05.DEPLOYMENT.MD) — deployment в целевом окружении
- [doc/06.RELEASE_NOTES.MD](doc/06.RELEASE_NOTES.MD) — релизные заметки `v0.1.0`

---

## Важно про Docker

Для текущего целевого окружения релизный путь — **native deployment**.

Docker-наработки сохранены отдельно в ветке:

- `phase4-docker-poc`

---

## Текущий статус

Проект готов к рабочему использованию в целевом окружении (native path) и зафиксирован тегом `v0.1.0`.
