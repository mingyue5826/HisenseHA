#!/usr/bin/env python3
"""AIHome API 探针 —— 用你的海信爱家账号跑一遍，看冰箱在 AIHome 下的数据结构与可控命令。

用法:
    # 只读：登录 + 家庭/设备列表 + detail（打印 named states 全量）
    python aihome-probe.py <用户名> <密码>

    # 只读 + 保存 detail 原始 JSON 到文件（便于交给 AI 分析）
    python aihome-probe.py <用户名> <密码> --save

    # 控制探测：逐个尝试推测的冰箱命令，打印真实响应，判断哪些命令能被接受
    python aihome-probe.py <用户名> <密码> --control

    # 指定设备（多设备时）
    python aihome-probe.py <用户名> <密码> --device <deviceId>

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

# --- 从上游 pyhisenseapi.py 还原的常量（加解密已逐字节核对通过）---
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


# ---------------- 加解密 ----------------

def encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    padding = 16 - len(raw) % 16
    cipher = Cipher(
        algorithms.AES(_PORTAL_APP_SECRET.encode("ascii")),
        modes.CBC(_PORTAL_AES_IV),
    )
    enc = cipher.encryptor()
    return base64.b64encode(enc.update(raw + bytes([padding]) * padding) + enc.finalize()).decode("ascii")


def sign(body: str) -> str:
    """X-Sign-For = base64(md5(加密后的 body + secret))。"""
    return base64.b64encode(hashlib.md5((body + _PORTAL_APP_SECRET).encode("utf-8")).digest()).decode("ascii")


def dump(obj) -> str:
    """必须无空格，否则签名不匹配。"""
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


# ---------------- HTTP ----------------

def post(path: str, body: str, *, verbose=False) -> dict:
    if verbose:
        print(f"    >> POST {BASE_URL}{path}")
        print(f"    >> X-Sign-For: {sign(body)}")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "okhttp/4.10.0",
            "appKey": _PORTAL_APP_KEY,
            "X-Sign-For": sign(body),
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        return {"httpCode": exc.code, "body": exc.read().decode("utf-8", "replace")}


def read_body(token: str, cid: str, extra: dict | None = None) -> str:
    payload = {"customerId": str(cid), "sourceType": READ_SOURCE_TYPE}
    payload.update(extra or {})
    return dump({
        "lastUpdateTime": 0, "accessToken": token, "appVersion": "", "openId": "",
        "version": "1.0", "deviceType": 2, "appType": 100, "versionCode": "101",
        "adaptertRank": 720, "_": ts(),
        "header": {"messageId": str(uuid.uuid4())},
        "payload": payload,
    })


def execute_body(token, cid, device_id, partner_id, command, params,
                 source_name=CONTROL_SOURCE_NAME) -> str:
    return dump({
        "appVersion": CONTROL_APP_VERSION,
        "header": {"messageId": str(uuid.uuid4())},
        "payload": {
            "exclusionFlag": 1, "sourceType": CONTROL_SOURCE_TYPE,
            "customerId": str(cid), "partnerId": str(partner_id),
            "deviceId": str(device_id),
            "actions": [{"command": command, "params": stringify(params)}],
        },
        "appType": 1,
        "sourceName": source_name,
        "accessToken": token,
    })


def ok(body) -> bool:
    return (isinstance(body, dict)
            and body.get("httpCode") not in (401, 403)
            and (body.get("payload") or {}).get("status") == "SUCCESS")


def summarize(body) -> str:
    if not isinstance(body, dict):
        return str(body)[:200]
    payload = body.get("payload") or {}
    parts = [
        f"httpCode={body.get('httpCode')}",
        f"status={payload.get('status')}",
        f"resultCode={payload.get('resultCode')}",
        f"errorCode={payload.get('errorCode')}",
    ]
    msg = payload.get("message") or body.get("message")
    if msg:
        parts.append(f"message={msg}")
    return " ".join(p for p in parts if not p.endswith("None"))


# ---------------- 设备类型 ----------------

def classify(device: dict) -> str:
    product = device.get("product") or {}
    blob = " ".join(str(v or "") for v in (
        device.get("categoryCode"), device.get("deviceTypeName"),
        product.get("name"), product.get("code"),
    )).lower()
    if "aircondition" in blob or "air_condition" in blob or "空调" in blob:
        return "空调"
    if "refrigerat" in blob or "fridge" in blob or "冰箱" in blob:
        return "冰箱"
    if "washer" in blob or "washing" in blob or "洗衣" in blob:
        return "洗衣机"
    if "dryer" in blob or "干衣" in blob or "烘干" in blob:
        return "干衣机"
    return "未识别"


# ---------------- 登录 ----------------

def login(username: str, password: str):
    body = dump({
        "loginName": encrypt(username), "signature": encrypt(password),
        "serverCode": "9501", "distributeId": "2001", "termType": 2,
    })
    req = request.Request(
        f"{PORTAL_URL}?lastUpdateTime=0&version=1.0&deviceType=2&appType=100"
        f"&versionCode=101&adaptertRank=720&_={ts()}",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "appKey": _PORTAL_APP_KEY, "X-Sign-For": sign(body),
        },
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    data = result.get("data") or {}
    if data.get("resultCode") != 0:
        print("!! 登录失败:", dump(result)[:500])
        return None
    info = data.get("tokenInfo") or {}
    cid = info.get("customerId") or data.get("customerId") or result.get("customerId")
    return info.get("token"), info.get("refreshToken"), str(cid)


# ---------------- 控制探测 ----------------

# 每条: (说明, command, params, source_name)
FRIDGE_PROBES = [
    ("开关机 Power(On)", "connector.device.command.Power",
     {"onAndOff": {"code": "On"}}, POWER_SOURCE_NAME),
    ("冷藏设温 refrigeratorSetTemperature", "connector.device.command.SetTemperature",
     {"refrigeratorSetTemperature": {"value": 6}}, None),
    ("冷藏设温 setTemperature.refrigerator", "connector.device.command.SetTemperature",
     {"setTemperature.refrigerator": {"value": 6}}, None),
    ("冷冻设温 freezeSetTemperature", "connector.device.command.SetTemperature",
     {"freezeSetTemperature": {"value": -17}}, None),
    ("冷冻设温 setTemperature.freeze", "connector.device.command.SetTemperature",
     {"setTemperature.freeze": {"value": -17}}, None),
    ("智能模式 SetWorkMode.Smart", "connector.device.command.SetWorkMode",
     {"workMode.Smart": {"value": 1}}, None),
    ("速冷模式 SetWorkMode.QuickCooling", "connector.device.command.SetWorkMode",
     {"workMode.QuickCooling": {"value": 1}}, None),
    ("除菌 SetDegermingSwitch", "connector.device.command.SetDegermingSwitch",
     {"degermingSwitch": {"value": 1}}, None),
]


def probe_controls(token, cid, device, partner_id):
    print()
    print("#" * 70)
    print("# 控制命令探测（会向设备真实下发命令！）")
    print("#" * 70)
    print("说明：每条命令独立尝试，只打印响应，不做状态断言。")
    print("      如果某条返回 SUCCESS，说明该 command + params 组合被云端接受。")
    print("      建议一边跑一边看冰箱/App 是否真的变化，以确认命令语义。")
    print()
    input(">>> 按回车开始探测（Ctrl+C 取消）...")

    did = str(device.get("deviceId"))
    for desc, command, params, source_name in FRIDGE_PROBES:
        body = execute_body(token, cid, did, partner_id, command, params, source_name or CONTROL_SOURCE_NAME)
        print(f"  [{desc}]")
        print(f"      command = {command}")
        print(f"      params  = {dump(stringify(params))}")
        result = post("/4.0/iot/devices/execute", body)
        print(f"      结果    : {summarize(result)}")
        print(f"      原始    : {dump(result)[:300]}")
        print()


# ---------------- 主流程 ----------------

def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    device_filter = None
    if "--device" in sys.argv:
        i = sys.argv.index("--device")
        if i + 1 < len(sys.argv):
            device_filter = sys.argv[i + 1]

    username = argv[0] if argv else os.environ.get("HISENSE_USER", "")
    password = argv[1] if len(argv) > 1 else os.environ.get("HISENSE_PASS", "")
    if not username or not password:
        print(__doc__)
        sys.exit(1)

    print("=" * 70)
    print("1) 登录")
    print("=" * 70)
    tokens = login(username, password)
    if not tokens:
        sys.exit(1)
    token, render, cid = tokens[0], tokens[1], tokens[2]
    print(f"  accessToken  : {token[:24]}...({len(token)} chars)")
    print(f"  refreshToken : {(render or '')[:24]}...")
    print(f"  customerId   : {cid}")

    print()
    print("=" * 70)
    print("2) 家庭列表  POST /4.0/iot/home/list")
    print("=" * 70)
    homes_body = post("/4.0/iot/home/list", read_body(token, cid))
    if not ok(homes_body):
        print("  失败:", dump(homes_body)[:600])
        sys.exit(1)
    homes = (homes_body.get("payload") or {}).get("homes") or []
    for home in homes:
        print(f"  - {home.get('id') or home.get('homeId')}  {home.get('name') or home.get('homeName')}")

    found_fridge = None
    for home in homes:
        home_id = str(home.get("id") or home.get("homeId"))
        print()
        print("=" * 70)
        print(f"3) 设备列表  POST /4.0/iot/devices/list  homeId={home_id}")
        print("=" * 70)
        dev_body = post("/4.0/iot/devices/list", read_body(token, cid, {"homeId": home_id}))
        if not ok(dev_body):
            print("  失败:", dump(dev_body)[:600])
            continue
        for device in (dev_body.get("payload") or {}).get("devices") or []:
            did = str(device.get("deviceId") or "")
            dtype = classify(device)
            product = device.get("product") or {}
            partner = device.get("partner") or {}
            partner_id = str(partner.get("id") or device.get("partnerId") or "1001")
            print(f"  - [{dtype}] {device.get('deviceName') or device.get('name') or device.get('nickname')}")
            print(f"      deviceId  = {did}")
            print(f"      wifiId    = {device.get('wifiId')}")
            print(f"      partnerId = {partner_id}")
            print(f"      category  = {device.get('categoryCode')}")
            print(f"      product   = {product.get('name')} / {product.get('code')}")

            if device_filter and did != device_filter:
                continue

            print()
            print(f"4) 设备详情  POST /4.0/iot/devices/detail")
            detail = post("/4.0/iot/devices/detail", read_body(token, cid, {
                "deviceId": did, "partnerId": partner_id,
            }))

            payload = detail.get("payload") or {}
            node = payload.get("device") or {}
            states = node.get("states") or payload.get("states")

            if flags & {"--save"}:
                out = f"detail_{did.replace(':', '_')}.json"
                with open(out, "w", encoding="utf-8") as fh:
                    json.dump(detail, fh, ensure_ascii=False, indent=2)
                print(f"  >>> 原始响应已保存: {out}")

            if isinstance(states, dict) and states:
                print(f"  >>> named states（共 {len(states)} 个）:")
                for key in sorted(states):
                    print(f"        {key:<34} = {states[key]}")
            else:
                print("  >>> !! 无 named states")
                raw = next((n.get("deviceStatus") for n in (states, node, payload)
                            if isinstance(n, dict) and n.get("deviceStatus") is not None), None)
                print(f"      deviceStatus = {str(raw)[:400]}")

            if dtype == "冰箱":
                found_fridge = (device, partner_id)

    if found_fridge and ("--control" in flags):
        probe_controls(token, cid, found_fridge[0], found_fridge[1])
    elif "--control" in flags:
        print("\n!! 未找到冰箱设备，跳过控制探测")

    print()
    print("=" * 70)
    print("完成。")
    print("  - 只读结果请重点看 named states")
    print("  - 若已跑 --control，请对照冰箱实际变化确认命令语义")
    print("=" * 70)


if __name__ == "__main__":
    main()
