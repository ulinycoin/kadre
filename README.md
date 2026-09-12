# Kadre

Система генерации кадров для **агента**: [Hermes Agent](https://hermes-agent.nousresearch.com/) или **Grok Bot**.

Поверх NanoGPT: **CyberRealistic XL** и **CyberRealistic Pony v9.0**. Маршрут, промпты и i2i — из живых тестов, не из догадок.

## Что умеет агент

| Запрос | Модель | Почему |
|---|---|---|
| Образ + аксессуары (Харли, Лара, Клеопатра) | XL | читаемый персонаж |
| 50+ | XL | Pony омолаживает |
| Акт, cum, писсинг, наездница | Pony | XL оставляет портрет и выкидывает действие |
| Барби / кукла | Pony | XL = силикон |
| Референс + новая поза | txt2img, без i2i | i2i залипает в старой позе даже на 0.75 |
| Референс + акт | Pony txt2img | вместе лицо и акт не держатся |
| Правка того же кадра | XL i2i, strength ~0.34 | только `imageDataUrl` на `/generations` |

Цена кадра: **$0.0051**. `negative_prompt` — snake_case. `input_references` на `/api/v1/images` не работает.

## Hermes Agent

```bash
mkdir -p ~/.hermes/plugins/image_gen
cp -R plugins/image_gen/nanogpt-cyber ~/.hermes/plugins/image_gen/nanogpt-cyber
hermes plugins enable nanogpt-cyber
```

В `~/.hermes/config.yaml`:

```yaml
image_gen:
  provider: nanogpt-cyber
  model: auto
```

Ключ: `NANOGPT_API_KEY` (или `hermes tools` → NanoGPT CyberRealistic).

Дальше обычный `image_generate`. Провайдер сам выбирает XL/Pony, переписывает промпт и решает, брать ли референс.

## Grok Bot

1. Системный промпт: [`grok/SYSTEM.md`](grok/SYSTEM.md)
2. Инструменты: [`grok/TOOLS.json`](grok/TOOLS.json)
3. Обработчики — CLI:

```bash
export NANOGPT_API_KEY=sk-nano-...
python scripts/kadre.py plan "клеопатра, наездница, лицом в камеру"
python scripts/kadre.py generate "харли квинн, склад, бита" --out .kadre-out/harley.jpg
```

Правила агента: [`skills/kadre/SKILL.md`](skills/kadre/SKILL.md)

## Проверка без ключа

```bash
python -m unittest tests/test_router.py
python scripts/kadre.py plan "кукла барби стиль"
python scripts/kadre.py doctor
```

## Локальный запуск генерации

Нужен ключ [nano-gpt.com](https://nano-gpt.com). Без него `plan` и тесты живы, `generate` нет.
