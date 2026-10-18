#!/usr/bin/env python3
"""冰箱控制命令字典探测器 —— 批量验证候选 command / params，找出正确答案。

用途：
  抓到微信小程序包后，把里面的 command 名填进 COMMAND_CANDIDATES，
  批量向设备下发并打印结果，快速确定可用组合。

用法:
    # 1) 先看当前内置的候选（温度已确认，其余为推测）
    python probe-commands.py <用户名> <密码> --list

    # 2) 批量探测所有候选（会真实下发命令）
    python probe-commands.py <用户名> <密码> --run

    # 3) 只测某一类
    python probe-commands.py <用户名> <密码> --run --only power

    # 4) 手动测一条自定义命令
    python probe-commands.py <用户名> <密码> --try "connector.device.command.SetPower" '{"powerStatus":{"value":1}}'

环境变量: HISENSE_USER / HISENSE_PASS
"""

import base64
import hashlib
import json
import os
import sys
import time
import uuid
from urllib import error, request

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_PORTAL_APP_KEY = "commonweb"
_PORTAL_APP_SECRET = "MORZRbkuiWxjp+SM4vR_GxY4pZxLZ6rn"
_PORTAL_AES_IV = _PORTAL_APP_SECRET[:16].encode("ascii")

PORTAL_URL = "https://portal-account.hismarttv.com/mobile/se/signon"
BASE_URL = "https://iot-aihome.hismarttv.com"
READ_SOURCE_TYPE = 3
CONTROL_APP_VERSION = "6.2.18.7"
CONTROL_SOURCE_TYPE = 20
CONTROL_SOURCE_NAME = "smartlifeAppH5"
POWER_SOURCE_NAME = "smartlifeApp"

# ---- 小程序抓包得到的另一套取值（19:34，模式切换实测可用）----
MINI_SOURCE_TYPE = 21
MINI_SOURCE_NAME = "miniProgram"
MINI_APP_VERSION = "1.5.6.6"
MINI_APP_TYPE = 2


# ============================================================
# 候选命令表 —— 抓到小程序包后，把真实 command 名替换到这里
# 格式: (分组, 说明, command, params, source_name)
# ============================================================
F = "connector.device.command."

COMMAND_CANDIDATES = [
    # ============================================================
    # ★★★ 全部已确认（小程序真实抓包，19:46）
    # ============================================================
    # 温度类 —— 带区域后缀 `.Refrigerator` / `.Freeze`
    ("temperature", "冷藏设温=6 [已确认]", F + "SetTemperature.Refrigerator",
     {"refrigeratorSetTemperature": {"value": 6}}, "mini"),
    ("temperature", "冷冻设温=-16 [已确认]", F + "SetTemperature.Freeze",
     {"freezeSetTemperature": {"value": -16}}, "mini"),
    # 模式类 —— 带模式后缀
    ("mode", "智能模式 [已确认]", F + "SetModes.Smart",
     {"smartModeSwitch": {"value": 1}}, "mini"),
    ("mode", "速冷模式 [已确认]", F + "SetModes.QuickCooling",
     {"quickCoolingModeSwitch": {"value": 1}}, "mini"),
    # 变温空间 —— 0=原鲜 1=0℃养鲜 2=母婴
    ("variation", "变温空间→原鲜(0) [已确认]", F + "SetVariationTempSpaceDrawer",
     {"variationTempSpaceDrawer": {"value": 0}}, "mini"),
    ("variation", "变温空间→0℃养鲜(1) [已确认]", F + "SetVariationTempSpaceDrawer",
     {"variationTempSpaceDrawer": {"value": 1}}, "mini"),
    ("variation", "变温空间→母婴(2) [已确认]", F + "SetVariationTempSpaceDrawer",
     {"variationTempSpaceDrawer": {"value": 2}}, "mini"),

    # ============================================================
    # 兼容性验证：SetTemperature 的"裸名"写法（早期实测也通过）
    # 小程序用带后缀的 .Refrigerator，两种都可用，保留作回归对比
    # ============================================================
    ("temperature", "冷藏设温(裸名写法)", F + "SetTemperature",
     {"refrigeratorSetTemperature": {"value": 6}}, None),

    # ============================================================
    # 未实现 / 待验证 —— 当前不需要，注释保留
    # ============================================================
    # ---- 开关机：用户明确表示当前不需要实现 ----
    # ("power", "开关机 SetPower", F + "SetPower", {"powerStatus": {"value": 1}}, None),

    # ---- 其余模式：本机 layout 有但不实现 ----
    # ("mode", "速冻 SetModes.QuickFrozen", F + "SetModes.QuickFrozen",
    #  {"quickFrozenModeSwitch": {"value": 1}}, None),
    # ("mode", "极冻 SetModes.SuperFrozen", F + "SetModes.SuperFrozen",
    #  {"superFrozenModeSwitch": {"value": 1}}, None),
    # ("mode", "假日 SetModes.Holiday", F + "SetModes.Holiday",
    #  {"holidayModeSwitch": {"value": 1}}, None),

    # ============================================================
    # 待验证：除菌 / 净化（本机 layout 能力名 DegermingSwitch / CleanerSwitch）
    # ============================================================
    ("clean", "除菌 DegermingSwitch 裸名", F + "DegermingSwitch",
     {"degermingSwitch": {"value": 1}}, "mini"),
    ("clean", "除菌 SetDegermingSwitch", F + "SetDegermingSwitch",
     {"degermingSwitch": {"value": 1}}, "mini"),
    ("clean", "除菌 SetCleanerSwitch", F + "CleanerSwitch",
     {"cleanerSwitch": {"value": 1}}, "mini"),

    # ============================================================
    # E. 档位 GearControl —— layout 第 5 列 modelCombFunction:
    #    {"function":"...GearControl.Refrigerator","subFunction":"refrigeratorGear","value":"5"}
    # ============================================================
    ("gear", "冷藏档位 SetRefrigeratorGear", F + "SetRefrigeratorGear",
     {"refrigeratorGear": {"value": 3}}, None),
    ("gear", "冷冻档位 SetFreezerGear", F + "SetFreezerGear",
     {"freezerGear": {"value": 3}}, None),
    ("gear", "档位 SetGearControl", F + "SetGearControl", {"refrigeratorGear": {"value": 3}}, None),

    # ============================================================
    # F. 补水 WaterSupply —— layout 第 21 列 modelCombFunction:
    #    {"function":"...WaterSupply","subFunction":"SuperWater"}
    # ============================================================
    ("water", "补水 SetWaterSupply.SuperWater", F + "SetWaterSupply",
     {"waterSupply": {"value": "SuperWater"}}, None),
    ("water", "补水 SetWaterSupply.GoldWater", F + "SetWaterSupply",
     {"waterSupply": {"value": "GoldWater"}}, None),
    ("water", "补水 SetWaterSupply.MicroWater", F + "SetWaterSupply",
     {"waterSupply": {"value": "MicroWater"}}, None),
    ("water", "补水 SetWaterSupply.Off", F + "SetWaterSupply",
     {"waterSupply": {"value": "Off"}}, None),

    # ============================================================
    # G. 制冰 / 养鲜灯 / 静音
    # ============================================================
    ("misc", "制冰 SetIceMakerSwitch", F + "SetIceMakerSwitch",
     {"iceMakerSwitch": {"value": 1}}, None),
    ("misc", "养鲜灯 SetWillLightSwitch", F + "SetWillLightSwitch",
     {"willLightSwitch": {"value": 1}}, None),
    ("misc", "静音 SetQuietModeSwitch", F + "SetQuietModeSwitch",
     {"quietModeSwitch": {"value": 1}}, None),
    ("misc", "AI节能 SetAIEcoSwitch", F + "SetAIEcoSwitch",
     {"aIecoSwitch": {"value": 1}}, None),
    ("misc", "谷电化霜 SetValleyElectricityDefrostingSwitch",
     F + "SetValleyElectricityDefrostingSwitch",
     {"valleyElectricityDefrostingSwitch": {"value": 1}}, None),

    # ============================================================
    # H. 其他变温抽屉（非本机，本机用 VariationTempSpace 见顶部）
    #    本机 states 键 variationTempSpaceDrawer 的取值映射：
    #      原鲜 OriginalFresh1=0 / 0°养鲜 FreshFood1=1 / 母婴 Infant1=2
    #    （已在顶部"已确认"区）
    # ============================================================

    # ============================================================
    # I. 其他抽屉 Drawer.* —— 依据 layout 第 12 列，均未验证
    # ============================================================
    ("drawer", "变温抽屉 SetVariationTemperature", F + "SetVariationTemperature",
     {"variationTemperature": {"value": 2}}, None),
    ("drawer", "真空抽屉 SetVacuum", F + "SetVacuum", {"vacuum": {"value": 1}}, None),
    ("drawer", "干湿抽屉 SetWet", F + "SetWet", {"wet": {"value": 1}}, None),
    ("drawer", "生鲜抽屉 SetFresh", F + "SetFresh", {"fresh": {"value": 1}}, None),
    ("drawer", "珍品抽屉 SetGem", F + "SetGem", {"gem": {"value": 1}}, None),
]


# ============================================================
# 冰箱告警码表 —— 与 `alarmStateCodeList` 的取值一一对应
# 来源：小程序 layout 抓包"异常消息"列的 modelCombFunction.subFunction
# 命名空间：connector.device.function.Alarm.Fridge
# ============================================================
ALARM_CODES = {
    "wideOpenDoorAlarm":       "宽温室门未关",
    "freezeOpenDoorAlarm":     "冷冻室门未关",
    "refriOpenDoorAlarm":      "冷藏室门未关",
    "variaOpenDoorAlarm":      "变温室门未关",
    "freezeOverTempAlarm":     "冷冻室超温",
    "variaOverTempAlarm":      "变温室超温",
    "refriOverTempAlarm_high": "冷藏室超温(偏高)",
    "refriOverTempAlarm_low":  "冷藏室超温(偏低)",
    "wideOverTempAlarm":       "宽温室超温",
    "freezeLeftOpenDoorAlarm": "冷冻门未关严",
    "refriLeftOpenDoorAlarm":  "冷藏门未关严",
    "iceMakerWaterLackAlarm":  "制冰储水盒缺水",
    "mildOdorAlarm":           "冷藏室轻微异味",
    "severeOdorAlarm":         "冷藏室气味过大",
}

# 报警查询接口（URL 待用户补充请求体后确认）
ALARM_PATH = "/4.0/iot/devices/alarm/state"


def alarm_body(token, cid, did, pid) -> str:
    """报警状态查询请求体 —— 依据小程序抓包结构，路径/字段仍待核实。"""
    return dump({"appVersion": CONTROL_APP_VERSION,
                 "header": {"messageId": str(uuid.uuid4())},
                 "payload": {"customerId": str(cid), "partnerId": str(pid),
                             "deviceId": str(did), "sourceType": READ_SOURCE_TYPE},
                 "appType": 2, "sourceName": CONTROL_SOURCE_NAME,
                 "accessToken": token})


def show_alarms() -> None:
    print("冰箱告警码表（alarmStateCodeList 取值）：\n")
    for code, text in ALARM_CODES.items():
        print(f"  {code:<28} -> {text}")
    print()


# ---------------- 加解密 ----------------

def encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    padding = 16 - len(raw) % 16
    cipher = Cipher(algorithms.AES(_PORTAL_APP_SECRET.encode("ascii")),
                    modes.CBC(_PORTAL_AES_IV))
    enc = cipher.encryptor()
    return base64.b64encode(enc.update(raw + bytes([padding]) * padding) + enc.finalize()).decode("ascii")


def sign(body: str) -> str:
    return base64.b64encode(hashlib.md5((body + _PORTAL_APP_SECRET).encode()).digest()).decode("ascii")


def dump(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def ts() -> int:
    return int(time.time() * 1000)


def stringify(value):
    if isinstance(value, dict):
        return {str(k): stringify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [stringify(i) for i in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return value


def post(path: str, body: str) -> dict:
    req = request.Request(
        f"{BASE_URL}{path}", data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "Accept": "application/json", "User-Agent": "okhttp/4.10.0",
                 "appKey": _PORTAL_APP_KEY, "X-Sign-For": sign(body)},
        method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        return {"httpCode": exc.code, "body": exc.read().decode("utf-8", "replace")}


def read_body(token, cid, extra=None) -> str:
    payload = {"customerId": str(cid), "sourceType": READ_SOURCE_TYPE}
    payload.update(extra or {})
    return dump({"lastUpdateTime": 0, "accessToken": token, "appVersion": "", "openId": "",
                 "version": "1.0", "deviceType": 2, "appType": 100, "versionCode": "101",
                 "adaptertRank": 720, "_": ts(), "header": {"messageId": str(uuid.uuid4())},
                 "payload": payload})


def execute_body(token, cid, did, pid, command, params, source_name) -> str:
    """构造 execute 请求体。

    source_name 取值：
      None / CONTROL_SOURCE_NAME  -> dev 分支风格（sourceType=20, appType=1）
      "mini"                      -> 小程序风格（sourceType=21, sourceName=miniProgram, appType=2）
    """
    if source_name == "mini":
        payload = {"sourceType": MINI_SOURCE_TYPE, "sourceName": MINI_SOURCE_NAME,
                   "customerId": str(cid), "deviceId": str(did), "partnerId": str(pid),
                   "actions": [{"command": command, "params": stringify(params)}]}
        return dump({"accessToken": token, "_t": ts(), "deviceId": str(did),
                     "header": {"messageId": f"mini_aiot-{ts()}-probe",
                                "timestamp": ts(), "languageId": 0},
                     "appVersion": MINI_APP_VERSION, "appType": MINI_APP_TYPE,
                     "payload": payload})
    return dump({"appVersion": CONTROL_APP_VERSION,
                 "header": {"messageId": str(uuid.uuid4())},
                 "payload": {"exclusionFlag": 1, "sourceType": CONTROL_SOURCE_TYPE,
                             "customerId": str(cid), "partnerId": str(pid),
                             "deviceId": str(did),
                             "actions": [{"command": command, "params": stringify(params)}]},
                 "appType": 1, "sourceName": source_name or CONTROL_SOURCE_NAME,
                 "accessToken": token})


def verdict(body) -> tuple[str, str]:
    """返回 (判定, 说明)。"""
    if not isinstance(body, dict):
        return "?", "响应非 JSON"
    payload = body.get("payload") or {}
    status = payload.get("status")
    err = payload.get("errorCode")
    desc = payload.get("errorDesc", "")
    if status == "SUCCESS":
        return "SUCCESS", "命令被接受"
    if err == "notSupported":
        return "notSupported", "command 名不存在"
    if err == "commandDuplicate":
        return "commandDuplicate", "键名撞车，需改用扁平驼峰键"
    if err == "invalidParam" or err == "paramError":
        return "paramError", "command 名对，但 params 结构不对"
    return str(err or status or "?"), desc[:80]


# ---------------- 登录 ----------------

def login(username, password):
    body = dump({"loginName": encrypt(username), "signature": encrypt(password),
                 "serverCode": "9501", "distributeId": "2001", "termType": 2})
    req = request.Request(
        f"{PORTAL_URL}?lastUpdateTime=0&version=1.0&deviceType=2&appType=100"
        f"&versionCode=101&adaptertRank=720&_={ts()}",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "appKey": _PORTAL_APP_KEY, "X-Sign-For": sign(body)},
        method="POST")
    with request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    data = result.get("data") or {}
    if data.get("resultCode") != 0:
        print("!! 登录失败:", dump(result)[:400])
        return None
    info = data.get("tokenInfo") or {}
    cid = info.get("customerId") or data.get("customerId") or result.get("customerId")
    return info.get("token"), info.get("refreshToken"), str(cid)


def find_fridge(token, cid):
    homes = ((post("/4.0/iot/home/list", read_body(token, cid)).get("payload") or {})
             .get("homes") or [])
    for home in homes:
        hid = str(home.get("id") or home.get("homeId"))
        devs = ((post("/4.0/iot/devices/list", read_body(token, cid, {"homeId": hid}))
                 .get("payload") or {}).get("devices") or [])
        for d in devs:
            blob = " ".join(str(v or "") for v in (
                d.get("categoryCode"), d.get("deviceTypeName"))).lower()
            if "refrigerat" in blob or "fridge" in blob or "冰箱" in blob:
                partner = d.get("partner") or {}
                pid = str(partner.get("id") or d.get("partnerId") or "1001")
                return d, pid
    return None, None


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    # --only / --try 带参数，需从 positional 里剔除它们的值
    username = positional[0] if positional else os.environ.get("HISENSE_USER", "")
    password = positional[1] if len(positional) > 1 else os.environ.get("HISENSE_PASS", "")

    if "--list" in flags:
        print("内置候选命令表：\n")
        for group, desc, cmd, params, src in COMMAND_CANDIDATES:
            print(f"  [{group:<11}] {desc}")
            print(f"                command = {cmd}")
            print(f"                params  = {dump(stringify(params))}")
            print()
        return

    if "--alarms" in flags:
        show_alarms()
        return

    if not username or not password:
        print(__doc__)
        sys.exit(1)

    tokens = login(username, password)
    if not tokens:
        sys.exit(1)
    token, _, cid = tokens
    print(f"登录 OK  customerId={cid}")

    device, pid = find_fridge(token, cid)
    if not device:
        print("!! 未找到冰箱设备")
        sys.exit(1)
    did = str(device.get("deviceId"))
    print(f"冰箱: {device.get('product', {}).get('name')}  deviceId={did[:40]}...  partnerId={pid}")

    # ---- 自定义单条 ----
    if "--try" in flags:
        i = sys.argv.index("--try")
        command = sys.argv[i + 1]
        params = json.loads(sys.argv[i + 2]) if i + 2 < len(sys.argv) else {}
        print(f"\n自定义命令: {command}")
        print(f"params    : {dump(params)}")
        r = post("/4.0/iot/devices/execute", execute_body(token, cid, did, pid, command, params, None))
        v, note = verdict(r)
        print(f"结果      : {v}  ({note})")
        print(f"原始      : {dump(r)[:400]}")
        return

    # ---- 批量 ----
    if "--run" not in flags:
        print("\n未指定 --run，只做只读检查。加 --run 才会真实下发命令。")
        print("或先用 --list 查看内置候选。")
        return

    only = None
    if "--only" in flags:
        i = sys.argv.index("--only")
        only = sys.argv[i + 1]

    targets = [c for c in COMMAND_CANDIDATES if not only or c[0] == only]
    print(f"\n将下发 {len(targets)} 条候选命令（会真实操作设备）")
    input(">>> 按回车开始（Ctrl+C 取消）...")

    wins = []
    for group, desc, cmd, params, src in targets:
        print(f"\n  [{group}] {desc}")
        print(f"      {cmd}  {dump(stringify(params))}")
        r = post("/4.0/iot/devices/execute", execute_body(token, cid, did, pid, cmd, params, src))
        v, note = verdict(r)
        mark = "  <<< 可用" if v == "SUCCESS" else ""
        print(f"      => {v}  ({note}){mark}")
        if v == "SUCCESS":
            wins.append((group, desc, cmd, params))

    print("\n" + "=" * 60)
    print(f"成功 {len(wins)} 条：")
    for group, desc, cmd, params in wins:
        print(f"  [{group}] {cmd}  {dump(stringify(params))}")
    print("=" * 60)
    print("提示: commandDuplicate = 键名撞车(改用扁平驼峰键);")
    print("      notSupported    = command 名不对;")
    print("      paramError      = command 对但 params 结构不对。")


if __name__ == "__main__":
    main()
