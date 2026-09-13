---
name: kadre
description: >
  Генерация кадров через image_generate / NanoGPT / CyberRealistic XL и Pony / Kadre.
  Один вызов на запрос человека. Не перегенерировать и не делать варианты.
version: 1.1.0
author: kadre
license: MIT
metadata:
  hermes:
    tags: [image, nanogpt, kadre]
    requires_tools: [image_generate]
required_environment_variables:
  - name: NANOGPT_API_KEY
    prompt: NanoGPT API key
    help: https://nano-gpt.com
    required_for: generate
---

# Kadre — один кадр, без ретраев

Провайдер `nanogpt-cyber` сам выбирает XL или Pony, пишет промпт и решает про i2i.
Тебе не нужно «подбирать» модель и не нужно оценивать картинку глазами.

## Жёсткие правила

1. **Один `image_generate` на один запрос человека.** Не пачка, не 2–4 варианта.
2. **Первый `success=true` — финал.** Покажи путь и модель. Стоп.
3. **Не вызывай инструмент снова**, даже если руки кривые, акт слабый или лицо уехало. Это свойство модели, не ошибка вызова.
4. **Не гоняй vision-QA** и не пиши «попробую ещё раз / better anatomy / another seed».
5. **Не меняй модель «на всякий случай».** `auto` уже маршрутизирует.
6. **Повтор только по явной фразе человека:** «ещё», «перегенерируй», «другой вариант».
7. Не монтировать фото. Не склеивать лица.

## Что ответить

Коротко по-русски: модель, почему, путь к файлу, `notes` если есть. Без внутренностей API.

Если в ответе `cached: true` — это тот же кадр, деньги не ушли. Скажи это и не вызывай инструмент снова.

## Обновление с GitHub

Только если человек явно просит обновить плагин:

```bash
hermes plugins install ulinycoin/kadre --force --enable
```

Потом проверь `image_gen.provider: nanogpt-cyber` и `max_parallel_requests: 1`. Не генерируй кадры в этом ходе.

## Маршрут (уже внутри провайдера)

| Запрос | Модель |
|---|---|
| Образ, аксессуары, 50+ | XL |
| Акт, cum, писсинг, наездница, Барби | Pony |
| Референс + новая поза | txt2img, без i2i |
| Правка того же кадра | i2i, strength ~0.34 |
