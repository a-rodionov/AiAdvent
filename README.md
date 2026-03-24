# AiAdvent. Задание #6. Первый агент

Реализуйте простого агента, который:
- принимает запрос пользователя;
- отправляет его в LLM через API;
- получает ответ;
- выводит результат в вашем интерфейсе.

(простой чат, CLI или web, запросы через HTTP-клиент)

Важно:
- агент должен быть отдельной сущностью, а не просто один вызов API;
- логика запроса и ответа должна быть инкапсулирована в агенте.

Результат:
Агент принимает запрос и корректно вызывает LLM через API

Формат:
Видео + Код

# Решение
[Ссылка на видео](https://disk.yandex.ru/i/JIFeA3mVg_dl6Q)

## Сервер                      
python server.py ./server_configs/local.json

## Клиент (в другом терминале)
python client.py --server http://127.0.0.1:8000

Архитектура сервера
- POST /session — создать сессию (тело: {"session_id": "<uuid>"})
- DELETE /session/{id} — удалить сессию
- GET /sessions — список сессий
- GET /session/{id} — детали сессии
- GET /session/{id}/ws — WebSocket для стриминга

Протокол WS: клиент отправляет SendMessageFrame → сервер стримит ChunkFrame-ы → в конце DoneFrame с токенами и stop_reason. Поддерживается CancelFrame для отмены и PingFrame/PongFrame для keepalive.
