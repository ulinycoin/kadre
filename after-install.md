Kadre установлен из GitHub.

В `~/.hermes/config.yaml`:

```yaml
image_gen:
  provider: nanogpt-cyber
  model: auto
  max_parallel_requests: 1
```

Дальше: `hermes gateway restart` (или новая сессия).

Обновить позже: `hermes plugins update nanogpt-cyber`
Если ставил копированием без git: `hermes plugins install ulinycoin/kadre --force --enable`
