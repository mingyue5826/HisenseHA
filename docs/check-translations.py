"""翻译一致性自检：不需要 Home Assistant，也不需要开冰箱。

用法::

    python docs/check-translations.py

它验证五件事：

1. 代码里每个 ``translation_key`` 都能在对应平台的 ``entity`` 下找到；
2. 翻译里没有代码已不使用的孤儿条目；
3. 动态生成的 ``fridge_alarm_<code>`` 16 个全部有中文和英文；
4. ``strings.json`` 与 ``translations/en.json`` 完全一致（hassfest 要求）；
5. 中英键集合一致，且每条都有非空 ``name``。

漏翻译不会让集成报错，只会让 UI 上显示出 key 本身，所以只能靠这个脚本兜住。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "hisense"

#: 模块 → HA 平台名。translation_key 必须放在 `entity.<平台>` 下。
PLATFORMS = {
    "sensor.py": "sensor",
    "binary_sensor.py": "binary_sensor",
    "switch.py": "switch",
    "select.py": "select",
    "number.py": "number",
    "button.py": "button",
    "climate.py": "climate",
}

FAILED: list[str] = []


def check(condition: bool, message: str) -> None:
    """记录一条断言结果，失败不中断（一次跑完能看到所有问题）。"""
    if condition:
        print(f"  ✓ {message}")
    else:
        print(f"  ✗ {message}")
        FAILED.append(message)


def static_keys(module: str) -> set[str]:
    """Return literal translation keys used by one module."""
    text = (PKG / module).read_text(encoding="utf-8")
    found = re.findall(r'translation_key="([^"]+)"', text)
    found += re.findall(r'_attr_translation_key\s*=\s*"([^"]+)"', text)
    return set(found)


def alarm_codes() -> list[str]:
    """Return the fridge alarm keys defined in fridge_const.py."""
    text = (PKG / "fridge_const.py").read_text(encoding="utf-8")
    block = text.split("FRIDGE_ALARM_CODES")[1].split("}")[0]
    return re.findall(r'"(\w+Alarm\w*)"\s*:', block)


def flatten(node, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out |= flatten(value, path)
        else:
            out.add(path)
    return out


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    strings_path = PKG / "strings.json"
    en_path = PKG / "translations" / "en.json"
    zh_path = PKG / "translations" / "zh-Hans.json"

    print("[1] 文件存在性与一致性")
    check(strings_path.exists(), "strings.json 存在")
    if not strings_path.exists():
        print("\n缺少 strings.json，后续检查跳过。")
        return 1
    check(en_path.exists(), "translations/en.json 存在")
    check(zh_path.exists(), "translations/zh-Hans.json 存在")

    strings = load(strings_path)
    en = load(en_path)
    zh = load(zh_path)
    check(strings == en, "strings.json 与 translations/en.json 完全一致")

    print("\n[2] 代码 → 翻译（每个 key 都在对应平台下）")
    missing: list[str] = []
    for module, platform in PLATFORMS.items():
        if not (PKG / module).exists():
            continue
        bucket = en.get("entity", {}).get(platform, {})
        for key in sorted(static_keys(module)):
            if key not in bucket:
                elsewhere = [
                    p for p, d in en.get("entity", {}).items() if key in d
                ]
                missing.append(f"{module}: {key}（缺失，或错放在 {elsewhere}）")
    check(not missing, f"静态 key 全部命中（{len(missing)} 个问题）")
    for item in missing:
        print(f"      {item}")

    print("\n[3] 动态告警 key")
    codes = alarm_codes()
    alarm_keys = {f"fridge_alarm_{code}" for code in codes}
    for lang, data in (("en", en), ("zh-Hans", zh)):
        bucket = data.get("entity", {}).get("binary_sensor", {})
        absent = sorted(alarm_keys - set(bucket))
        check(not absent, f"{lang}: {len(codes)} 个告警翻译齐全（缺 {len(absent)} 个）")
        for key in absent:
            print(f"      {lang} 缺 {key}")

    print("\n[4] 孤儿条目（翻译里有、代码里不用）")
    used: set[tuple[str, str]] = set()
    for module, platform in PLATFORMS.items():
        if not (PKG / module).exists():
            continue
        used |= {(platform, key) for key in static_keys(module)}
    used |= {("binary_sensor", key) for key in alarm_keys}
    dead: list[str] = []
    for platform, bucket in en.get("entity", {}).items():
        for key in bucket:
            if (platform, key) not in used:
                dead.append(f"{platform}.{key}")
    check(not dead, f"没有孤儿条目（{len(dead)} 个）")
    for item in dead:
        print(f"      {item}")

    print("\n[5] 中英对照")
    en_flat, zh_flat = flatten(en), flatten(zh)
    only_en = sorted(en_flat - zh_flat)
    only_zh = sorted(zh_flat - en_flat)
    check(not only_en, f"中文不缺键（缺 {len(only_en)} 个）")
    for item in only_en[:20]:
        print(f"      中文缺 {item}")
    check(not only_zh, f"英文不缺键（多 {len(only_zh)} 个）")
    for item in only_zh[:20]:
        print(f"      英文缺 {item}")

    empty: list[str] = []

    def walk(node, data, prefix: str = "") -> None:
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(value, data[key], path)
            elif not str(value).strip():
                empty.append(path)

    walk(zh, zh)
    check(not empty, f"中文没有空值（{len(empty)} 个）")
    for item in empty:
        print(f"      {item}")

    print()
    if FAILED:
        print(f"失败 {len(FAILED)} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
