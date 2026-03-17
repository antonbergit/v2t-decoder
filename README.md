# Offline ASR service (Debian 12 + Docker)

Сервис для автономной транскрибации аудио на базе `faster-whisper`.

## Почему выбран этот движок

- Работает локально, без внешних API.
- Хорошее качество на русском и английском.
- Подходит для CPU-режима (`int8`) в контейнере Debian 12.
- Можно переключить модель (`small`, `medium`, `large-v3`) через переменные окружения.

## Структура

- `app/main.py` — FastAPI API.
- `app/asr.py` — загрузка и вызов модели.
- `docker-compose.yml` — запуск сервиса.
- `Dockerfile` — контейнер.
- `tests/test_api.py` — API тесты.

## API

### `GET /health`
Проверка состояния сервиса.

### `POST /transcribe`
Форма multipart:
- `audio` — аудиофайл (`audio/*`)
- query param `language` (опционально): `ru`, `en`, ...

Пример ответа:

```json
{
  "language": "ru",
  "duration_sec": 12.34,
  "text": "распознанный текст",
  "segments": [
    {"start": 0.0, "end": 2.1, "text": "..."}
  ]
}
```

## Локальная разработка

1. Подготовить окружение:

```bash
cp .env.example .env
make install
```

2. Запустить тесты:

```bash
make test
```

3. Запустить сервис:

```bash
make run
```

## Docker развертывание (Proxmox VM / Debian 12)

1. Установить Docker + Compose plugin.
2. В каталоге проекта:

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

3. Проверка:

```bash
curl -s http://127.0.0.1:8000/health
```

4. Тест запроса транскрибации:

```bash
curl -X POST "http://127.0.0.1:8000/transcribe?language=ru" \
  -F "audio=@/path/to/sample.wav"
```

## Тюнинг

В `.env`:

- `MODEL_SIZE=small` — баланс скорость/качество.
- `DEVICE=cpu` — для обычного контейнера без GPU.
- `COMPUTE_TYPE=int8` — меньше потребление памяти на CPU.

Для лучшего качества можно `MODEL_SIZE=medium` или `large-v3` (потребуется больше RAM/CPU).
