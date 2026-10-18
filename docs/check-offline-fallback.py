"""离线降级自检：不需要 Home Assistant，也不需要连冰箱。

用法::

    python docs/check-offline-fallback.py                 # 用 docs/api-samples 里的真实抓包
    python docs/check-offline-fallback.py 自己的detail.json

它验证五件事：

1. 在线时能把 states 正常解析成内部字段；
2. 设备离线（``onlineStatus="0"``）时只更新 ``online``，**不**用云端缓存覆盖
   温度/告警/故障，也**不**改写"本机支持哪些告警"的结论；
3. 重新上线后以云端真实值覆盖；
4. 实体 ``available`` 只看设备在不在线（``onlineStatus``），云端读取失败时保留
   旧值；以及"还没读到数据也会先把告警实体全建出来，机型明确不支持（``--``）时
   unavailable 并在实体注册表里禁用，键缺失只 unavailable、不禁用"；
5. ``reportTime``（上次数据更新时间）在线、离线都能正确记录。

依赖：``cryptography``（导入集成模块时用到）。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = ROOT / "custom_components" / "hisense"
DEFAULT_SAMPLE = ROOT / "docs" / "api-samples" / "detail-响应体.json"

FAILED: list[str] = []


def check(condition: bool, message: str) -> None:
    """记录一条断言结果，失败不中断（一次跑完能看到所有问题）。"""
    if condition:
        print(f"  ✓ {message}")
    else:
        print(f"  ✗ {message}")
        FAILED.append(message)


def load_package_module(name: str):
    """把集成目录当成包加载，绕开 __init__.py 的 homeassistant 依赖。"""
    full_name = f"hispkg.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def install_ha_stubs() -> None:
    """最小化伪造 homeassistant，只为单独加载 entity.py。"""

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

        def __class_getitem__(cls, item):
            return cls

    class DataUpdateCoordinator:
        def __class_getitem__(cls, item):
            return cls

    class UpdateFailed(Exception):
        pass

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})

    util = types.ModuleType("homeassistant.util")
    util.slugify = lambda value: re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")

    # coordinator 现在记录「上次成功读取的本地时刻」，用得到 dt_util.utcnow。
    from datetime import datetime as _datetime, timezone as _timezone

    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.utcnow = lambda: _datetime.now(_timezone.utc)
    dt_mod.parse_datetime = lambda value: None
    dt_mod.DEFAULT_TIME_ZONE = _datetime.now().astimezone().tzinfo
    util.dt = dt_mod

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.update_coordinator = update_coordinator

    ha = types.ModuleType("homeassistant")
    ha.helpers = helpers
    ha.core = core
    ha.util = util

    for name, module in (
        ("homeassistant", ha),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.update_coordinator", update_coordinator),
        ("homeassistant.core", core),
        ("homeassistant.util", util),
        ("homeassistant.util.dt", dt_mod),
    ):
        sys.modules[name] = module


def install_binary_sensor_stubs() -> None:
    """最小化伪造 homeassistant.components.binary_sensor，只为加载 binary_sensor.py。"""

    class BinarySensorEntity:
        pass

    class BinarySensorEntityDescription:
        def __init__(self, **kwargs):
            self.entity_category = kwargs.get("entity_category")
            for key, value in kwargs.items():
                setattr(self, key, value)

    class BinarySensorDeviceClass:
        PROBLEM = "problem"
        CONNECTIVITY = "connectivity"
        POWER = "power"
        RUNNING = "running"

    module = types.ModuleType("homeassistant.components.binary_sensor")
    module.BinarySensorEntity = BinarySensorEntity
    module.BinarySensorEntityDescription = BinarySensorEntityDescription
    module.BinarySensorDeviceClass = BinarySensorDeviceClass

    components = types.ModuleType("homeassistant.components")
    components.binary_sensor = module

    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.binary_sensor"] = module

    # binary_sensor.py 还会 import entity_registry 用来禁用机型不支持的实体。
    # 自检不跑真实注册表，这里给一个可替换的 holder，供 6b 段注入假注册表。
    class RegistryEntryDisabler:
        DEVICE = "device"
        INTEGRATION = "integration"
        USER = "user"

    registry = types.ModuleType("homeassistant.helpers.entity_registry")
    registry.RegistryEntryDisabler = RegistryEntryDisabler
    registry.holder = {}
    registry.async_get = lambda hass: registry.holder["registry"]

    helpers = sys.modules["homeassistant.helpers"]
    helpers.entity_registry = registry
    sys.modules["homeassistant.helpers.entity_registry"] = registry


def load_states(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("payload") or {}
    device = payload.get("device") or {}
    states = device.get("states") or payload.get("states")
    if not isinstance(states, dict) or not states:
        raise SystemExit(f"{path} 里找不到 payload.device.states")
    return states


def main() -> int:
    sample = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE
    states = load_states(sample)
    print(f"样本：{sample}")
    print(f"states 键数：{len(states)}，onlineStatus={states.get('onlineStatus')!r}\n")

    _pkg = types.ModuleType("hispkg")
    _pkg.__path__ = [str(PKG_DIR)]
    sys.modules["hispkg"] = _pkg
    api = load_package_module("pyhisenseapi")

    client = api.HiSenseFridge.__new__(api.HiSenseFridge)
    client.status = {}
    client._pending_status = {}

    # --- 1. 在线 ---------------------------------------------------------
    print("[1] 在线解析")
    client._update_from_states(states)
    online_status = dict(client.status)
    supported_alarms = set(online_status.get("unsupported_alarms") or [])
    check(client.status.get("online") is True, "online=True")
    check(online_status.get("alarm_states") is not None, "解析出告警位")

    # --- 2. 在线且确实有告警 + 故障 --------------------------------------
    print("\n[2] 在线告警态")
    alarming = dict(states)
    alarming["refriOpenDoorAlarm"] = "1"
    alarming["tempSensorFault"] = "1"
    client._update_from_states(alarming)
    alarm_before = dict(client.status["alarm_states"])
    faults_before = list(client.status["active_faults"])
    check(client.status.get("alarm") is True, "聚合告警为 True")
    check(client.status.get("fault") is True, "聚合故障为 True")

    # --- 3. 离线 ---------------------------------------------------------
    print("\n[3] 设备离线（云端把其余键写成 --/0）")
    offline = {key: "--" for key in states}
    offline.update(
        {
            "onlineStatus": "0",
            "refrigeratorSetTemperature": "5",
            "freezeSetTemperature": "-18",
            "compressorFrequency": "0",
            "dBDDegerming": "0",
        }
    )
    fresh = client._update_from_states(offline)
    check(client.status.get("online") is False, "记录 online=False")
    check(fresh == {"online"}, f"只更新 online（实际 {sorted(fresh)}）")
    check(client.status["alarm_states"] == alarm_before, "告警位未被云端缓存改写")
    check(client.status.get("alarm") is True, "离线不把「门未关」吞成正常")
    check(client.status["active_faults"] == faults_before, "故障未被清空")
    check(
        set(client.status["unsupported_alarms"]) == supported_alarms,
        "「支持哪些告警」的结论未被离线污染",
    )
    check(
        client.status["refrigerator_temperature"]
        == online_status["refrigerator_temperature"],
        "温度未被离线时的缓存值覆盖",
    )

    # --- 4. 恢复在线 -----------------------------------------------------
    print("\n[4] 恢复在线")
    client._update_from_states(dict(states))
    check(client.status.get("online") is True, "online=True")
    check(client.status["alarm_states"] == online_status["alarm_states"], "以云端真实值覆盖")
    check(client.status.get("alarm") is False, "告警回落到样本真实值")

    # --- 5. 机型不报 onlineStatus ----------------------------------------
    print("\n[5] 机型不报 onlineStatus")
    no_online = {k: v for k, v in states.items() if k != "onlineStatus"}
    other = api.HiSenseFridge.__new__(api.HiSenseFridge)
    other.status = {}
    other._pending_status = {}
    other._update_from_states(no_online)
    check("online" not in other.status, "缺键不推断为离线")
    check(other.status.get("refrigerator_temperature") is not None, "其余字段照常解析")

    # --- 6. 实体 available ------------------------------------------------
    print("\n[6] 实体 available")
    install_ha_stubs()
    load_package_module("pyhisenseapi")
    entity = load_package_module("entity")

    class FakeCoordinator:
        def __init__(self, data, success):
            self.data = data
            self.last_update_success = success
            self.device_type = "冰箱"
            self.client = types.SimpleNamespace(
                device_id="dev", get_status=lambda: dict(data or {})
            )

    class Probe(entity.HisenseEntity):
        pass

    def available(data, success=True, offline_entity=False):
        probe = Probe(FakeCoordinator(data, success), "u", "o")
        probe._attr_available_offline = offline_entity
        return probe.available

    check(available({"online": True}) is True, "在线 + 读取成功 → 可用")
    check(available({"online": False}) is False, "设备离线 → 不可用")
    check(
        available({"online": True}, success=False) is True,
        "云端读取失败 → 保留旧值，实体仍可用",
    )
    check(
        available({}, success=False) is True,
        "读取失败且不报 online → 同样不影响",
    )
    check(available({}) is True, "不报 online 的机型 → 照常可用")
    check(
        available({"online": False}, offline_entity=True) is True,
        "连通性实体在设备离线时仍可用",
    )
    check(
        available({"online": True}, success=False, offline_entity=True) is True,
        "连通性实体在断网时仍可用",
    )

    # --- 6b. 告警实体：先全建，机型不支持才 unavailable -------------------
    install_binary_sensor_stubs()
    bs = load_package_module("binary_sensor")

    created: list = []
    coordinator = FakeCoordinator({}, True)
    bs._add_fridge_entities(coordinator, created.extend)
    check(
        len(created) == 4 + len(bs.ALARM_KEYS),
        f"首次读取前就建出全部实体（{len(created)} 个）",
    )

    def flag_sensor(status, key, success=True):
        desc = next(d for d in bs.FRIDGE_FLAG_DESCRIPTIONS if d.key == key)
        return bs.HisenseFridgeFlagSensor(FakeCoordinator(status, success), desc)

    check(
        flag_sensor({"degerming_active": True}, "degerming_active").is_on is True,
        "除菌状态实体（只读）随 dBDDegerming 变为 on",
    )
    check(
        flag_sensor({"degerming_active": None}, "degerming_active").available is False,
        "机型不报除菌位 → 状态实体不可用（而不是显示 off）",
    )
    check(
        flag_sensor({"degerming_active": True}, "degerming_active", False).is_on
        is True,
        "云端读取失败 → 除菌状态保留上次读到的值（不硬说成 off）",
    )

    def alarm(status):
        desc = bs._fridge_alarm_description("refriOpenDoorAlarm")
        return bs.HisenseFridgeAlarmSensor(FakeCoordinator(status, True), desc)

    def alarm_available(status):
        return alarm(status).available

    check(alarm_available({}) is True, "支持性未知 → 实体可用（状态 unknown）")
    check(
        alarm_available({"alarm_states": {"refriOpenDoorAlarm": False}}) is True,
        "机型上报该告警位 → 可用",
    )
    check(
        alarm_available({"unsupported_alarms": ["refriOpenDoorAlarm"]}) is False,
        "机型明确不支持（--） → 不可用，并写入注册表禁用",
    )
    check(
        alarm_available({"missing_alarms": ["refriOpenDoorAlarm"]}) is False,
        "键本次缺失 → 不可用，但不禁用（下次完整响应即恢复）",
    )
    check(
        alarm({"unsupported_alarms": ["refriOpenDoorAlarm"]})._unsupported is True,
        "-- 才允许禁用",
    )
    check(
        alarm({"missing_alarms": ["refriOpenDoorAlarm"]})._unsupported is False,
        "缺失不等于不支持，不能据此禁用实体",
    )
    check(
        alarm_available({"online": False}) is False,
        "设备离线 → 告警实体不可用",
    )

    # 禁用：只有 -- 才写注册表，而且不覆盖用户自己的设置
    reg_mod = sys.modules["homeassistant.helpers.entity_registry"]

    class FakeRegistry:
        def __init__(self, disabled_by=None):
            self.entry = types.SimpleNamespace(disabled_by=disabled_by)
            self.updates = []

        def async_get(self, entity_id):
            return self.entry

        def async_update_entity(self, entity_id, **kwargs):
            self.updates.append(kwargs)
            self.entry.disabled_by = kwargs.get("disabled_by")

    fake = FakeRegistry()
    reg_mod.holder["registry"] = fake
    entity = alarm({"unsupported_alarms": ["refriOpenDoorAlarm"]})
    entity.hass = types.SimpleNamespace()
    entity.entity_id = "binary_sensor.alarm_x"
    entity._disable_if_unsupported()
    check(
        fake.updates == [{"disabled_by": "integration"}],
        "明确不支持（--） → 写入注册表禁用（disabled_by=integration）",
    )
    entity._disable_if_unsupported()
    check(len(fake.updates) == 1, "已禁用过的实体不重复写注册表")

    fake_user = FakeRegistry(disabled_by="user")
    reg_mod.holder["registry"] = fake_user
    entity_user = alarm({"unsupported_alarms": ["refriOpenDoorAlarm"]})
    entity_user.hass = types.SimpleNamespace()
    entity_user.entity_id = "binary_sensor.alarm_y"
    entity_user._disable_if_unsupported()
    check(fake_user.updates == [], "用户手动处理过的实体不被覆盖")

    fake_missing = FakeRegistry()
    reg_mod.holder["registry"] = fake_missing
    entity_missing = alarm({"missing_alarms": ["refriOpenDoorAlarm"]})
    entity_missing.hass = types.SimpleNamespace()
    entity_missing.entity_id = "binary_sensor.alarm_z"
    entity_missing._disable_if_unsupported()
    check(fake_missing.updates == [], "键缺失 → 不禁用（下次完整响应即恢复）")

    # --- 7. 上次数据更新时间 ---------------------------------------------
    print("\n[7] reportTime 解析")
    import asyncio

    raw = json.loads(sample.read_text(encoding="utf-8"))
    expected_report_time = (raw.get("payload") or {}).get("device", {}).get("reportTime")

    def make_client(response):
        async def fake_refresh():
            return True

        async def fake_post(*args, **kwargs):
            return response

        c = api.HiSenseFridge.__new__(api.HiSenseFridge)
        c.status = {}
        c._pending_status = {}
        c.session = None
        c.access_token = "token"
        c.customer_id = "1"
        c.device_id = "dev"
        c.partner_id = "1001"
        c.refresh = fake_refresh
        c._post = fake_post
        return c

    if expected_report_time:
        online_client = make_client(raw)
        status = asyncio.run(online_client.check_status())
        check(
            (status or {}).get("report_time") == expected_report_time,
            f"在线时记录 reportTime（{expected_report_time}）",
        )

        parsed = status or {}
        check(
            len(parsed.get("unsupported_alarms") or []) == 11,
            f"样本里 11 个 -- 键记入 unsupported（{len(parsed.get('unsupported_alarms') or [])} 个）",
        )
        check(
            parsed.get("missing_alarms") == [],
            "完整响应没有缺失键",
        )

        partial_raw = json.loads(json.dumps(raw))
        partial_raw["payload"]["device"]["states"].pop("refriOpenDoorAlarm", None)
        partial = asyncio.run(make_client(partial_raw).check_status()) or {}
        check(
            partial.get("missing_alarms") == ["refriOpenDoorAlarm"]
            and "refriOpenDoorAlarm" not in (partial.get("unsupported_alarms") or []),
            "缺失键只进 missing_alarms，不进 unsupported_alarms",
        )

        # 设备离线时 reportTime 停在旧值，但它正是「数据有多旧」的答案，
        # 所以离线降级不该把它一起冻结成上一次在线值。
        offline_raw = json.loads(json.dumps(raw))
        offline_raw["payload"]["device"]["states"] = {
            k: "--" for k in (raw["payload"]["device"].get("states") or {})
        }
        offline_raw["payload"]["device"]["states"]["onlineStatus"] = "0"
        offline_raw["payload"]["device"]["reportTime"] = "2020-01-01 00:00:00"
        offline_client = make_client(offline_raw)
        offline_status = asyncio.run(offline_client.check_status()) or {}
        check(offline_status.get("online") is False, "离线被记录")
        check(
            offline_status.get("report_time") == "2020-01-01 00:00:00",
            "离线时仍更新 reportTime（用于判断数据有多旧）",
        )
    else:
        check(True, "样本无 reportTime，跳过（实体将回退到本地读取时间）")

    print()
    if FAILED:
        print(f"失败 {len(FAILED)} 项：")
        for item in FAILED:
            print(f"  - {item}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
