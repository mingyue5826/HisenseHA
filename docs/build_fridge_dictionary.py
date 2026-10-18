"""从「智控字典」抓包生成精简的本地冰箱字典。

用途
----
``docs/api-samples/layout-control-响应体.json`` 是微信小程序 ``POST
/4.0/iot/layout/smartHomeApp/control`` 的原始响应（约 253 KB / 6216 行）。
里面绝大多数内容对集成无用（空字符串、图片 URL、UI 版式字段）。本脚本把它
压成三块精华，输出到 ``docs/fridge_dictionary.json``：

1. ``alarm_map``    —— ``subFunction`` → 标题 / 说明 / 触发值。**只收录干净的
   1:1 映射**（Alarm.Fridge + Fault.Fridge 命名空间），可直接当查表用。
2. ``functions``    —— 按 ``connector.device.function.*`` 分组的能力清单，
   保留 ``subFunction`` / ``value`` / ``title`` / ``briefIntro``。
3. ``columns``      —— 27 个栏目的结构，供核对「小程序页面有哪些功能区」。

为什么要清洗
------------
同一 ``(function, subFunction)`` 在原始响应里可能对应**多个** ``showInfo.title``：

* 告警列嵌套重复（第 1 列 subColumns 与第 2 列平铺是同一批）→ 真重复，可去。
* ``GearControl.*`` 的 ``refrigeratorGear`` 有 value 1~5，标题都是「冷藏室」，
  真正的差异在 ``briefIntro``（档位 → 温度区间）。
* ``WillLight.willLight`` 的 value 1~7 有两种完全不同的语义（四季 / 营养素），
  是两条并列 UI 线，**不能**当键值表用。

所以本脚本的输出保留「一对多」，由使用方自己决定取哪条，不擅自合并。

用法::

    python docs/build_fridge_dictionary.py            # 生成并打印摘要
    python docs/build_fridge_dictionary.py --diff     # 与已存字典比对
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
SOURCE = DOCS / "api-samples" / "layout-control-响应体.json"
TARGET = DOCS / "fridge_dictionary.json"

#: 只有这两个命名空间是「1:1 键名 → 文案」的干净映射。
ALARM_NAMESPACES = (
    "connector.device.function.Alarm.Fridge",
    "connector.device.function.Fault.Fridge",
)


def _clean(value):
    """空字符串 / None 一律返回 None，渲染时就不必再判空。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_comb(raw):
    """``modelCombFunction`` 是「JSON 字符串」，这里容错解析。"""
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str) and raw.strip().startswith("["):
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        func = _clean(item.get("function"))
        sub = _clean(item.get("subFunction"))
        if not func and not sub:
            continue
        out.append({"function": func, "subFunction": sub, "value": _clean(item.get("value"))})
    return out


def _walk_column(column):
    """深度优先遍历栏目，含嵌套 ``subColumns``。"""
    yield column
    for child in column.get("subColumns") or []:
        yield from _walk_column(child)


def _tiles(column):
    """列出栏目下所有 tile，含 ``subTiles``。"""
    for tile in column.get("tiles") or []:
        yield tile
        for sub in tile.get("subTiles") or []:
            yield sub


def build(source: Path) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8"))
    page = raw["payload"]["pageInfo"]
    columns = page.get("columns") or []

    alarm_map: dict[str, dict] = {}
    functions: dict[str, dict] = {}
    out_columns: list[dict] = []
    tile_total = 0

    for column in columns:
        col_entry = {
            "index": column.get("index"),
            "title": _clean(column.get("title")),
            "briefIntro": _clean(column.get("briefIntro")),
            "columnType": column.get("columnType"),
            "subColumns": [],
            "tiles": [],
        }
        for node in _walk_column(column):
            is_root = node is column
            target = col_entry["tiles"] if is_root else None
            if not is_root:
                target = {
                    "title": _clean(node.get("title")),
                    "briefIntro": _clean(node.get("briefIntro")),
                    "tiles": [],
                }
                col_entry["subColumns"].append(target)
                target = target["tiles"]

            for tile in _tiles(node):
                tile_total += 1
                show = tile.get("showInfo") or {}
                action = tile.get("actionInfo") or {}
                combos = _parse_comb(action.get("modelCombFunction"))

                entry = {
                    "typeCode": tile.get("typeCode"),
                    "title": _clean(show.get("title")),
                    "briefIntro": _clean(show.get("briefIntro")),
                    "modelFunction": _clean(action.get("modelFunction")),
                    "modeFunction": _clean(action.get("modeFunction")),
                    "modelCombFunction": combos or None,
                }
                entry = {k: v for k, v in entry.items() if v is not None}
                if entry:
                    target.append(entry)

                for combo in combos:
                    func, sub = combo["function"], combo["subFunction"]
                    if not (func and sub):
                        continue
                    bucket = functions.setdefault(func, {"subFunctions": {}})
                    slot = bucket["subFunctions"].setdefault(sub, {"titles": []})
                    title = _clean(show.get("title"))
                    brief = _clean(show.get("briefIntro"))
                    row = {"value": combo["value"], "title": title, "briefIntro": brief}
                    if row not in slot["titles"]:
                        slot["titles"].append(row)

                    if func in ALARM_NAMESPACES and sub not in alarm_map:
                        alarm_map[sub] = {
                            "namespace": func,
                            "title": title,
                            "briefIntro": brief,
                            # 字典里带 value 说明「等于该值才高亮/显示」，即触发值；
                            # 不带 value 的告警位一律按 1 = 触发处理。
                            "activeValue": combo["value"] or "1",
                        }

        out_columns.append(col_entry)

    return {
        "meta": {
            "source": "POST https://iot-aihome.hismarttv.com/4.0/iot/layout/smartHomeApp/control",
            "sceneCode": "mainPage",
            "device": "BCD-516WD1FPA-EQ51 (容声 Ronshen, productCode LB051600602J)",
            "pageTitle": _clean(page.get("title")),
            "pageCode": _clean(page.get("pageCode")),
            "capturedAt": "2026-10-11",
            "columnCount": len(columns),
            "tileCount": tile_total,
            "alarmMapSize": len(alarm_map),
            "functionCount": len(functions),
        },
        "alarm_map": alarm_map,
        "functions": functions,
        "columns": out_columns,
    }


def _fingerprint(data: dict) -> dict:
    """只比较「键名 → 文案」，UI 版式噪音不参与 diff。"""
    return {
        "alarm_map": {
            key: [val.get("title"), val.get("briefIntro"), val.get("activeValue")]
            for key, val in sorted(data.get("alarm_map", {}).items())
        },
        "functions": {
            func: {
                sub: [row.get("title") for row in val.get("titles", [])]
                for sub, val in sorted(body.get("subFunctions", {}).items())
            }
            for func, body in sorted(data.get("functions", {}).items())
        },
    }


def _diff(old: dict, new: dict) -> int:
    a, b = _fingerprint(old), _fingerprint(new)
    changes = 0
    for section in ("alarm_map", "functions"):
        keys = set(a[section]) | set(b[section])
        for key in sorted(keys):
            if a[section].get(key) != b[section].get(key):
                changes += 1
                print(f"[{section}] {key}")
                print(f"  - 旧: {a[section].get(key)}")
                print(f"  + 新: {b[section].get(key)}")
    return changes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成精简本地冰箱字典")
    parser.add_argument("--diff", action="store_true", help="与已存在的目标文件比对")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--target", type=Path, default=TARGET)
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"找不到源文件：{args.source}", file=sys.stderr)
        return 2

    data = build(args.source)

    if args.diff:
        if not args.target.exists():
            print(f"目标文件不存在，无法比对：{args.target}", file=sys.stderr)
            return 2
        old = json.loads(args.target.read_text(encoding="utf-8"))
        changes = _diff(old, data)
        print(f"\n共 {changes} 处差异")
        return 0

    args.target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    meta = data["meta"]
    print(f"已写入 {args.target}")
    print(
        f"  栏目 {meta['columnCount']} / tile {meta['tileCount']} / "
        f"告警映射 {meta['alarmMapSize']} / 能力 {meta['functionCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
