#!/usr/bin/env python3
"""CLI для Hermes / Grok Bot: plan | generate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "image_gen" / "nanogpt-cyber"
sys.path.insert(0, str(PLUGIN))

from nanogpt import api_key, generate  # noqa: E402
from plan import make_plan  # noqa: E402


def cmd_plan(args: argparse.Namespace) -> int:
    plan = make_plan(
        args.request,
        has_reference=bool(args.ref),
        model_override=None if args.model == "auto" else args.model,
        aspect_ratio=args.aspect,
    )
    print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    plan = make_plan(
        args.request,
        has_reference=bool(args.ref),
        model_override=None if args.model == "auto" else args.model,
        aspect_ratio=args.aspect,
    )
    result = generate(
        model=plan.model,
        prompt=plan.prompt,
        negative_prompt=plan.negative_prompt,
        resolution=plan.resolution,
        seed=args.seed,
        guidance_scale=plan.guidance_scale,
        steps=plan.steps,
        reference=args.ref if plan.use_i2i else None,
        strength=plan.strength,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result["bytes"])
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(out.resolve()),
                "model": plan.model,
                "reason": plan.reason,
                "warnings": plan.warnings,
                "used_i2i": plan.use_i2i,
                "strength": plan.strength,
                "cost": result.get("cost"),
                "balance": result.get("balance"),
                "prompt": plan.prompt,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    print(json.dumps({"has_key": bool(api_key()), "plugin": str(PLUGIN)}, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Kadre — NanoGPT XL/Pony для агента")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("request", help="запрос пользователя, как есть")
    common.add_argument("--ref", help="путь или URL референса")
    common.add_argument("--model", default="auto", choices=["auto", "cyberrealistic-xl", "cyberrealistic-pony-v9"])
    common.add_argument("--aspect", default="portrait", choices=["portrait", "square", "landscape"])

    sp = sub.add_parser("plan", parents=[common], help="только маршрут и промпт")
    sp.set_defaults(func=cmd_plan)

    sg = sub.add_parser("generate", parents=[common], help="сгенерировать кадр")
    sg.add_argument("--out", default=".kadre-out/frame.jpg")
    sg.add_argument("--seed", type=int)
    sg.set_defaults(func=cmd_generate)

    sd = sub.add_parser("doctor", help="проверка ключа")
    sd.set_defaults(func=cmd_doctor)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
