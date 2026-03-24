# AiAdvent

Решения заданий находятся в git ветках "task_N".

# Сервер                      
python server.py ./server_configs/local.json

# Клиент (в другом терминале)
python client.py --server http://127.0.0.1:8000

Архитектура сервера
- POST /session — создать сессию (тело: {"session_id": "<uuid>"})
- DELETE /session/{id} — удалить сессию
- GET /sessions — список сессий
- GET /session/{id} — детали сессии
- GET /session/{id}/ws — WebSocket для стриминга

Протокол WS: клиент отправляет SendMessageFrame → сервер стримит ChunkFrame-ы → в конце DoneFrame с токенами и stop_reason. Поддерживается CancelFrame для отмены и PingFrame/PongFrame для keepalive.
