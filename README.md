# AiAdvent. Задание №5. Версии моделей

Выполните один и тот же запрос:

- на слабой модели;
- на средней модели;
- на сильной модели.

(например: из начала, середины и конца списка HuggingFace)

Замерьте:

- время ответа;
- количество токенов;
- стоимость (если модель платная).

Сравните:

- качество ответов;
- скорость;
- ресурсоёмкость.

Результат:
Короткий вывод о различиях между моделями + ссылки.

Формат:
Видео + Код

## Решение

[Ссылка на видео](https://disk.yandex.ru/i/jB_xhDzZjoOl3A)

Всем моделям был отправлен запрос: "Есть микросервисная архитектура: Frontend -> API Gateway (Kong) -> Сервис A (Go, gRPC) -> Сервис B (Python, HTTP). В логах Kong изредка появляются 504 Gateway Timeout, хотя в логах сервисов A и B все запросы успешны и выполняются быстрее 200 мс. Таймауты возникают только в часы пик и только для определённых эндпоинтов, которые требуют передачи больших файлов (до 10 МБ). Перечисли все возможные причины такого поведения и опиши, как проверить каждую гипотезу?"

| Название модели           | Время ответа, с | Кол-во токенов | Стоимость  |
| ------------------------- | --------------- | -------------- | ---------- |
| claude-haiku-4-5-20251001 | 33,21           | 4362           | 0.021062 $ |
| claude-sonnet-4-6         | 122,79          | 7320           | 0.107556 $ |
| claude-opus-4-6           | 135,54          | 7926           | 0.194410 $ |

- claude-haiku-4-5-20251001 предоставил 17 гипотез о причинах описанной проблемы. Для каждой из них указал способ диагностирования и для большинства способ устранения. В конце предоставил приоритезированный план проверки гипотез. Гипотезы весьма разнообразные, включающие множество аспектов, задействованных в задаче компонентов. Большинство из них можно отклонить по условиям задачи.
- claude-sonnet-4-6 удалось лучше локализовать проблему в цепочке вызовов и предоставить 14 более релевантных гипотез, чем claude-haiku-4-5-20251001. Были предоставлены описания гипотез, способ диагностиики и исправления, а также приоритезированный план работ. Присутсвует визуализация схемы с помощью текста.
- claude-opus-4-6 предостаил 15 описаний гипотез. В отличие от предыдущих моделей гипотезы не сгруппированы по причине ошибки, а приведены плоским списком. На мой, взгляд перечень гипотез проигрывает claude-sonnet-4-6. Для части из них неверно указаны способы исправления. Отмечу, что некоторые гипотезы требуют глубоких технических знаний и отсутствовали у предыдущих моделей. Присутсвует визуализация схемы с помощью текста, превосходящая предыдущие модели. Также как и предыдущих моделей помимо описания гипотез, приведены способ диагностиики и исправления, приоритезированный план работ.
- Для решение типовых задач рекомендуется использовать claude-sonnet-4-6. Если требуется решить более сложую задачу, то рекомендуется использовать claude-opus-4-6, сильнее ограничивая контекст решаемой задачи.

<details>
<summary>Ответ claude-haiku-4-5-20251001</summary>
# Анализ 504 Gateway Timeout в Kong при передаче больших файлов

## 1. **Проблемы с таймаутами Kong**

### Гипотеза 1.1: Недостаточный `upstream_connect_timeout`

**Причина:** Kong не успевает установить соединение с Сервисом A в часы пик.

**Проверка:**

```bash
# Текущие настройки Kong
curl http://localhost:8001/services/{service_name} | jq '.connect_timeout'

# Увеличить таймаут подключения (по умолчанию 60000 мс)
curl -X PATCH http://localhost:8001/services/{service_name} \
  -d "connect_timeout=120000"

# Мониторить время подключения
tcpdump -i any -n 'tcp.flags.syn==1' | grep -E '(service_a|service_b)'
```

### Гипотеза 1.2: Недостаточный `upstream_send_timeout`

**Причина:** Kong не успевает отправить весь запрос (10 МБ) за отведённое время.

**Проверка:**

```bash
# Текущее значение (по умолчанию 60000 мс)
curl http://localhost:8001/services/{service_name} | jq '.send_timeout'

# Увеличить
curl -X PATCH http://localhost:8001/services/{service_name} \
  -d "send_timeout=300000"

# Проверить скорость загрузки файла
time curl -X POST http://localhost:8000/upload \
  -F "file=@10mb_file.bin" -w "\nTime: %{time_total}s\n"
```

### Гипотеза 1.3: Недостаточный `upstream_read_timeout`

**Причина:** Kong ждёт ответа от сервиса дольше, чем позволяет таймаут.

**Проверка:**

```bash
# Текущее значение (по умолчанию 60000 мс)
curl http://localhost:8001/services/{service_name} | jq '.read_timeout'

# Увеличить
curl -X PATCH http://localhost:8001/services/{service_name} \
  -d "read_timeout=300000"

# Проверить время обработки на бэкенде
curl -X POST http://localhost:8000/upload \
  -F "file=@10mb_file.bin" \
  -w "Total: %{time_total}s, Connect: %{time_connect}s, Processing: %{time_starttransfer}s\n"
```

---

## 2. **Проблемы с буферизацией**

### Гипотеза 2.1: Недостаточный `client_body_buffer_size` в Kong

**Причина:** Kong не может полностью забуферизировать 10 МБ файл в памяти.

**Проверка:**

```bash
# Проверить текущее значение в nginx.conf Kong
docker exec kong cat /etc/kong/nginx.conf | grep client_body_buffer_size

# Увеличить в kong.conf
client_body_buffer_size 50m;

# Перезагрузить Kong
docker restart kong

# Проверить использование памяти Kong
docker stats kong --no-stream
```

### Гипотеза 2.2: Недостаточный `client_max_body_size`

**Причина:** Kong отклоняет запросы больше лимита.

**Проверка:**

```bash
# Проверить лимит
curl http://localhost:8001/services/{service_name} | jq '.client_body_buffer_size'

# Увеличить в kong.conf
client_max_body_size 50m;

# Проверить ошибку 413 (Payload Too Large)
curl -X POST http://localhost:8000/upload \
  -F "file=@10mb_file.bin" -v 2>&1 | grep -E "(413|Content-Length)"
```

---

## 3. **Проблемы с сетевой пропускной способностью**

### Гипотеза 3.1: Насыщение сетевого канала в часы пик

**Причина:** Множество больших файлов одновременно исчерпывают пропускную способность.

**Проверка:**

```bash
# Мониторить пропускную способность в реальном времени
iftop -i eth0

# Или через nethogs
nethogs -d 1

# Проверить пакеты, потерянные на интерфейсе Kong
ip -s link show | grep -A 3 "RX\|TX"

# Нагрузочное тестирование с большими файлами
ab -n 100 -c 10 -p 10mb_file.bin http://localhost:8000/upload

# Проверить задержки между Kong и Сервисом A
mtr -r -c 100 service_a_host
```

### Гипотеза 3.2: Проблемы с TCP окном (TCP Window Size)

**Причина:** Неоптимальный размер TCP окна замедляет передачу.

**Проверка:**

```bash
# Проверить TCP окно между Kong и Сервисом A
tcpdump -i any -n 'tcp.flags.syn==1' -A | grep -i "win="

# Оптимизировать TCP параметры на Kong
sysctl -w net.ipv4.tcp_window_scaling=1
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728

# Проверить текущие значения
sysctl net.ipv4.tcp_rmem
sysctl net.ipv4.tcp_wmem
```

---

## 4. **Проблемы с Сервисом A (Go, gRPC)**

### Гипотеза 4.1: Недостаточное количество воркеров/горутин

**Причина:** Сервис A не может обработать все запросы одновременно в часы пик.

**Проверка:**

```bash
# Проверить количество активных горутин
curl http://localhost:6060/debug/pprof/goroutine?debug=1

# Проверить метрики через Prometheus
curl http://localhost:9090/api/v1/query?query=go_goroutines

# Увеличить пул воркеров в коде Go
// Текущее значение
maxConcurrentStreams := 100

// Увеличить
maxConcurrentStreams := 1000

# Перезагрузить сервис и проверить
docker logs service_a | grep "goroutine"
```

### Гипотеза 4.2: Проблемы с gRPC буферизацией

**Причина:** gRPC имеет ограничения на размер сообщений.

**Проверка:**

```bash
# Проверить MaxReceiveMessageSize в коде Go
grpc.WithDefaultCallOptions(
    grpc.MaxCallRecvMsgSize(50 * 1024 * 1024), // 50 МБ
)

# Проверить логи gRPC
GRPC_GO_LOG_VERBOSITY_LEVEL=99 GRPC_GO_LOG_SEVERITY_LEVEL=info \
  ./service_a

# Проверить размер сообщения в gRPC
grpcurl -plaintext list service_a:50051
```

---

## 5. **Проблемы с Сервисом B (Python, HTTP)**

### Гипотеза 5.1: Недостаточное количество воркеров в Python

**Причина:** WSGI сервер (Gunicorn/uWSGI) не может обработать все запросы.

**Проверка:**

```bash
# Проверить текущее количество воркеров
ps aux | grep gunicorn | wc -l

# Увеличить в конфиге Gunicorn
gunicorn --workers 16 --worker-class gevent app:app

# Проверить очередь запросов
curl http://localhost:8002/metrics | grep queue

# Нагрузочное тестирование
locust -f locustfile.py --host=http://localhost:8002 -u 100 -r 10
```

### Гипотеза 5.2: Проблемы с обработкой больших файлов в Python

**Причина:** Python медленнее обрабатывает большие потоки данных.

**Проверка:**

```python
# Проверить использование памяти при обработке файла
import tracemalloc
tracemalloc.start()

# Обработать файл
with open('10mb_file.bin', 'rb') as f:
    data = f.read()

current, peak = tracemalloc.get_traced_memory()
print(f"Peak memory: {peak / 1024 / 1024:.1f} МБ")

# Оптимизировать: использовать streaming вместо загрузки в память
@app.route('/upload', methods=['POST'])
def upload():
    chunk_size = 1024 * 1024  # 1 МБ chunks
    while True:
        chunk = request.stream.read(chunk_size)
        if not chunk:
            break
        # Обработать chunk
```

---

## 6. **Проблемы с Kong -> Сервис A (gRPC)**

### Гипотеза 6.1: Проблемы с gRPC плагином Kong

**Причина:** Kong gRPC плагин имеет баги при передаче больших файлов.

**Проверка:**

```bash
# Проверить версию Kong и плагина
kong version
curl http://localhost:8001/plugins | jq '.data[] | select(.name=="grpc-gateway")'

# Обновить Kong и плагины
docker pull kong:latest
docker-compose up -d

# Проверить логи Kong на ошибки gRPC
docker logs kong | grep -i "grpc\|error"

# Альтернатива: использовать HTTP/2 вместо gRPC
curl -I --http2 http://localhost:8000/api
```

### Гипотеза 6.2: Проблемы с HTTP/2 мультиплексированием

**Причина:** Kong переиспользует одно соединение для множества запросов.

**Проверка:**

```bash
# Проверить, использует ли Kong HTTP/2
curl -I --http2 http://localhost:8000/api -v 2>&1 | grep "HTTP/2"

# Отключить HTTP/2 multiplexing в Kong
curl -X PATCH http://localhost:8001/services/{service_name} \
  -d "protocol=http"

# Проверить количество соединений
netstat -an | grep ESTABLISHED | wc -l
```

---

## 7. **Проблемы с диском и I/O**

### Гипотеза 7.1: Медленный диск на сервисах

**Причина:** Диск не успевает записать/прочитать 10 МБ файл.

**Проверка:**

```bash
# Проверить I/O задержки
iostat -x 1 10

# Проверить использование диска
df -h
du -sh /var/log /tmp

# Нагрузочное тестирование диска
fio --name=randread --ioengine=libaio --iodepth=16 \
    --rw=randread --bs=4k --direct=1 --size=1G --numjobs=4

# Проверить скорость записи на диск
dd if=/dev/zero of=/tmp/test bs=1M count=1000 oflag=direct
```

### Гипотеза 7.2: Недостаточно файловых дескрипторов

**Причина:** ОС не может открыть новые соединения.

**Проверка:**

```bash
# Проверить лимит на процесс
ulimit -n

# Проверить использование дескрипторов Kong
lsof -p $(pgrep -f kong) | wc -l

# Увеличить лимит
ulimit -n 65536

# Постоянно в /etc/security/limits.conf
kong soft nofile 65536
kong hard nofile 65536
```

---

## 8. **Проблемы с DNS и разрешением имён**

### Гипотеза 8.1: Медленное разрешение DNS

**Причина:** Kong медленно разрешает имя Сервиса A в часы пик.

**Проверка:**

```bash
# Проверить время разрешения DNS
time nslookup service_a

# Проверить кэш DNS в Kong
curl http://localhost:8001/upstreams/{upstream_name} | jq '.dns_order'

# Увеличить TTL кэша DNS
curl -X PATCH http://localhost:8001/upstreams/{upstream_name} \
  -d "dns_order=LAST,A,AAAA" \
  -d "dns_ttl=300"

# Проверить логи DNS
systemctl status systemd-resolved
journalctl -u systemd-resolved -f
```

---

## 9. **Проблемы с мониторингом и логированием**

### Гипотеза 9.1: Логирование замедляет обработку

**Причина:** Синхронное логирование в часы пик замедляет ответ.

**Проверка:**

```bash
# Проверить уровень логирования Kong
curl http://localhost:8001/config | jq '.log_level'

# Отключить подробное логирование
curl -X PATCH http://localhost:8001/config \
  -d "log_level=warn"

# Проверить размер лог-файлов
du -sh /var/log/kong/

# Настроить ротацию логов
logrotate -f /etc/logrotate.d/kong
```

---

## 10. **Комплексная диагностика**

### Скрипт для сбора всех метрик:

```bash
#!/bin/bash

echo "=== Kong Metrics ==="
curl -s http://localhost:8001/status | jq .

echo "=== Service A Metrics ==="
curl -s http://service_a:9090/metrics | grep -E "grpc_|go_goroutines"

echo "=== Service B Metrics ==="
curl -s http://service_b:8002/metrics | grep -E "http_|process_"

echo "=== Network Stats ==="
netstat -s | grep -E "segments|retransmitted"

echo "=== Disk I/O ==="
iostat -x 1 1

echo "=== Memory Usage ==="
free -h

echo "=== Kong Connections ==="
netstat -an | grep ESTABLISHED | wc -l
```

---

## **Рекомендуемый порядок проверки:**

1. **Сначала:** Таймауты Kong (1.1-1.3)
2. **Затем:** Буферизация (2.1-2.2)
3. **Параллельно:** Мониторить сеть (3.1-3.2)
4. **Проверить:** Воркеры сервисов (4.1, 5.1)
5. **Если не помогло:** Диск и I/O (7.1-7.2)

Какой из пунктов вам нужно разобрать подробнее?

</details>

<details>
<summary>Ответ claude-sonnet-4-6</summary>
# Диагностика 504 Gateway Timeout в Kong при передаче больших файлов

## Карта проблемы

```
Frontend → Kong → Service A (gRPC) → Service B (HTTP)
                ↑
         504 здесь, но A и B говорят "всё ок"
         Только часы пик + файлы до 10 МБ
```

Ключевое противоречие: **Kong видит таймаут, сервисы — нет**. Это означает проблема либо в самом Kong, либо в сети между Kong и сервисами, либо в том, что сервисы логируют "успех" до фактической отправки ответа.

---

## Группа 1: Проблемы на уровне Kong

### Гипотеза 1.1: Kong upstream timeout меньше реального времени передачи файла

**Суть:** Kong имеет отдельные таймауты: `connect_timeout`, `write_timeout`, `read_timeout`. При передаче 10 МБ файла `read_timeout` может истекать раньше, чем данные полностью переданы, даже если сервис "ответил" быстро (отправил заголовки, но тело передаётся дольше).

```
Kong read_timeout = 60s
Сервис A: заголовки отправлены за 50ms ✓ (логирует успех)
Тело 10MB передаётся 65s при нагрузке → Kong режет соединение
```

**Проверка:**

```bash
# Смотрим текущие таймауты для upstream в Kong
curl http://localhost:8001/services/service-a | jq '{
  connect_timeout,
  write_timeout,
  read_timeout
}'

# Или через Admin API для конкретного route
curl http://localhost:8001/routes | jq '.data[] | select(.name=="large-file-route")'

# Замеряем реальное время передачи тела ответа (не TTFB!)
curl -w "@curl-format.txt" -o /dev/null -s https://your-api/endpoint/large-file
```

```
# curl-format.txt
time_namelookup:  %{time_namelookup}\n
time_connect:     %{time_connect}\n
time_appconnect:  %{time_appconnect}\n
time_pretransfer: %{time_pretransfer}\n
time_redirect:    %{time_redirect}\n
time_starttransfer: %{time_starttransfer}\n  ← TTFB (сервис логирует здесь)
time_total:       %{time_total}\n            ← полная передача (Kong смотрит сюда)
```

**Фикс:**

```yaml
# Kong Service config
connect_timeout: 5000 # 5s
write_timeout: 120000 # 2min для upload
read_timeout: 120000 # 2min для download больших файлов
```

---

### Гипотеза 1.2: Kong буферизует весь ответ в памяти перед отправкой клиенту

**Суть:** Kong (nginx под капотом) по умолчанию буферизует ответы. При 10 МБ + высокая нагрузка = буферы переполняются, запись на диск, резкое замедление.

**Проверка:**

```bash
# Смотрим nginx-related настройки Kong
# В kong.conf или через переменные окружения
grep -E "proxy_buffer|nginx_proxy" /etc/kong/kong.conf

# Мониторим использование памяти Kong в часы пик
kubectl top pod -l app=kong -n kong --containers

# Проверяем наличие временных файлов (признак disk buffering)
ls -la /tmp/kong* 2>/dev/null
# или внутри контейнера
kubectl exec -it kong-pod -- ls -la /tmp/

# Смотрим nginx worker memory
kubectl exec -it kong-pod -- cat /proc/$(pgrep nginx | head -1)/status | grep VmRSS
```

```nginx
# Добавляем в nginx директивы через Kong custom template
proxy_buffering off;           # отключить буферизацию для стриминга
proxy_max_temp_file_size 0;    # не писать на диск
# или увеличить буферы
proxy_buffers 16 1m;
proxy_buffer_size 2m;
```

**Проверка через Kong:**

```bash
# Через nginx directives в kong.conf
nginx_proxy_proxy_buffering=off
nginx_proxy_proxy_max_temp_file_size=0
```

---

### Гипотеза 1.3: Проблема с connection pool к upstream

**Суть:** В часы пик все соединения из пула заняты. Новый запрос ждёт свободного соединения, и это ожидание засчитывается в таймаут Kong, хотя сам сервис обрабатывает запрос быстро.

```
Kong connection pool: 10 connections
Часы пик: все 10 заняты передачей больших файлов
Новый запрос: ждёт 60s → 504
Сервис A: получает запрос, обрабатывает за 150ms → логирует успех
```

**Проверка:**

```bash
# Метрики Kong через Prometheus
curl http://localhost:8001/metrics | grep -E "kong_upstream_target|connections"

# Смотрим активные соединения к upstream
kubectl exec -it kong-pod -- netstat -an | grep :50051 | awk '{print $6}' | sort | uniq -c

# Включаем детальное логирование Kong
# В kong.conf
log_level = debug

# Смотрим время ожидания соединения в логах
# Ищем "upstream" + время до первого байта
```

```lua
-- Kong plugin для измерения времени ожидания пула
local function measure_pool_wait(conf)
  local start = ngx.now()
  -- после получения соединения
  local wait_time = ngx.now() - start
  kong.log.warn("Pool wait time: " .. wait_time .. "s")
end
```

---

## Группа 2: Проблемы на уровне gRPC (Kong → Service A)

### Гипотеза 2.1: gRPC message size limits

**Суть:** gRPC имеет лимит на размер сообщения (по умолчанию **4 МБ**). При передаче 10 МБ файла через gRPC запрос молча отклоняется или зависает на стороне Kong/транспорта, но сервис A может не получить запрос вовсе или получить его частично.

```
Kong → gRPC → Service A
       ↑
  max_recv_msg_size = 4MB
  10MB файл → hang/error на уровне транспорта
  Service A не получает запрос → не логирует ничего
  Kong ждёт ответа → 504
```

**Проверка:**

```bash
# Проверяем размер файлов в "успешных" запросах сервиса A
# Если все успешные < 4MB, а таймауты при > 4MB — это оно

# Тестируем напрямую gRPC без Kong
grpcurl -d @ -plaintext service-a:50051 FileService/Upload < test_10mb.bin

# Смотрим настройки в коде Service A
grep -r "MaxRecvMsgSize\|MaxSendMsgSize\|max_message_length" ./service-a/

# Проверяем Kong grpc-gateway plugin настройки
curl http://localhost:8001/plugins | jq '.data[] | select(.name=="grpc-gateway")'
```

```go
// Service A — правильная настройка
grpc.NewServer(
    grpc.MaxRecvMsgSize(50 * 1024 * 1024),  // 50MB
    grpc.MaxSendMsgSize(50 * 1024 * 1024),
)

// Клиент в Kong или при прямом вызове
conn, err := grpc.Dial(addr,
    grpc.WithDefaultCallOptions(
        grpc.MaxCallRecvMsgSize(50 * 1024 * 1024),
    ),
)
```

---

### Гипотеза 2.2: gRPC keepalive и idle connection timeout

**Суть:** При высокой нагрузке gRPC соединения могут закрываться по keepalive timeout. Kong пытается использовать "мёртвое" соединение, тратит время на обнаружение разрыва, переподключение — всё это входит в таймаут.

**Проверка:**

```bash
# Смотрим gRPC connection events
kubectl logs service-a-pod | grep -E "keepalive|connection|GOAWAY"

# Wireshark/tcpdump между Kong и Service A
kubectl exec -it kong-pod -- tcpdump -i eth0 -w /tmp/grpc.pcap host service-a-ip and port 50051

# Копируем и анализируем
kubectl cp kong-pod:/tmp/grpc.pcap ./grpc.pcap
wireshark grpc.pcap  # фильтр: grpc || http2
```

```go
// Настройка keepalive в Service A
keepaliveParams := keepalive.ServerParameters{
    MaxConnectionIdle:     15 * time.Second,
    MaxConnectionAge:      30 * time.Second,
    MaxConnectionAgeGrace: 5 * time.Second,
    Time:                  5 * time.Second,
    Timeout:               1 * time.Second,
}

// Клиентские параметры (Kong side или при тестировании)
keepalivePolicy := keepalive.EnforcementPolicy{
    MinTime:             5 * time.Second,
    PermitWithoutStream: true,
}
```

---

### Гипотеза 2.3: HTTP/2 flow control window

**Суть:** gRPC работает поверх HTTP/2. Flow control window по умолчанию 65 КБ. При передаче 10 МБ нужно много window updates. При нагрузке эти обновления задерживаются → передача данных останавливается → таймаут.

**Проверка:**

```bash
# Анализ HTTP/2 фреймов
tcpdump -i any -w capture.pcap port 50051
# В Wireshark: фильтр http2.type == 8 (WINDOW_UPDATE frames)
# Смотрим частоту и размер обновлений

# Метрики Go runtime Service A
curl http://service-a:6060/debug/pprof/goroutine?debug=1 | grep -A5 "grpc"

# Проверяем initial window size
# В коде Service A
grep -r "InitialWindowSize\|InitialConnWindowSize" ./
```

```go
// Увеличиваем window size
grpc.NewServer(
    grpc.InitialWindowSize(1 << 30),      // 1GB per stream
    grpc.InitialConnWindowSize(1 << 30),  // 1GB per connection
)
```

---

## Группа 3: Проблемы на уровне сети

### Гипотеза 3.1: MTU mismatch и фрагментация пакетов

**Суть:** В Kubernetes/облаке часто используется overlay network (VXLAN, Calico, Flannel) с уменьшенным MTU (1450 вместо 1500). Большие файлы = много пакетов = при фрагментации часть теряется → ретрансмиты → таймаут.

**Проверка:**

```bash
# Проверяем MTU на всех интерфейсах
kubectl exec -it kong-pod -- ip link show
kubectl exec -it kong-pod -- cat /sys/class/net/eth0/mtu

kubectl exec -it service-a-pod -- ip link show

# Тест с разными размерами пакетов
kubectl exec -it kong-pod -- ping -M do -s 1400 service-a-ip  # не фрагментировать
kubectl exec -it kong-pod -- ping -M do -s 1450 service-a-ip  # должен упасть если MTU < 1478

# Смотрим потери пакетов и ретрансмиты
kubectl exec -it kong-pod -- netstat -s | grep -E "retransmit|fragment|error"

# Более детально через ss
kubectl exec -it kong-pod -- ss -ti dst service-a-ip | grep -E "retrans|lost"
```

```bash
# Фикс: явно устанавливаем MTU
# В Kubernetes CNI config (например Calico)
# calico-config ConfigMap
"mtu": 1440  # с запасом для VXLAN overhead (50 bytes)
```

---

### Гипотеза 3.2: TCP buffer overflow и backpressure

**Суть:** В часы пик TCP send/receive буферы переполняются. Ядро начинает применять backpressure, соединение "замирает". Сервис уже отправил данные в kernel buffer (считает запрос выполненным), но данные не дошли до Kong.

**Проверка:**

```bash
# Смотрим TCP буферы
sysctl net.core.rmem_max net.core.wmem_max
sysctl net.ipv4.tcp_rmem net.ipv4.tcp_wmem

# Мониторим drops в часы пик
watch -n1 'netstat -s | grep -E "overflow|drop|fail"'

# Детальная статистика по соединению
ss -tm dst service-a-ip
# Смотрим: rcv_space, snd_buf, rcv_buf

# Проверяем очереди
kubectl exec -it kong-pod -- cat /proc/net/sockstat
```

```bash
# Тюнинг TCP буферов
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728
sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"
```

---

### Гипотеза 3.3: DNS resolution timeout под нагрузкой

**Суть:** Kong резолвит upstream по DNS. В часы пик DNS сервер перегружен, резолюция занимает секунды. Это время входит в `connect_timeout` Kong.

**Проверка:**

```bash
# Замеряем DNS время
kubectl exec -it kong-pod -- time nslookup service-a.namespace.svc.cluster.local
kubectl exec -it kong-pod -- dig service-a.namespace.svc.cluster.local | grep "Query time"

# Делаем это многократно в часы пик
for i in {1..100}; do
  kubectl exec -it kong-pod -- dig +stats service-a.svc.cluster.local 2>&1 | grep "Query time"
done

# Смотрим DNS cache в Kong
# Kong использует lua-resty-dns-client
curl http://localhost:8001/ | jq '.configuration.dns_resolver'

# Проверяем CoreDNS метрики
kubectl top pod -n kube-system -l k8s-app=kube-dns
```

```yaml
# Kong DNS настройки
dns_stale_ttl: 4 # использовать stale записи
dns_cache_size: 10000 # увеличить кэш
dns_order: LAST,SRV,A,CNAME # оптимизировать порядок
```

---

## Группа 4: Проблемы логирования (ложная картина)

### Гипотеза 4.1: Сервисы логируют "успех" до завершения передачи

**Суть:** Это критически важная гипотеза. Сервис A логирует завершение запроса в момент **начала отправки ответа** (после `w.WriteHeader(200)` или `stream.Send()`), а не после того, как данные реально переданы клиенту (Kong).

```
Service A timeline:
t=0ms:   получен запрос
t=150ms: данные готовы, начинаем отправку
t=150ms: ← ЗДЕСЬ ЛОГИРУЕТСЯ "успех за 150ms"
t=150ms...8000ms: передача 10MB данных в Kong
t=8000ms: Kong timeout → 504
```

**Проверка:**

```go
// Текущий (проблемный) код Service A — типичная ошибка
func (s *Server) GetFile(ctx context.Context, req *pb.FileRequest) (*pb.FileResponse, error) {
    data := fetchFile(req.Id)  // 150ms
    log.Info("request completed", "duration", time.Since(start))  // ← логируем здесь!
    return &pb.FileResponse{Data: data}, nil  // реальная передача ещё не началась
}

// Правильный подход — измерять до return
func (s *Server) GetFile(ctx context.Context, req *pb.FileRequest) (*pb.FileResponse, error) {
    defer func() {
        log.Info("request fully completed", "duration", time.Since(start))
    }()
    data := fetchFile(req.Id)
    return &pb.FileResponse{Data: data}, nil
}
```

```python
# Service B (Python/HTTP) — аналогичная проблема
# Проблемный вариант
@app.route('/file/<id>')
def get_file(id):
    data = fetch_file(id)
    logger.info(f"Request completed in {time.time() - start:.3f}s")  # ← до отправки!
    return Response(data, mimetype='application/octet-stream')

# Правильный — middleware с измерением после отправки
@app.after_request
def log_response(response):
    # Но даже это не гарантирует измерение времени передачи тела!
    pass

# Для стриминга нужен специальный подход
def generate():
    for chunk in data_chunks:
        yield chunk
    logger.info(f"Stream completed in {time.time() - start:.3f}s")  # ← после передачи
```

**Проверка гипотезы:**

```bash
# Добавляем трассировку с временными метками на каждом этапе
# Используем distributed tracing (Jaeger/Zipkin)

# Смотрим span'ы:
# Kong: request_start → response_end (504 через 60s)
# Service A: request_received → handler_start → handler_end → ?
#                                                              ↑
#                                              нет span'а "data_sent_to_client"

# Если span'ы Service A заканчиваются раньше Kong timeout
# но нет span'а подтверждения получения данных — это оно
```

---

### Гипотеза 4.2: Разные часы на сервисах (clock skew)

**Суть:** Логи Kong и сервисов сравниваются по timestamp. Если часы расходятся, запрос который Kong считает "зависшим" может в логах сервиса выглядеть как выполненный в другое время.

**Проверка:**

```bash
# Проверяем синхронизацию времени
kubectl exec -it kong-pod -- date +%s%N
kubectl exec -it service-a-pod -- date +%s%N
kubectl exec -it service-b-pod -- date +%s%N

# Разница не должна превышать ~100ms
# Если больше — проблема с NTP

# Проверяем NTP статус
kubectl exec -it kong-pod -- chronyc tracking 2>/dev/null || \
kubectl exec -it kong-pod -- ntpq -p 2>/dev/null

# Коррелируем логи с учётом skew
# Берём request_id из Kong лога и ищем его в логах сервисов
grep "request-id-xyz" /var/log/kong/access.log
grep "request-id-xyz" /var/log/service-a/app.log
```

---

## Группа 5: Проблемы инфраструктуры

### Гипотеза 5.1: Load Balancer / Ingress timeout перед Kong

**Суть:** Перед Kong может стоять ещё один балансировщик (AWS ALB, nginx ingress, etc.) со своими таймаутами. 504 в "логах Kong" может быть на самом деле от этого балансировщика.

**Проверка:**

```bash
# Проверяем заголовки ответа — кто именно вернул 504
curl -v https://api.example.com/large-file 2>&1 | grep -E "Server:|Via:|X-Kong|x-amzn"

# Если в ответе нет Kong-специфичных заголовков — 504 не от Kong
# Kong добавляет: X-Kong-Upstream-Latency, X-Kong-Proxy-Latency

# Смотрим реальный источник в заголовках
# Kong: {"server": "kong/3.x.x"}
# ALB: {"server": "awselb/2.0"}

# Проверяем таймауты ALB/NLB
aws elbv2 describe-target-group-attributes \
  --target-group-arn arn:aws:elasticloadbalancing:...
# Смотрим: deregistration_delay, slow_start, stickiness
```

---

### Гипотеза 5.2: Kubernetes resource limits и CPU throttling

**Суть:** В часы пик Kong pod достигает CPU limit → CPU throttling → обработка запросов замедляется → таймауты. При этом сами сервисы A и B работают нормально.

**Проверка:**

```bash
# Смотрим CPU throttling
kubectl exec -it kong-pod -- cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled

# Метрики через kubectl top
kubectl top pod -l app=kong --containers

# Prometheus метрики (если есть)
# container_cpu_cfs_throttled_seconds_total{pod=~"kong.*"}

# Проверяем limits
kubectl describe pod kong-pod | grep -A4 "Limits:"

# Смотрим историю в часы пик
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/kong/pods/kong-pod-xxx
```

```yaml
# Фикс: убираем CPU limit или увеличиваем
resources:
  requests:
    cpu: "2"
    memory: "2Gi"
  limits:
    memory: "4Gi" # memory limit оставляем
    # cpu limit убираем или делаем достаточно большим
```

---

### Гипотеза 5.3: Ephemeral storage исчерпан (Kong пишет на диск)

**Суть:** Kong буферизует большие ответы на диск. В часы пик ephemeral storage заканчивается → запись блокируется → таймаут.

**Проверка:**

```bash
# Смотрим использование диска
kubectl exec -it kong-pod -- df -h
kubectl exec -it kong-pod -- du -sh /tmp/* /usr/local/kong/logs/*

# Проверяем inode
kubectl exec -it kong-pod -- df -i

# Смотрим I/O wait
kubectl exec -it kong-pod -- iostat -x 1 10

# События Kubernetes
kubectl describe pod kong-pod | grep -A5 "Events:"
# Ищем: "Evicted", "DiskPressure", "EphemeralStorageExceeded"
```

---

## Итоговый план диагностики

```
┌─────────────────────────────────────────────────────────────┐
│                    ПЛАН ДИАГНОСТИКИ                          │
├─────────────────────────────────────────────────────────────┤
│ ШАГ 1 (5 мин): Определить КТО реально отдаёт 504           │
│   curl -v endpoint → смотрим Server: заголовок              │
│   Есть X-Kong-* заголовки? → Kong                           │
│   Нет → балансировщик перед Kong                            │
├─────────────────────────────────────────────────────────────┤
│ ШАГ 2 (10 мин): Проверить логирование сервисов              │
│   Добавить distributed tracing (OpenTelemetry)              │
│   Убедиться что span закрывается ПОСЛЕ отправки данных      │
├─────────────────────────────────────────────────────────────┤
│ ШАГ 3 (5 мин): Проверить gRPC message size limits           │
│   grpcurl с 10MB файлом напрямую к Service A                │
│   Если ошибка → это причина                                 │
├─────────────────────────────────────────────────────────────┤
│ ШАГ 4 (5 мин): Проверить Kong таймауты                      │
│   curl Admin API → services → timeouts                      │
│   Сравнить с реальным временем передачи (curl -w)           │
├─────────────────────────────────────────────────────────────┤
│ ШАГ 5 (15 мин): Нагрузочный тест с мониторингом            │
│   k6/locust с большими файлами                              │
│   Одновременно: kubectl top, netstat -s, ss -ti             │
└─────────────────────────────────────────────────────────────┘
```

**Наиболее вероятные причины** (по убыванию вероятности):

1. 🔴 **Гипотеза 4.1** — сервисы логируют до реальной отправки данных
2. 🔴 **Гипотеза 1.1** — Kong read_timeout меньше времени передачи тела
3. 🟡 **Гипотеза 2.1** — gRPC message size limit 4MB
4. 🟡 **Гипотеза 1.2** — буферизация Kong при нагрузке
5. 🟢 **Гипотеза 5.2** — CPU throttling Kong в часы пик
</details>

<details>
<summary>Ответ claude-opus-4-6</summary>
# Диагностика 504 Gateway Timeout в микросервисной архитектуре

## Визуализация пути запроса

```
Frontend ──→ [Kong :8000] ──→ [Service A :50051 gRPC] ──→ [Service B :8080 HTTP]
                │                        │                          │
                ▼                        ▼                          ▼
          nginx/OpenResty          Go runtime                 Python WSGI/ASGI
          upstream timeout      gRPC streaming              gunicorn/uvicorn
          proxy buffers         connection pool              worker threads
```

---

## 1. Исчерпание пула соединений Kong → Service A

### Почему

Kong использует upstream connection pool. В часы пик при больших файлах соединения удерживаются дольше → пул исчерпан → новые запросы ждут в очереди → timeout. При этом сами запросы, которые **прошли**, выполняются быстро — вы видите только survivors.

### Как проверить

```bash
# Метрики Kong — количество активных соединений к upstream
curl -s http://kong:8001/upstreams/service-a/health | jq '.data[].health'

# Prometheus-метрики (если включён плагин)
kong_upstream_target_health
kong_nginx_connections_active

# В логах Kong включить детальную диагностику
# kong.conf
log_level = debug
upstream_keepalive_pool_size = 512  # текущее значение?
upstream_keepalive_max_requests = 10000
```

```bash
# Проверить текущие лимиты
curl http://kong:8001/upstreams/service-a | jq '.data[].slots'

# Мониторинг в реальном времени
watch -n1 'ss -tn state established dst <service-a-ip> | wc -l'
```

### Фикс

```yaml
# kong upstream config
upstream:
  keepalive: 512 # было 60 по умолчанию
  keepalive_requests: 10000
  keepalive_timeout: 120
```

---

## 2. Таймауты Kong настроены без учёта размера файлов

### Почему

Дефолтные `write_timeout` / `read_timeout` / `send_timeout` в Kong = 60s, но для **больших файлов** важен не только общий таймаут, а скорость передачи. Если сеть нагружена, 10 МБ передаётся медленно, и Kong закрывает соединение раньше, чем тело запроса полностью передано upstream'у.

### Как проверить

```bash
# Текущие таймауты маршрута
curl http://kong:8001/routes/<route-id> | jq '{
  read_timeout, write_timeout, connect_timeout
}'

# Текущие таймауты сервиса
curl http://kong:8001/services/service-a | jq '{
  read_timeout, write_timeout, connect_timeout
}'
```

```bash
# Тест: отправить 10MB файл через Kong с замером
time curl -X POST https://api.example.com/upload \
  -F "file=@large_10mb.bin" \
  -w "\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}\n\
TIME_CONNECT:%{time_connect}\nTIME_STARTTRANSFER:%{time_starttransfer}\n"
```

### Фикс

```bash
# Увеличить таймауты для конкретного маршрута
curl -X PATCH http://kong:8001/routes/<route-id> \
  -d "read_timeout=120000" \
  -d "write_timeout=120000" \
  -d "connect_timeout=10000"
```

---

## 3. Буферизация proxy в Kong (OpenResty/nginx)

### Почему

Kong основан на nginx. При `proxy_buffering on` nginx пытается буферизовать весь ответ/запрос. Для 10 МБ файлов буферы переполняются → nginx пишет на диск → при высокой нагрузке I/O диска становится bottleneck → timeout.

### Как проверить

```bash
# Проверить текущую конфигурацию nginx внутри Kong
cat /usr/local/kong/nginx-kong.conf | grep -i buffer
cat /usr/local/kong/nginx-kong.conf | grep -i proxy_

# Мониторинг дискового I/O на ноде Kong
iostat -x 1 10
iotop -ao

# Проверить наличие временных файлов nginx
ls -la /usr/local/kong/proxy_temp/
watch -n1 'ls /usr/local/kong/proxy_temp/ | wc -l'
```

```nginx
# Что искать в конфигурации
proxy_buffering on;           # ← проблема для больших файлов
proxy_buffer_size 8k;
proxy_buffers 8 8k;
proxy_busy_buffers_size 16k;
proxy_temp_file_write_size 16k;  # ← слишком маленький для 10MB
```

### Фикс

```lua
-- Kong custom nginx template или плагин
-- kong.conf
nginx_proxy_proxy_buffering = off
-- или увеличить буферы
nginx_proxy_proxy_buffer_size = 128k
nginx_proxy_proxy_buffers = 16 128k
nginx_proxy_client_body_buffer_size = 16m
```

---

## 4. Ограничение `client_max_body_size` / `client_body_buffer_size`

### Почему

Если `client_body_buffer_size` < размера файла, nginx буферизует тело на диск. Если `client_max_body_size` слишком мал — запрос отклоняется, но при граничных значениях поведение может быть непредсказуемым (частичная передача → timeout).

### Как проверить

```bash
# Проверить текущие лимиты
grep -i client_max_body /usr/local/kong/nginx-kong.conf
grep -i client_body_buffer /usr/local/kong/nginx-kong.conf

# Через Admin API
curl http://kong:8001/ | jq '.configuration.nginx_http_client_max_body_size'
```

```bash
# Тест с файлами разного размера
for size in 1 5 10 15; do
  dd if=/dev/urandom of=/tmp/test_${size}mb.bin bs=1M count=$size 2>/dev/null
  echo "=== ${size}MB ==="
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
    -X POST -F "file=@/tmp/test_${size}mb.bin" https://api.example.com/upload
done
```

### Фикс

```
# kong.conf
nginx_http_client_max_body_size = 50m
nginx_http_client_body_buffer_size = 16m
```

---

## 5. gRPC message size limits (Service A)

### Почему

gRPC по умолчанию ограничивает размер сообщения **4 МБ**. Файл 10 МБ → ошибка на стороне gRPC. Но Kong может интерпретировать разрыв gRPC-соединения как timeout, а не как ошибку. Сервис A при этом логирует ошибку на уровне фреймворка, а не приложения.

### Как проверить

```go
// Проверить текущие настройки в коде Service A
// Искать в main.go или server.go:
grpc.MaxRecvMsgSize(...)
grpc.MaxSendMsgSize(...)

// Дефолт: 4MB = 4 * 1024 * 1024
```

```bash
# Тест через grpcurl напрямую к Service A (минуя Kong)
grpcurl -plaintext -d @ -max-msg-sz 15000000 \
  service-a:50051 mypackage.MyService/Upload < large_file.bin

# Проверить логи gRPC на уровне transport
GRPC_GO_LOG_VERBOSITY_LEVEL=99 GRPC_GO_LOG_SEVERITY_LEVEL=info ./service-a
```

### Фикс

```go
server := grpc.NewServer(
    grpc.MaxRecvMsgSize(50 * 1024 * 1024), // 50MB
    grpc.MaxSendMsgSize(50 * 1024 * 1024),
)
```

---

## 6. Kong ↔ Service A: gRPC-HTTP/2 framing и flow control

### Почему

HTTP/2 имеет механизм flow control с окнами (window size). При передаче больших файлов через gRPC, если receiver (Kong или Service A) не успевает обрабатывать фреймы, sender блокируется. В часы пик окна flow control заполняются → deadlock-подобная ситуация → timeout.

### Как проверить

```bash
# Включить verbose логирование HTTP/2 в Kong
# kong.conf
log_level = debug

# Анализ трафика между Kong и Service A
sudo tcpdump -i any -w /tmp/grpc_capture.pcap \
  host <service-a-ip> and port 50051

# Открыть в Wireshark, фильтр:
# http2.type == 7 (GOAWAY)
# http2.type == 3 (RST_STREAM)
# http2.type == 8 (WINDOW_UPDATE)
```

```bash
# Проверить HTTP/2 настройки Kong
grep -i http2 /usr/local/kong/nginx-kong.conf

# Проверить grpc_buffer_size
grep -i grpc /usr/local/kong/nginx-kong.conf
```

### Фикс

```
# kong.conf
nginx_proxy_grpc_buffer_size = 16m
nginx_proxy_grpc_read_timeout = 120s
nginx_proxy_grpc_send_timeout = 120s
```

---

## 7. Исчерпание worker connections / file descriptors в Kong

### Почему

Каждый большой файл = долгоживущее соединение. В часы пик количество одновременных соединений превышает `worker_connections` или лимит file descriptors → новые соединения не создаются → timeout.

### Как проверить

```bash
# Текущие лимиты
grep worker_connections /usr/local/kong/nginx-kong.conf
cat /proc/$(pgrep -f "nginx: worker")/limits | grep "open files"

# Текущее использование
ls /proc/$(pgrep -f "nginx: worker" | head -1)/fd | wc -l

# Системные лимиты
ulimit -n
sysctl fs.file-max
cat /proc/sys/fs/file-nr  # allocated  free  max

# Ошибки в логах
grep "worker_connections are not enough" /usr/local/kong/logs/error.log
grep "Too many open files" /usr/local/kong/logs/error.log
```

```bash
# Мониторинг в реальном времени
watch -n1 'ss -s'
watch -n1 'cat /proc/sys/fs/file-nr'
```

### Фикс

```
# kong.conf
nginx_worker_connections = 16384

# Системный уровень
ulimit -n 65536
# /etc/security/limits.conf
kong soft nofile 65536
kong hard nofile 65536
```

---

## 8. Survivorship bias в логах сервисов A и B

### Почему

**Ключевая гипотеза.** Запросы, которые получают 504, могут **никогда не доходить** до сервисов A и B. Kong отдаёт 504 потому что:

- Не смог установить соединение (connect timeout)
- Запрос стоял в очереди и был отброшен
- Соединение было установлено, но тело запроса не было полностью передано

Сервисы видят только успешно доставленные запросы.

### Как проверить

```bash
# Сопоставить request_id между Kong и сервисами
# В Kong включить X-Kong-Request-Id
curl http://kong:8001/plugins -d "name=correlation-id" \
  -d "config.header_name=X-Request-ID" \
  -d "config.generator=uuid"

# Затем найти 504 запросы в логах Kong
grep "504" /usr/local/kong/logs/access.log | awk '{print $REQUEST_ID}'

# Искать эти же ID в логах Service A
grep "<request-id>" /var/log/service-a/access.log
# Если не найдены — запрос не дошёл до сервиса
```

```python
# Скрипт для автоматического сопоставления
import re
from collections import defaultdict

kong_504_ids = set()
with open('kong_access.log') as f:
    for line in f:
        if ' 504 ' in line:
            match = re.search(r'request_id=(\S+)', line)
            if match:
                kong_504_ids.add(match.group(1))

service_a_ids = set()
with open('service_a_access.log') as f:
    for line in f:
        match = re.search(r'request_id=(\S+)', line)
        if match:
            service_a_ids.add(match.group(1))

never_reached = kong_504_ids - service_a_ids
print(f"504 in Kong: {len(kong_504_ids)}")
print(f"Never reached Service A: {len(never_reached)}")
print(f"Reached but still 504: {len(kong_504_ids & service_a_ids)}")
```

---

## 9. DNS resolution delays

### Почему

Kong резолвит upstream по DNS. В часы пик DNS-сервер перегружен → резолв занимает секунды → это вычитается из connect_timeout → для больших файлов суммарное время превышает таймаут.

### Как проверить

```bash
# Проверить DNS-конфигурацию Kong
curl http://kong:8001/ | jq '.configuration | {
  dns_resolver, dns_order, dns_stale_ttl, dns_not_found_ttl,
  dns_error_ttl, dns_no_sync
}'

# Замерить время DNS-резолва
for i in $(seq 1 100); do
  dig @<kong-dns-server> service-a.internal +stats | grep "Query time"
done

# Проверить DNS cache hit rate
curl http://kong:8001/status | jq '.database'
# Или через Prometheus
kong_dns_query_duration_seconds
```

```bash
# Проверить, не используется ли DNS вместо IP
curl http://kong:8001/services/service-a | jq '.host'
# Если host = DNS-имя, а не IP — потенциальная проблема
```

### Фикс

```
# kong.conf
dns_stale_ttl = 60
dns_not_found_ttl = 1
dns_order = LAST,A,SRV,CNAME
```

---

## 10. Backpressure от Service B → Service A → Kong

### Почему

Service B (Python) при больших файлах может блокироваться на I/O (запись на диск, обработка). В часы пик worker'ы Python заняты → Service A ждёт ответа → Kong ждёт Service A. Но Service A логирует запрос как успешный **после** получения ответа, а Kong уже отдал 504.

```
Timeline:
0s    ─── Kong отправляет запрос Service A ───
55s   ─── Service A всё ещё ждёт Service B ───
60s   ─── Kong: TIMEOUT 504 ─── (закрывает соединение)
62s   ─── Service B отвечает Service A ───
62s   ─── Service A логирует: "200 OK, 62s" ───
          (но Kong уже ушёл)
```

### Как проверить

```bash
# Проверить количество worker'ов Service B
# Если gunicorn:
ps aux | grep gunicorn | wc -l
# Если uvicorn:
ps aux | grep uvicorn | wc -l

# Мониторинг очереди запросов Service B
# gunicorn с statsd
gunicorn --statsd-host=localhost:8125 app:app

# Проверить время ответа Service B в часы пик
# В логах Service A — время вызова Service B
grep "service_b_call_duration" /var/log/service-a/app.log | \
  awk '{print $NF}' | sort -n | tail -20
```

```python
# Добавить в Service A middleware для логирования
import time
import logging

class TimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        start = time.monotonic()
        try:
            await self.app(scope, receive, send)
        finally:
            duration = time.monotonic() - start
            if duration > 5:  # логировать медленные запросы
                logging.warning(f"Slow request: {duration:.2f}s {scope['path']}")
```

### Фикс

```bash
# Увеличить worker'ы Service B
gunicorn -w 8 -k uvicorn.workers.UvicornWorker --timeout 120 app:app

# Или перейти на async
uvicorn app:app --workers 4 --loop uvloop
```

---

## 11. TCP connection queue overflow (SYN backlog)

### Почему

При пиковой нагрузке TCP backlog на Service A переполняется → SYN-пакеты от Kong дропаются → Kong ждёт → connect timeout → 504.

### Как проверить

```bash
# На машине Service A
# Проверить дропы
netstat -s | grep -i "listen"
# SYNs to LISTEN sockets dropped: <число>
# times the listen queue of a socket overflowed: <число>

cat /proc/net/netstat | grep -i overflow
nstat -az | grep -i "listen\|overflow\|drop"

# Текущий backlog
ss -tlnp | grep 50051
# Recv-Q / Send-Q — если Recv-Q близок к Send-Q, очередь полна

# Системные лимиты
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_max_syn_backlog
```

```bash
# Мониторинг в реальном времени
watch -n1 'nstat -az TcpExtListenOverflows TcpExtListenDrops'
```

### Фикс

```bash
# Системный уровень
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535

# В Go-сервисе (если используется net.Listen)
listener, _ := net.Listen("tcp", ":50051")
// Go использует somaxconn автоматически
```

---

## 12. Kubernetes / Docker networking (если контейнеризация)

### Почему

В K8s: kube-proxy (iptables/IPVS) → conntrack table overflow → пакеты дропаются. Или: Service mesh sidecar (Envoy/Istio) добавляет латентность. Или: Pod'ы на разных нодах → сетевой overlay (VXLAN) добавляет overhead для больших пакетов.

### Как проверить

```bash
# Conntrack table
sysctl net.netfilter.nf_conntrack_count
sysctl net.netfilter.nf_conntrack_max
# Если count близок к max — проблема

# Conntrack drops
conntrack -S | grep drop
dmesg | grep "nf_conntrack: table full"

# MTU проблемы (фрагментация больших пакетов)
ping -M do -s 1472 <service-a-pod-ip>  # стандартный MTU 1500
ping -M do -s 1422 <service-a-pod-ip>  # VXLAN overhead = 50 bytes

# Проверить сетевые политики
kubectl get networkpolicies -A
```

```bash
# Если Istio/Envoy sidecar
istioctl proxy-status
istioctl proxy-config cluster <pod-name>
kubectl logs <pod-name> -c istio-proxy | grep "504\|timeout\|overflow"

# Envoy stats
kubectl exec <pod> -c istio-proxy -- \
  curl localhost:15000/stats | grep -E "overflow|timeout|retry|pending"
```

### Фикс

```bash
# Conntrack
sysctl -w net.netfilter.nf_conntrack_max=524288

# MTU
# В CNI конфигурации установить правильный MTU
# Calico: MTU = 1440 (для VXLAN)
# Flannel: MTU = 1450
```

---

## 13. Rate limiting / Circuit breaker в Kong

### Почему

Плагины rate-limiting или circuit-breaker в Kong могут срабатывать для эндпоинтов с большими файлами, потому что они дольше занимают соединение → считаются как "медленные" → circuit breaker открывается.

### Как проверить

```bash
# Список всех плагинов на маршруте
curl http://kong:8001/routes/<route-id>/plugins | jq '.data[].name'

# Проверить конфигурацию circuit breaker
curl http://kong:8001/upstreams/service-a | jq '{
  healthchecks: .healthchecks
}'

# Проверить passive health checks
curl http://kong:8001/upstreams/service-a | jq '
  .healthchecks.passive.unhealthy.tcp_failures,
  .healthchecks.passive.unhealthy.timeouts,
  .healthchecks.passive.unhealthy.http_failures
'
```

---

## 14. Garbage Collection паузы (Go Service A)

### Почему

При обработке 10 МБ файлов Go аллоцирует много памяти. В часы пик GC может вызывать stop-the-world паузы. Если пауза совпадает с моментом, когда Kong ждёт ответ — timeout.

### Как проверить

```bash
# Включить GC трейсинг
GODEBUG=gctrace=1 ./service-a 2>&1 | tee gc.log

# Формат вывода:
# gc 1 @0.012s 2%: 0.010+1.5+0.020 ms clock, 0.080+0/1.2/0.30+0.16 ms cpu, ...
# Искать паузы > 100ms

# Или через pprof
go tool pprof http://service-a:6060/debug/pprof/heap
go tool pprof http://service-a:6060/debug/pprof/goroutine

# Проверить количество горутин
curl http://service-a:6060/debug/pprof/goroutine?debug=1 | head -5
```

```go
// Добавить runtime метрики
import "runtime"

var m runtime.MemStats
runtime.ReadMemStats(&m)
log.Printf("Alloc=%dMB, NumGC=%d, PauseTotalNs=%d",
    m.Alloc/1024/1024, m.NumGC, m.PauseTotalNs)
```

### Фикс

```bash
# Настроить GC
GOGC=200 ./service-a          # менее агрессивный GC
GOMEMLIMIT=2GiB ./service-a   # Go 1.19+, soft memory limit
```

---

## 15. Python GIL + синхронная обработка в Service B

### Почему

Если Service B использует синхронный фреймворк (Flask/Django + gunicorn sync workers), каждый worker блокируется на обработке файла. При N workers и N+1 одновременных запросах с большими файлами — очередь → timeout.

### Как проверить

```bash
# Тип worker'ов
ps aux | grep gunicorn
# sync workers = проблема для I/O-bound задач

# Количество одновременных запросов vs workers
# Добавить в Service B
import threading
import logging

active_requests = 0
lock = threading.Lock()

@app.before_request
def track_start():
    global active_requests
    with lock:
        active_requests += 1
        logging.info(f"Active requests: {active_requests}")

@app.after_request
def track_end(response):
    global active_requests
    with lock:
        active_requests -= 1
    return response
```

```bash
# Нагрузочный тест напрямую на Service B
ab -n 100 -c 20 -p large_file.bin -T 'application/octet-stream' \
  http://service-b:8080/process
```

---

## Системный план диагностики

```
┌─────────────────────────────────────────────────────────┐
│              ПОРЯДОК ДИАГНОСТИКИ                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ШАГ 1: Correlation ID                                  │
│  ├── Включить X-Request-ID сквозной                     │
│  ├── Найти 504 запросы в Kong                           │
│  └── Проверить: дошли ли они до Service A/B?            │
│       │                                                 │
│       ├── НЕ дошли → проблема между Kong и Service A    │
│       │   ├── Шаг 2a: connection pool Kong              │
│       │   ├── Шаг 2b: TCP backlog Service A             │
│       │   ├── Шаг 2c: DNS resolution                   │
│       │   └── Шаг 2d: K8s networking / conntrack        │
│       │                                                 │
│       └── Дошли → проблема с таймингом                  │
│           ├── Шаг 2e: Kong timeout < actual duration    │
│           ├── Шаг 2f: gRPC message size limit           │
│           ├── Шаг 2g: Service B backpressure            │
│           └── Шаг 2h: GC pauses                         │
│                                                         │
│  ШАГ 3: Воспроизведение                                 │
│  ├── Нагрузочный тест с файлами 10MB                    │
│  ├── Постепенно увеличивать concurrency                  │
│  └── Фиксировать момент появления 504                   │
│                                                         │
│  ШАГ 4: Мониторинг в реальном времени                   │
│  ├── ss -tn state established (connections)             │
│  ├── nstat (TCP drops/overflows)                        │
│  ├── iostat (disk I/O для буферов)                      │
│  └── /proc/sys/fs/file-nr (file descriptors)            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

```bash
# Универсальный скрипт мониторинга для запуска в часы пик
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  echo "--- Kong connections ---"
  ss -tn state established dst $SERVICE_A_IP | wc -l
  echo "--- Service A TCP queue ---"
  ss -tlnp sport = :50051
  echo "--- Conntrack ---"
  cat /proc/sys/net/netfilter/nf_conntrack_count
  echo "--- File descriptors ---"
  cat /proc/sys/fs/file-nr
  echo "--- TCP drops ---"
  nstat -az TcpExtListenOverflows TcpExtListenDrops 2>/dev/null
  echo ""
  sleep 5
done
```

> **Наиболее вероятные причины** (по опыту): **#2** (таймауты Kong), **#8** (survivorship bias — запросы не доходят), **#3** (буферизация nginx), **#7** (исчерпание connections/fd). Начинайте с correlation ID — это сразу сузит область поиска вдвое.

</details>
