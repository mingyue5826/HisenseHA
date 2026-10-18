# 接口文档 · AIHome（海信爱家）

> 覆盖本集成用到的全部 AIHome 接口。
> 抓包环境：海信爱家 App `7.0.8.12`、微信小程序 `1.5.6.6`。
> 响应原文见 [`api-samples/`](./api-samples/)。
> 冰箱字段语义见 [`冰箱开发指南.md`](./冰箱开发指南.md)。
>
> **示例值均已脱敏**：`deviceId` / `serialNumber` / `customerId` / `homeId` /
> `room.id` / `token` / `loginName` / `signature` 全部替换为示例值，
> 与任何真实账号无关，直接照抄格式即可。

---

## 通用

### 请求 host

```
https://iot-aihome.hismarttv.com
```

认证接口在另一个 host：`https://portal-account.hismarttv.com`。

### 请求方式

**全部是 `POST`**，参数一律放在 JSON body 里（认证接口的公共参数在 query，见下节）。
没有 GET、没有路径参数。

### 请求头

| 请求头 | 值 | 说明 |
|---|---|---|
| `Content-Type` | `application/json; charset=UTF-8` | 固定 |
| `Accept` | `application/json` | 固定 |
| `User-Agent` | `okhttp/4.10.0` | App 特征，集成照抄 |
| `appKey` | `commonweb` | **固定值**，参与签名 |
| `X-Sign-For` | `base64(MD5(body + appSecret))` | 见下 |

```http
POST /4.0/iot/devices/detail HTTP/1.1
Host: iot-aihome.hismarttv.com
Content-Type: application/json; charset=UTF-8
Accept: application/json
User-Agent: okhttp/4.10.0
appKey: commonweb
X-Sign-For: 9Xb0kQm3jJ7p1sVn2cR8tYwZ4aB6dE0fG2hI4jK6lM8=

{"lastUpdateTime":0,"accessToken":"...","payload":{"customerId":"100000001","sourceType":3,"deviceId":"86xxxxxxxx...","partnerId":"1001"}}
```

### 签名算法

| 项 | 值 |
|---|---|
| 算法 | `base64( MD5( body字符串 + "MORZRbkuiWxjp+SM4vR_GxY4pZxLZ6rn" ) )` |
| 被签名的 `body` | **实际发送的那串 JSON**（不是对象） |
| 硬性要求 | `json.dumps(obj, separators=(",", ":"), ensure_ascii=False)` —— **不能有空格、不能转义中文** |

序列化改了（哪怕多一个空格），签名就对不上，服务端直接拒绝。

### 三种请求体风格

| 风格 | 特征 | 用在哪 |
|---|---|---|
| **读（门户风格）** | `appType:100`、`deviceType:2`、`versionCode:"101"`、`payload.sourceType:3` | `home/list`、`devices/list`、`devices/detail` |
| **控制（App 风格）** | `appType:1`、`payload.sourceType:20`、`sourceName:"smartlifeAppH5"`、`payload.actions[]` | `devices/execute` |
| **配置查询（App 风格）** | `appType:1`、`payload.sourceType:20`、无 `actions` | `function/getHomepageConfig`、`scenes/execute/config/get` |

`appVersion` 服务端**不校验**：集成固定发 `6.2.18.7`，App 实际是 `7.0.8.12`，两者都能成功。

### 两个容易搞混的 `deviceId`

| 位置 | 含义 |
|---|---|
| `payload.deviceId` | **被控设备** ID，形如 `86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1` |
| 顶层 `deviceId` | **App 会话/终端** ID，形如 `86xxxxxx...`，App 抓包里才有，集成不发也能通过 |

### 统一成功判定

```
httpCode not in (401, 403)  and  payload.status == "SUCCESS"
```

`401` / `403` 视为 token 过期，需要重新登录。

---

## 一、认证登录 · `/mobile/se/signon`

独立 host，仅此接口。

### 请求地址

```
POST https://portal-account.hismarttv.com/mobile/se/signon
```

### 请求头

同通用（`Content-Type` / `appKey` / `X-Sign-For`）。

### 请求参数（query）

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `lastUpdateTime` | string | `0` | 固定 |
| `version` | string | `1.0` | 固定 |
| `deviceType` | string | `2` | 固定（手机） |
| `appType` | string | `100` | 固定 |
| `versionCode` | string | `101` | 固定 |
| `adaptertRank` | string | `720` | 屏幕适配等级，固定 |
| `_` | string | `1792279336082` | 毫秒时间戳，防缓存 |

### 请求体

| 字段 | 类型 | 示例 | 说明 |
|---|---|---|---|
| `loginName` | string | `q9K...==` | 账号，**AES 加密后 base64** |
| `signature` | string | `Zx7...==` | 密码，**AES 加密后 base64** |
| `serverCode` | string | `9501` | 固定 |
| `distributeId` | string | `2001` | 固定 |
| `termType` | int | `2` | 固定 |

加密算法：

```
AES-256-CBC
  key = "MORZRbkuiWxjp+SM4vR_GxY4pZxLZ6rn"   (32 字符 → 256 位)
  iv  = key[:16] = "MORZRbkuiWxjp+SM"        (固定 IV)
  padding = PKCS#7（满块也补一整块）
  输出 = base64
```

```json
{"loginName":"q9K...==","signature":"Zx7...==","serverCode":"9501","distributeId":"2001","termType":2}
```

### 响应参数

#### `data`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `data.resultCode` | 结果码 | int | `0` | `0` = 成功，其它为失败 |
| `data.tokenInfo.token` | 访问令牌 | string | `1aos...` | **长期有效**，后续所有接口用 |
| `data.tokenInfo.refreshToken` | 刷新令牌 | string | `...` | 实际不用：刷新 = 用账号密码重新登录 |
| `data.tokenInfo.customerId` | 客户 ID | string | `100000001` | 后续接口 `payload.customerId` 用它 |

### 响应示例

```json
{
  "data": {
    "resultCode": 0,
    "tokenInfo": {
      "token": "1aos...",
      "refreshToken": "",
      "customerId": "100000001"
    }
  }
}
```

> `accessToken` 没有短过期，集成只在 `401/403` 时才重新登录。

---

## 二、家庭列表 · `/home/list`

### 请求地址

```
POST /4.0/iot/home/list
```

### 请求体

读风格（`sourceType = 3`）。

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `lastUpdateTime` | 上次更新时间 | int | `0` | 固定 0，全量 |
| `accessToken` | 访问令牌 | string | `1aos...` | 登录返回 |
| `appVersion` | App 版本 | string | `""` | 读风格填空串 |
| `openId` | 开放 ID | string | `""` | 固定空 |
| `version` | 协议版本 | string | `"1.0"` | 固定 |
| `deviceType` | 设备类型 | int | `2` | 固定（手机） |
| `appType` | App 类型 | int | `100` | 固定 |
| `versionCode` | 版本号 | string | `"101"` | 固定 |
| `adaptertRank` | 适配等级 | int | `720` | 固定 |
| `_` | 时间戳 | int | `1792279336082` | 毫秒 |
| `header.messageId` | 消息 ID | string | uuid4 | 每次随机 |
| `payload.customerId` | 客户 ID | string | `"100000001"` | |
| `payload.sourceType` | 来源类型 | int | `3` | 读接口固定 3 |

```json
{"lastUpdateTime":0,"accessToken":"1aos...","appVersion":"","openId":"","version":"1.0","deviceType":2,"appType":100,"versionCode":"101","adaptertRank":720,"_":1792279336082,"header":{"messageId":"3f1c8a9e-..."},"payload":{"customerId":"100000001","sourceType":3}}
```

### 响应参数

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `payload.status` | 状态 | string | `SUCCESS` | |
| `payload.homes[]` | 家庭列表 | list | | |
| `payload.homes[].id` | 家庭 ID | string | `10000002` | 旧字段名为 `homeId` |
| `payload.homes[].name` | 家庭名 | string | `我的家` | 旧字段名为 `homeName` |

### 响应示例

```json
{
  "header": {"messageId": "h5-native-request-1792279336082", "timestamp": 1792279336082},
  "payload": {
    "status": "SUCCESS",
    "homes": [
      {"id": "10000002", "name": "我的家"}
    ]
  }
}
```

---

## 三、设备列表 · `/devices/list`

### 请求地址

```
POST /4.0/iot/devices/list
```

### 请求体

读风格，`payload` 在家庭列表基础上多一个 `homeId`。

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `payload.homeId` | string | `"10000002"` | 家庭 ID |
| `payload.sourceType` | int | `3` | 固定 |

```json
{"lastUpdateTime":0,"accessToken":"1aos...","appVersion":"","openId":"","version":"1.0","deviceType":2,"appType":100,"versionCode":"101","adaptertRank":720,"_":1792279336082,"header":{"messageId":"3f1c8a9e-..."},"payload":{"customerId":"100000001","sourceType":3,"homeId":"10000002"}}
```

### 响应参数

#### `payload.devices`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `payload.devices[].deviceId` | 设备 ID | string | `86xxxxxxxx...:lb0516...` | 后续所有接口的主键 |
| `payload.devices[].wifiId` | Wi-Fi 模块 ID | string | | 能耗接口用 |
| `payload.devices[].name` | 设备名 | string | `冰箱` | 也可能在 `deviceName` |
| `payload.devices[].categoryCode` | 品类码 | string | `connector.device.type.fridge` | 见下表 |
| `payload.devices[].product.code` | 产品编码 | string | `LB051600602J` | 功能清单接口要用 |
| `payload.devices[].product.name` | 产品型号 | string | `BCD-516WD1FPA-EQ51` | |
| `payload.devices[].partner.id` | 合作方 | string | `1001` | 透传给 `payload.partnerId` |

#### 品类码 `categoryCode`

| 值 | 设备 |
|---|---|
| `connector.device.type.fridge` | 冰箱 |
| `connector.device.type.aircondition` | 空调 |
| `connector.device.type.washer` | 洗衣机 |
| `connector.device.type.dryer` | 干衣机 |

> 集成判断设备类型的兜底方式是产品名关键字（小写匹配）：
> `refrigerat|fridge|冰箱`、`aircondition|air_condition|空调`、
> `washer|washing|洗衣`、`dryer|干衣|烘干`。

### 响应示例

```json
{
  "payload": {
    "status": "SUCCESS",
    "devices": [
      {
        "deviceId": "86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1",
        "wifiId": "lb051600602j0093fe7d2a1",
        "deviceName": "冰箱",
        "categoryCode": "connector.device.type.fridge",
        "product": {"code": "LB051600602J", "name": "BCD-516WD1FPA-EQ51"},
        "partner": {"id": "1001"}
      }
    ]
  }
}
```

---

## 四、设备详情 · `/devices/detail`

读状态的主接口。**状态是命名键值对**，不要解析 `originalState` 数组。

### 请求地址

```
POST /4.0/iot/devices/detail
```

### 请求体

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `payload.customerId` | string | `"100000001"` | |
| `payload.sourceType` | int | `3` | 固定 |
| `payload.deviceId` | string | `"86xxxxxxxx...:lb0516..."` | 目标设备 |
| `payload.partnerId` | string | `"1001"` | 固定 |

```json
{"lastUpdateTime":0,"accessToken":"1aos...","appVersion":"","openId":"","version":"1.0","deviceType":2,"appType":100,"versionCode":"101","adaptertRank":720,"_":1792279336082,"header":{"messageId":"3f1c8a9e-..."},"payload":{"customerId":"100000001","sourceType":3,"deviceId":"86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1","partnerId":"1001"}}
```

### 响应参数

表格从 `payload.device` 开始，祖宗层级省略。

#### `payload.device`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `deviceId` | 设备 ID | string | `86xxxxxxxx...:lb0516...` | |
| `nickname` | 设备别名 | string | `冰箱` | |
| `categoryCode` | 品类码 | string | `connector.device.type.fridge` | |
| `connectionType` | 联网方式 | string | `wifi` | |
| `product.code` | 产品编码 | string | `LB051600602J` | |
| `product.name` | 产品型号 | string | `BCD-516WD1FPA-EQ51` | |
| `deviceInfo.hwVersion` | 硬件版本 | string | `S1807BX.6.03.05.01` | |
| `deviceInfo.swVersion` | 软件版本 | string | `1.0` | |
| `brand.code` / `brand.name` | 品牌 | string | `Ronshen` / `容声` | |
| `states` | 状态字典 | map<string,string> | 见下 | **核心字段**，值是字符串 |
| `reportTime` | 状态上报时间 | string | `2026-10-18 07:48:01` | 设备上报时刻，不是请求时刻 |
| `offlineTime` | 离线时间 | long | `1791918311692` | 毫秒 |
| `labels[]` | 标签 | list | | `key` / `type` / `value` |
| `originalState` | 旧版状态数组 | string | `"6,-16,-40,64,..."` | **废弃，勿解析** |

#### `labels[]`

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `key` | string | `recommendFunctions` | 标签名 |
| `type` | string | `2` | |
| `value` | string | `5254,5224,...` | 逗号分隔 |

已知标签：

| key | 含义 | 能否用于判断能力 |
|---|---|---|
| `appearance` | 外观主题编号 | 否 |
| `recommendFunctions` | 首页推荐位栏目 ID（对应 layout 的 `templateId`） | **否**。同一台机器会同时列出 4 个互斥的除菌系统 |

#### `states`

`map<string, string>`。值只有三种形态：

| 值 | 含义 |
|---|---|
| `"0"` / `"1"` | 布尔位（`0` = 正常/关，`1` = 异常/开） |
| 数字字符串 | 数值（温度、频率、档位） |
| `"--"` | **该键无有效值**。布尔位表示机型不支持；枚举位表示"当前无此状态"（如 `workMode` 无模式运行） |

冰箱 74 个键的逐项说明见 [`冰箱开发指南.md` 第 2 节](./冰箱开发指南.md)。

### 响应示例

```json
{
  "header": {"messageId": "h5-native-request-1792280882508-311972447", "timestamp": 1792280882563, "languageId": 0},
  "payload": {
    "status": "SUCCESS",
    "customerId": "100000001",
    "device": {
      "deviceId": "86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1",
      "nickname": "冰箱",
      "categoryCode": "connector.device.type.fridge",
      "product": {"code": "LB051600602J", "name": "BCD-516WD1FPA-EQ51"},
      "states": {
        "onlineStatus": "1",
        "refrigeratorOn": "1",
        "refrigeratorSetTemperature": "6",
        "refrigeratorRealTemperature": "7",
        "displayTemperature.refrigerator": "5",
        "freezeSetTemperature": "-16",
        "freezeRealTemperature": "-17",
        "displayTemperature.freeze": "-18",
        "workMode": "0",
        "workMode.Smart": "1",
        "workMode.QuickCooling": "0",
        "compressorFrequency": "0",
        "refriOpenDoorAlarm": "0",
        "mildOdorAlarm": "--"
      },
      "reportTime": "2026-10-18 07:48:01"
    }
  }
}
```

> 完整 74 键原文：[`api-samples/detail-响应体.json`](./api-samples/detail-响应体.json)

---

## 五、设备控制 · `/devices/execute`

### 请求地址

```
POST /4.0/iot/devices/execute
```

### 请求体

控制风格。**与读风格的 body 完全不同**，不能复用。

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `appVersion` | App 版本 | string | `"7.0.8.12"` | 不校验，`6.2.18.7` 也可 |
| `appType` | App 类型 | int | `1` | 固定 |
| `sourceName` | 来源名 | string | `"smartlifeAppH5"` | 固定；开机用 `smartlifeApp` |
| `accessToken` | 访问令牌 | string | | |
| `header.messageId` | 消息 ID | string | uuid | |
| `payload.exclusionFlag` | 互斥标志 | int | `1` | 固定 |
| `payload.sourceType` | 来源类型 | int | `20` | 固定 |
| `payload.customerId` | 客户 ID | string | `"100000001"` | |
| `payload.partnerId` | 合作方 | string | `"1001"` | |
| `payload.deviceId` | **被控设备 ID** | string | `86xxxxxxxx...` | |
| `payload.actions[]` | 动作列表 | list | | 可一次多条 |
| `payload.actions[].command` | 命令名 | string | `connector.device.command.SetModes.Smart` | |
| `payload.actions[].params` | 参数 | map | `{"smartModeSwitch":{"value":"1"}}` | **值必须是字符串** |

```json
{
  "appVersion": "7.0.8.12",
  "payload": {
    "exclusionFlag": 1,
    "sourceType": "20",
    "customerId": "100000001",
    "partnerId": "1001",
    "deviceId": "86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1",
    "actions": [
      {
        "params": {"smartModeSwitch": {"value": "1"}},
        "command": "connector.device.command.SetModes.Smart"
      }
    ]
  },
  "appType": "1",
  "header": {"messageId": "2fa32c40-ca85-11f1-9cda-df375bd4562a"},
  "sourceName": "smartlifeAppH5",
  "accessToken": "1aos..."
}
```

> `_stringify`：`bool` / `int` / `float` 一律转字符串。发 `1` 和发 `"1"` 都能通，但按 App 抓包发字符串最稳。

**关闭同一个模式就是把 `value` 改成 `"0"`，其余字段一个不动**（`exclusionFlag` 依然是 `1`）：

```json
{
  "appVersion": "7.0.8.12",
  "payload": {
    "exclusionFlag": 1,
    "sourceType": "20",
    "customerId": "100000001",
    "partnerId": "1001",
    "deviceId": "86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1",
    "actions": [
      {
        "params": {"quickCoolingModeSwitch": {"value": "0"}},
        "command": "connector.device.command.SetModes.QuickCooling"
      }
    ]
  },
  "appType": "1",
  "header": {"messageId": "02ac48f0-ca91-11f1-9cda-df375bd4562a"},
  "sourceName": "smartlifeAppH5",
  "accessToken": "1aos..."
}
```

关闭动作**不会改设定温度**：`refrigeratorSetTemperature` / `freezeSetTemperature` 一直是
用户手动设的值，模式期间被覆盖的只有 `displayTemperature`，所以关掉之后设备自动回到原温度。

### 响应参数

与 `detail` 同构，成功时直接回带最新 `states`，可省一次查询。

| 字段 key | 类型 | 说明 |
|---|---|---|
| `payload.status` | string | `SUCCESS` = 命令已下发 |
| `payload.device.states` | map | 执行后的状态快照 |
| `payload.status` = `FAIL` 时 `payload.errorCode` | string | 见下表 |

### 冰箱已验证命令

| 动作 | command | params |
|---|---|---|
| 冷藏设温 | `connector.device.command.SetTemperature.Refrigerator` | `{"refrigeratorSetTemperature":{"value":"5"}}` |
| 冷冻设温 | `connector.device.command.SetTemperature.Freeze` | `{"freezeSetTemperature":{"value":"-16"}}` |
| 智能模式 开 / 关 | `connector.device.command.SetModes.Smart` | `{"smartModeSwitch":{"value":"1"}}` / `"0"` |
| 速冷模式 开 / 关 | `connector.device.command.SetModes.QuickCooling` | `{"quickCoolingModeSwitch":{"value":"1"}}` / `"0"` |
| 变温空间 | `connector.device.command.SetVariationTempSpaceDrawer` | `{"variationTempSpaceDrawer":{"value":"2"}}` |
| 除菌+净味 开 | `connector.device.command.DBDDegerming` | `{"dBDDegerming":{"value":"1"}}` |
| 除菌+净味 关 | `connector.device.command.DBDDegerming` | `{"dBDDegerming":{"value":"0"}}` |

空调命令见旧版门户文档。

---

## 六、首页功能清单 · `/devices/function/getHomepageConfig`

**按产品型号返回该机型的功能声明**，含命令名、参数键、取值范围、状态映射。

### 请求地址

```
POST /4.0/iot/devices/function/getHomepageConfig
```

### 请求体

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `appVersion` | string | `"7.0.8.12"` | |
| `appType` | string | `"1"` | 字符串 `"1"` |
| `payload.sourceType` | int | `20` | |
| `payload.products[]` | list | | 可传多个产品 |
| `payload.products[].productCode` | string | `LB051600602J` | 来自设备列表或 detail |
| `payload.products[].categoryCode` | string | `connector.device.type.fridge` | |
| `header.messageId` | string | uuid | |
| `accessToken` | string | | |
| `deviceId`（顶层） | string | `86xxxxxx...` | **会话 ID，不是设备 ID** |

```json
{
  "appVersion": "7.0.8.12",
  "payload": {
    "sourceType": 20,
    "products": [
      {"productCode": "LB051600602J", "categoryCode": "connector.device.type.fridge"}
    ]
  },
  "appType": "1",
  "header": {"messageId": "e991bb72-ca81-11f1-9cda-df375bd4562a"},
  "accessToken": "1aos...",
  "deviceId": "86xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### 响应参数

#### `payload.products`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `payload.products[]` | 产品列表 | list<products> | | |
| `products[].categoryCode` | 品类码 | string | `connector.device.type.fridge` | |
| `products[].productCode` | 产品编码 | string | `LB051600602J` | |
| `products[].functions[]` | 功能列表 | list<function> | | 见下 |
| `products[].preferFunctions[]` | 首页展示规则 | list | | 见下 |

#### `functions[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `code` | 功能码 | string | `connector.device.function.Modes.Smart` | |
| `name` | 功能名 | string | `智能模式` | 中文 |
| `desc` | 描述 | string | `""` | 常空 |
| `action` | 可执行动作 | object | | **没有该字段 = 只读** |
| `action.command` | 命令名 | string | `connector.device.command.SetModes.Smart` | 官方写法 |
| `action.params[].attribute` | 参数键 | string | `smartModeSwitch` | |
| `action.params[].optional` | 是否可选 | string | `"1"` | `"0"` = 必填 |
| `attributes[]` | 属性定义 | list | | 取值范围的唯一来源 |
| `states[]` | 状态映射 | list | | `states[].code` → `states[].attribute` |

#### `attributes[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `code` | 属性码 | string | `refrigeratorSetTemperature` | |
| `type` | 数据类型 | string | `1` | 见下表 |
| `suffix` | 单位 | string | `℃` | |
| `step` | 步长 | string | `""` | 常空，按 1 处理 |
| `defaultValue` | 默认值 | string | `2` | |
| `value` | 取值范围 | string / list | `[2,8]` | 数值型是字符串区间，枚举型是对象数组 |

#### `type` 取值 → HA 平台

| type | 取值形态 | 示例 | 对应 HA |
|---|---|---|---|
| `1` | 数值区间字符串 `[min,max]` | `[2,8]` | `number`（有 action）/ `sensor`（无 action） |
| `3` | 布尔枚举 `0/1` | `Off` / `On` | `switch`（有 action）/ `binary_sensor` |
| `4` | 枚举数组 | `Smart` / `QuickCooling` | `select` |

#### 枚举项结构（`type` 为 `3`/`4` 时）

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `value` | string | `"0"` | **下发给设备的原始值** |
| `code` | string | `Smart` | 英文码，可用于程序判断 |
| `name` | string | `智能` | 中文名 |
| `stateName` | string | `智能` | 当前状态文案 |
| `commandName` | string | `智能` | 操作文案 |

#### `preferFunctions[]`

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `priority` | int | `1` | 越小越优先 |
| `conditions` | map | `{"onlineStatus":"1"}` | 满足才展示 |
| `functions[].functionCode` | string | `connector.device.function.Modes.Smart` | 关联 `functions[].code` |
| `functions[].index` | int | `4` | 首页排序位 |
| `functions[].displayType` | int | `1` | `1` = 按钮，`2` = 数值展示 |
| `functions[].displayState` | string | `displayTemperature.refrigerator` | 展示哪个状态 |

> `priority 0` 的条件是 `onlineStatus=0`，只挂 `Online` —— 这就是官方的离线降级规则。

### 本机（`LB051600602J`）功能全集

| 功能码 | 名称 | command | 参数键 | 状态键 |
|---|---|---|---|---|
| `FoodMaterialControl` | 食材管理 | —（无 action） | — | — |
| `Modes.Smart` | 智能模式 | `SetModes.Smart` | `smartModeSwitch` | `workMode.Smart` |
| `Modes.QuickCooling` | 速冷模式 | `SetModes.QuickCooling` | `quickCoolingModeSwitch` | `workMode.QuickCooling` |
| `Modes` | 模式（总） | `SetModes` | `modes` | `workMode` |
| `TemperatureControl.Refrigerator` | 冷藏温度控制 | `SetTemperature.Refrigerator` | `refrigeratorSetTemperature` | `setTemperature.refrigerator`、`displayTemperature.refrigerator` |
| `TemperatureControl.Freeze` | 冷冻温度控制 | `SetTemperature.Freeze` | `freezeSetTemperature` | `setTemperature.freeze`、`displayTemperature.freeze` |
| `RefrigeratorTemperatureControl` | 冷藏温度控制（旧别名） | `SetRefrigeratorTemperature` | `refrigeratorSetTemperature` | `refrigeratorSetTemperature` |
| `FreezeTemperatureControl` | 冷冻温度控制（旧别名） | `SetFreezeTemperature` | `freezeSetTemperature` | `freezeSetTemperature` |
| `Online` | 在线状态 | —（只读） | — | `onlineStatus` |

**同一个功能会以两个名字同时出现**（`TemperatureControl.Refrigerator` 与
`RefrigeratorTemperatureControl`），这是历史遗留，不是两个功能。

### 响应示例

```json
{
  "payload": {
    "status": "SUCCESS",
    "products": [
      {
        "categoryCode": "connector.device.type.fridge",
        "productCode": "LB051600602J",
        "functions": [
          {
            "code": "connector.device.function.Modes.Smart",
            "name": "智能模式",
            "action": {
              "command": "connector.device.command.SetModes.Smart",
              "params": [{"attribute": "smartModeSwitch", "optional": "1"}]
            },
            "attributes": [
              {
                "code": "smartModeSwitch",
                "type": "3",
                "defaultValue": "0",
                "value": [
                  {"value": "0", "code": "Off", "name": "关闭"},
                  {"value": "1", "code": "On", "name": "开启"}
                ]
              }
            ],
            "states": [{"code": "workMode.Smart", "attribute": "smartModeSwitch"}]
          }
        ],
        "preferFunctions": [
          {
            "priority": 0,
            "conditions": {"onlineStatus": "0"},
            "functions": [
              {"functionCode": "connector.device.function.Online", "index": 1, "displayType": 2, "displayState": "onlineStatus"}
            ]
          }
        ]
      }
    ]
  }
}
```

> 完整原文：[`api-samples/homepageConfig-响应体.json`](./api-samples/homepageConfig-响应体.json)

> ⚠️ **这个清单不是完整能力清单**。变温空间、除菌都能在这台机器上正常控制，
> 却都不在首页功能表里（它们不在首页，在"更多"页）。所以：
> **功能表里有 → 一定有；没有 → 不能断定没有。**
> 判断能力优先用它，其次用 `states` 的 `--`，最后靠实测。

---

## 七、场景可执行配置 · `/scenes/execute/config/get`

返回**指定家庭下所有设备可被场景调用的命令**，以及**命令之间的互斥关系**。

### 请求地址

```
POST /4.0/iot/scenes/execute/config/get
```

### 请求体

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `appVersion` | string | `"7.0.8.12"` | |
| `appType` | string | `"1"` | |
| `payload.sourceType` | int | `20` | |
| `payload.customerId` | string | `"100000001"` | |
| `payload.whitelist` | int | `1` | 固定 |
| `payload.homeId` | string | `"10000002"` | 家庭 ID |
| `header.messageId` | string | uuid | |
| `accessToken` | string | | |

```json
{
  "appVersion": "7.0.8.12",
  "payload": {"sourceType": 20, "customerId": "100000001", "whitelist": 1, "homeId": "10000002"},
  "appType": "1",
  "header": {"messageId": "97165090-ca81-11f1-9cda-df375bd4562a"},
  "accessToken": "1aos...",
  "deviceId": "86xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### 响应参数

#### `payload.result.actionDevices`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `deviceId` | 设备 ID | string | | |
| `nickName` | 别名 | string | `冰箱` | |
| `room.id` / `room.name` | 房间 | | `10000003` / `厨房` | |
| `categoryCode` | 品类码 | string | `connector.device.type.fridge` | |
| `states` | 状态字典 | map | | 与 `detail` 的 `states` **完全一致** |
| `commands[]` | 可用命令 | list | | 见下 |
| `conflictCommands[]` | 互斥关系 | list | | 见下 |

#### `commands[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `code` | 命令名 | string | `connector.device.command.SetTemperature.Refrigerator` | |
| `name` | 中文名 | string | `设置冷藏室温度` | |
| `attributes[].code` | 参数键 | string | `refrigeratorSetTemperature` | |
| `attributes[].state` | 关联状态键 | string | `setTemperature.refrigerator` | |
| `attributes[].type` | 数据类型 | string | `1` | 同首页功能清单 |
| `attributes[].value` | 取值范围 | string / list | `[2,8]` | |
| `attributes[].suffix` | 单位 | string | `℃` | |
| `attributes[].displayTemplate` | 展示模板 | string | `${name}${value}${suffix}` | |

#### `conflictCommands[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `srcCommand.code` | 命令 A | string | `connector.device.command.SetModes` | |
| `srcCommand.attributes[].code` | A 的参数键 | string | `modes` | |
| `srcCommand.attributes[].values` | A 的取值 | list | `["0","3","4"]` | 空数组表示"任意值" |
| `allExclusive` | 是否全互斥 | string | `"0"` | |
| `targetCommands[].code` | 命令 B | string | `connector.device.command.SetTemperature.Refrigerator` | |
| `targetCommands[].attributes[].values` | B 的取值 | list | `[]` | |

**语义**：A 与 B **不能同时成立**。表是双向的（A→B 和 B→A 各出现一次）。

### 本机互斥结论

| 命令 | 与 `SetModes` 的哪些取值互斥 |
|---|---|
| `SetTemperature.Refrigerator` | `0`（智能）、`3`（速冷）、`4` |
| `SetTemperature.Freeze` | `0`（智能）、`2`、`6`、`7`、`8`、`9` |
| `SetRefrigeratorGear` | `0`、`3`、`4` |
| `SetFreezerGear` | `0`、`2`、`6`、`7`、`8`、`9` |

实际表现（已实测）：

- **开模式 → 该舱温度被锁定**，此时手调温度不会生效于该舱，除非先退模式。
- **手调温度 → 相关模式自动退出**（冷藏设温退智能+速冷；冷冻设温只退智能）。
- `SetRefrigeratorGear` / `SetFreezerGear` 不在本机 `commands` 里 —— 是别的机型的能力。

### 响应示例

```json
{
  "payload": {
    "status": "SUCCESS",
    "result": {
      "actionDevices": [
        {
          "deviceId": "86xxxxxxxx...",
          "nickName": "冰箱",
          "categoryCode": "connector.device.type.fridge",
          "commands": [
            {
              "code": "connector.device.command.SetModes",
              "name": "设置模式",
              "attributes": [
                {
                  "code": "modes",
                  "state": "workMode",
                  "type": "4",
                  "value": [{"value": "0", "code": "Smart", "name": "智能"}]
                }
              ]
            }
          ],
          "conflictCommands": [
            {
              "srcCommand": {
                "code": "connector.device.command.SetTemperature.Refrigerator",
                "attributes": [{"code": "refrigeratorSetTemperature", "values": [""]}]
              },
              "targetCommands": [
                {
                  "code": "connector.device.command.SetModes",
                  "attributes": [{"code": "smartFridgeModes", "values": ["0", "3", "4"]}]
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

> 完整原文：[`api-samples/scenes-execute-config-响应体.json`](./api-samples/scenes-execute-config-响应体.json)

> ⚠️ 同一份数据里"模式"参数有三个名字：`modes`（命令定义）、`smartFridgeModes`（互斥表）、
> `smartModeSwitch` / `quickCoolingModeSwitch`（单模式开关）。**下发时按具体命令用对应那个，别混。**

---

## 八、智控页面布局 · `/layout/smartHomeApp/control`

返回"智控"页的 UI 描述。**纯展示层**：没有 `command`、没有 `states`、没有数值范围。

### 请求地址

```
POST /4.0/iot/layout/smartHomeApp/control
```

### 请求体

小程序风格，与 App 不同。

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `appType` | string | `"2"` | **注意是 2**（App 是 1） |
| `appVersion` | string | `"1.5.6.6"` | 小程序版本 |
| `payload.sceneCode` | string | `"mainPage"` | 页面标识 |
| `payload.terminalTypeCode` | string | `"001"` | 终端类型 |
| `payload.deviceId` | string | | 目标设备 |
| `payload.sourceType` | int | `20` | |
| `header.messageId` | string | | 小程序用 `mini_aiot-...` 前缀 |

```json
{
  "appType": "2",
  "appVersion": "1.5.6.6",
  "header": {"messageId": "mini_aiot-1792279336082"},
  "accessToken": "1aos...",
  "payload": {
    "sceneCode": "mainPage",
    "terminalTypeCode": "001",
    "sourceType": 20,
    "deviceId": "86100c0090020020000000403a9c5d10:lb051600602j0093fe7d2a1"
  }
}
```

### 响应参数

#### `payload.pageInfo.columns[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `index` | 栏序号 | int | `4` | 1 起 |
| `title` | 栏标题 | string | `温度调节` | 中文 |
| `columnType` | 栏类型 | int | | |
| `templateId` | 模板 ID | string | `5254` | 与 `labels.recommendFunctions` 对应 |
| `briefIntro` | 栏说明 | string | | |
| `tiles[]` | 卡片列表 | list | | 见下 |
| `subColumns[]` | 子栏 | list | | 第 1 栏是嵌套容器 |

#### `tiles[]` / `subTiles[]`

| 字段 key | 字段名 | 类型 | 示例值 | 说明 |
|---|---|---|---|---|
| `typeCode` | 卡片类型 | int | `6` | 见下表 |
| `showInfo.title` | 显示标题 | string | `冷藏室超温` | |
| `showInfo.briefIntro` | 说明文案 | string | | 最有用，可作实体说明 |
| `showInfo.showState` | 状态文案 | string | `""` | 实测 204 个全空 |
| `actionInfo.modelFunction` | 能力名 | string | `connector.device.function.Modes.Smart` | |
| `actionInfo.modeFunction` | 模式名 | string | `Smart` | 仅模式类卡片 |
| `actionInfo.modelCombFunction` | 组合功能 | string(JSON) | 见下 | |

#### `typeCode`

| 值 | 含义 | 数量（本机） |
|---|---|---|
| `1` | 功能入口（可点） | 49 |
| `2` | 纯跳转 | 2 |
| `4` | 模式项 | 11 |
| `6` | 状态 / 告警位 | 56 |
| `7` | 抽屉子档位 | 5 |
| `8` | 分组标题 | 20 |

#### `modelCombFunction`

是一个**被转义的 JSON 字符串**，需要二次 `json.loads`：

```json
"[{\"function\":\"connector.device.function.Alarm.Fridge\",\"subFunction\":\"refriOpenDoorAlarm\",\"value\":\"1\"}]"
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `function` | string | 能力命名空间 |
| `subFunction` | string | **通常等于 `states` 的键名**，也可能是 `execute` 的 params 键 |
| `value` | string | 触发值或档位值 |

#### 能力命名空间一览（本机返回 28 个）

`modelCombFunction.function` 和 `modelFunction` 用的都是这套点号命名，规律是
`connector.device.function.<域>.<能力>`。把前缀去掉后，与 `execute` 的命令名
`connector.device.command.<同一后缀>` 一一对应（少数例外，见
[冰箱开发指南 §3.2](./冰箱开发指南.md)）。

| 命名空间 | 子项数 | 代表中文名 | 本机 `states` 里有无对应键 |
|---|---|---|---|
| `Alarm.Fridge` | 14 | 宽温室门未关告警 | ✅ 14 个告警位都有 |
| `Fault.Fridge` | 12 | 宽温室传感器异常 | ✅ 12 个都有 |
| `Online` | 1 | 离线异常 | ✅ `onlineStatus` |
| `GearControl.Refrigerator` / `GearControl.Freezer` | 各 1 | 冷藏室 / 冷冻室 | ❌ 无档位控制命令 |
| `MoisturizingLightModes` | 3 | 综合营养 | ❌ 无对应键 |
| `model.WillLight` / `WillLight` | 各 1 | 综合营养 / 四季养鲜 | ❌ 无对应键 |
| `WaterSupply` | 4 | 超级补水 | ❌ 无对应键 |
| `Drawer.*`（15 个） | 2~4 | 冰鲜 / 生鲜 / 母婴 / 干货 | ❌ 全是别家机型的抽屉模板 |

`Drawer.*` 那 15 个命名空间（`Vacuum`、`AIVacuum`、`Wet`、`Fresh`、`Gem`、
`PreparedFood`、`VariaTempKeepFresh`、`VariationTemperature`、`MagicSpace`、
`DryWetControl`、`MultiFresh`、`Moisturizing`、`IceTemperature` 等）在本机全部
只是**模板残留**：栏目会被渲染出来，但对应的 `states` 键要么不存在、要么是 `--`。
它们唯一的价值是告诉你"别的机型可能这么命名"。

#### 告警位 · `connector.device.function.Alarm.Fridge`（14 项）

`subFunction` 就是 `states` 的键名，`value: "1"` 表示触发。这段中文文案可直接
作为 HA 实体的 `friendly_name` / 属性说明。

| `states` 键 | 中文名 | App 提示文案 |
|---|---|---|
| `refriOpenDoorAlarm` | 冷藏室门未关告警 | 冷藏室门未关，请及时关闭。 |
| `refriLeftOpenDoorAlarm` | 冷藏门未关严 | 冷藏室温度升高，请检查冷藏室门是否关严，如已解决请忽略。 |
| `freezeOpenDoorAlarm` | 冷冻室门未关警告 | 冷冻室门未关，请及时关闭。 |
| `freezeLeftOpenDoorAlarm` | 冷冻门未关严 | 冷冻室温度升高，请检查冷冻室门是否关严，如已解决请忽略。 |
| `variaOpenDoorAlarm` | 变温室门未关告警 | 变温室门未关，请及时关闭。 |
| `wideOpenDoorAlarm` | 宽温室门未关告警 | 宽温室门未关，建议尽快关闭 |
| `refriOverTempAlarm_high` | 冷藏室超温提醒 | 冷藏室温度过高，请查看解决方案 |
| `refriOverTempAlarm_low` | 冷藏室超温提醒 | 冷藏室温度过高，请查看解决方案 |
| `freezeOverTempAlarm` | 冷冻室超温提醒 | 冷冻室温度过高，请查看解决方案 |
| `variaOverTempAlarm` | 变温室超温提醒 | 变温室温度过高，请查看解决方案 |
| `wideOverTempAlarm` | 宽温室超温提醒 | 宽温室温度过高，请查看解决方案 |
| `iceMakerWaterLackAlarm` | 制冰储水盒缺水 | 制冰储水盒缺水，无法继续制冰，请及时加水 |
| `mildOdorAlarm` | 冷藏室轻微气味告警信息 | 冷藏室检测有轻微异味，请及时处理临过期食材或密封保存气味较大食材 |
| `severeOdorAlarm` | 冷藏室气味过大告警信息 | 冷藏室检测有明显异味，请立即处理过期腐坏食材或密封保存气味较大食材 |

> 注意两个坑：
> 1. `refriOverTempAlarm_high` / `_low` 是两个独立键，而裸名 `refriOverTempAlarm`
>    **不在**字典里（本机恒为 `--`），是旧固件遗留。
> 2. `hydropeniaAlarm` 本机有实值，但字典里查不到，语义未证实。

#### 故障位 · `connector.device.function.Fault.Fridge`（12 项）

官方只定义了 12 个；`states` 里还有 28 个非官方故障键（`wideFanFault`、
`refriFanFault` 等），只能用聚合方式呈现，不单独建实体。

| `states` 键 | 中文名 | App 提示文案 |
|---|---|---|
| `refriSensorFault` | 冷藏室温度传感器故障 | 冷藏室温度传感器异常，建议及时报修 |
| `freezeSensorFault` | 冷冻室温度传感器故障 | 冷冻室温度传感器异常，建议及时报修 |
| `variaSensorFault` | 变温室温度传感器故障 | 变温室温度传感器异常，建议及时报修 |
| `wideSensorFault` | 宽温室传感器异常 | 宽温室温度传感器异常，建议及时报修 |
| `tempSensorFault` | 环境温度故障 | 环境温度传感器异常，建议及时报修 |
| `humiSensorFault` | 环境湿度故障 | 环境湿度传感器异常，建议及时报修 |
| `refriCapillaryCloggingFault` | 冷藏毛细管堵塞故障 | 制冷系统运行异常，建议及时报修，如已解决请忽略。 |
| `freezeCapillaryCloggingFault` | 冷冻毛细管堵塞故障 | 制冷系统运行异常，建议及时报修，如已解决请忽略。 |
| `electricValveSwitchRefriFault` | 电动阀切换冷藏侧故障 | 电动阀运行异常，建议及时报修，如已解决请忽略。 |
| `electricValveSwitchFreezeFault` | 电动阀切换冷冻侧故障 | 电动阀运行异常，建议及时报修，如已解决请忽略。 |
| `refriDamperFault` | 冷藏风门故障 | 冷藏风门运行异常，建议及时报修，如已解决请忽略。 |
| `freezeDefrostingHeaterFault` | 冷冻化霜加热器故障 | 冷冻化霜加热器运行异常，建议及时报修，如已解决请忽略。 |

### 响应示例

```json
{
  "payload": {
    "status": "SUCCESS",
    "pageInfo": {
      "columns": [
        {
          "index": 18,
          "title": "离子除菌净味系统",
          "templateId": "5257",
          "tiles": [
            {
              "typeCode": 1,
              "showInfo": {"title": "离子除菌", "briefIntro": "开启后，将进行除菌净味"},
              "actionInfo": {
                "modelFunction": "connector.device.function.CleanerSwitch,DBDDegerming,DegermingSwitch",
                "modelCombFunction": ""
              }
            }
          ]
        }
      ]
    }
  }
}
```

> 完整原文（6000+ 行）：[`api-samples/layout-control-响应体.json`](./api-samples/layout-control-响应体.json)

### 三份文件，各有各的用处

同一份响应有三层形态，别搞混：

| 文件 | 体积 | 形态 | 用途 |
|---|---|---|---|
| `api-samples/layout-control-响应体.json` | 254 KB / 6000+ 行 | 云端原样，一条没删 | 查原始字段、排查"这个值到底哪来的" |
| `fridge_dictionary.json` | 110 KB | 只留 `alarm_map` + `functions` + `columns` 三块 | **写代码时照着抄中文名和键名** |
| `custom_components/hisense/fridge_const.py` | ~12 KB | 手写常量 | 集成实际使用的唯一来源 |

简化前后的差别（同样的告警，两种表达）：

```jsonc
// 原始响应：信息被埋在 4 层里，且 modelCombFunction 是转义字符串
{
  "payload": {"pageInfo": {"columns": [
    {"index": 1, "title": "异常消息", "subColumns": [
      {"title": "门未关告警", "tiles": [
        {"typeCode": 6,
         "showInfo": {"title": "冷藏室门未关告警", "briefIntro": "冷藏室门未关，请及时关闭。"},
         "actionInfo": {
           "modelFunction": "connector.device.function.Alarm.Fridge",
           "modelCombFunction": "[{\"function\":\"connector.device.function.Alarm.Fridge\",\"subFunction\":\"refriOpenDoorAlarm\",\"value\":\"1\"}]"
         }}
      ]}
    ]}
  ]}}
}
```

```jsonc
// fridge_dictionary.json：拍平成 键 → {命名空间, 中文名, 提示, 触发值}
{
  "alarm_map": {
    "refriOpenDoorAlarm": {
      "namespace": "connector.device.function.Alarm.Fridge",
      "title": "冷藏室门未关告警",
      "briefIntro": "冷藏室门未关，请及时关闭。",
      "activeValue": "1"
    }
  }
}
```

简化版由 [`build_fridge_dictionary.py`](./build_fridge_dictionary.py) 从原始响应生成，
可以用 `--diff` 和代码里的常量做离线比对，检查云端有没有新增/改名。

### ⚠️ 只作开发参考，不参与运行时

集成**不会调用**这个接口。理由有三：

1. **贵**：一次 254 KB、6000+ 行，只为拿几个中文名，而实体的键名是固定的；
2. **不准**：它是产品模板，不是本机硬件清单 —— 本机没有制冰机，
   响应里照样有"制冰开关"栏目；`wideOverTempAlarm` 这一栏也在，但 `states` 值是 `--`；
3. **不稳**：栏目顺序、`templateId`、文案都可能随 App 版本变，跟着它跑等于把
   实体列表交给云端随机决定。

所以正确做法是：**用这份文档 / 简化 json 查一次，把结论写成
`fridge_const.py` 里的常量**，之后运行时只读 `states`。想确认常量有没有过期，
就抓一次新响应跑 `python docs/build_fridge_dictionary.py --diff`，不要在集成里在线比对。

> 同理，`modelCombFunction.subFunction` 也**不能**直接当键值表用：35 组里有 9 组
> 重复或歧义（比如 `willLight` 的 `value=4` 同时是"四季养鲜·春"和"叶绿素"）。
> 详见 [冰箱开发指南 §2.7](./冰箱开发指南.md)。

---

## 九、标签保存 · `/devices/label/batchSave`

保存设备标签（如提示音开关）。走独立结构，不用 `actions`。

### 请求地址

```
POST /4.0/iot/devices/label/batchSave
```

### 请求体

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `accessToken` | string | | |
| `deviceId` | string | | 被控设备 |
| `appVersion` | string | `"6.2.18.7"` | |
| `header.languageId` | int | `0` | |
| `header.messageId` | string | uuid | |
| `header.timestamp` | long | `1792279336082` | 毫秒 |
| `payload.labels[].partnerId` | string | `"1001"` | |
| `payload.labels[].devId` | string | | 同 `deviceId` |
| `payload.labels[].labelKey` | string | `buzzer_sound` | 标签名 |
| `payload.labels[].labelValue` | string | `"1"` | |

```json
{
  "accessToken": "1aos...",
  "deviceId": "86xxxxxxxx...",
  "header": {"languageId": 0, "messageId": "3f1c8a9e-...", "timestamp": 1792279336082},
  "appVersion": "6.2.18.7",
  "payload": {
    "labels": [
      {"partnerId": "1001", "devId": "86xxxxxxxx...", "labelKey": "buzzer_sound", "labelValue": "1"}
    ]
  }
}
```

### 响应参数

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `payload.resultCode` | int | `0` | `0` = 成功（也可能在顶层 `resultCode`） |

### 响应示例

```json
{"payload": {"status": "SUCCESS", "resultCode": 0}}
```

---

## 十、空调今日能耗 · `/smartHome/databoard/aircondition/todayenergy`

扁平参数体，不走任何信封。

### 请求地址

```
POST /4.0/smartHome/databoard/aircondition/todayenergy
```

### 请求体

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `accessToken` | string | | |
| `deviceId` | string | | 空调设备 ID |
| `homeId` | string | `"10000002"` | |
| `partnerId` | string | `"1001"` | |
| `wifiId` | string | | 设备列表里的 `wifiId` |

```json
{"accessToken":"1aos...","deviceId":"86xxxxxxxx...","homeId":"10000002","partnerId":"1001","wifiId":"lb051600602j0093fe7d2a1"}
```

### 响应参数

| 字段 key | 类型 | 示例值 | 说明 |
|---|---|---|---|
| `todayEnergy` | number | `1.23` | 今日用电量（度）；可能嵌在 `data` / `payload` 内 |

> 解析时需向下钻最多 4 层 `data` / `payload` 才能取到。

### 响应示例

```json
{"payload": {"status": "SUCCESS", "data": {"todayEnergy": 1.23, "runTime": 180}}}
```

---

## 附录 A：`execute` 错误码

| `payload.status` / 错误码 | 含义 | 处理 |
|---|---|---|
| `SUCCESS` | 命令已下发 | 成功 |
| `commandDuplicate` | `Matched multiple sub commands.` 命令名前缀匹配到多个子命令 | 改用带后缀全名，或改扁平参数键（`refrigeratorSetTemperature` 而不是 `setTemperature.refrigerator`） |
| `notSupported` | 设备命令表里没有这个命令名 | 换命令名，**不代表设备没这个功能** |
| `paramError` | 参数键或取值不合法 | 命令名对、参数错，改参数。**不会改变设备状态**，可安全试错 |
| `deviceOffline` | 设备离线 | 等设备上线 |

## 附录 B：抓包要点

| 项 | 说明 |
|---|---|
| 渠道 | App（需系统证书）或微信小程序，两者打到同一域、同一命令名 |
| 必须看 | 请求 **body**（命令名、参数键、参数值）+ 请求 URL（决定 `sourceType` / `appType`） |
| 别用 | `originalState` 数组 —— 356 项位置会随固件变，用 `states` |
| 签名 | 抓包里 `X-Sign-For` 无法复用（body 变了签名就变），按算法自己算 |

## 附录 C：还没抓全的第 11 个接口 —— 报警状态查询

小程序进冰箱页时会**并发**发出三个请求（`timestamp` 相差 181 ms），其中一个是独立的
报警查询，不在上面的十个接口里：

```
POST https://iot-aihome.hismarttv.com/4.0/iot/.../alarm/...   ← 路径没抓全
```

响应结构：

```json
{
  "header": {"messageId": "mini_aiot-1791717992880-71e37987", "timestamp": 1791717992702, "languageId": 0},
  "payload": {"status": "SUCCESS", "alarmStateCodeList": []},
  "signatureServer": "cFS2GxwvITYyZJYtPlhrEw=="
}
```

已知：

| 项 | 结论 |
|---|---|
| `alarmStateCodeList` | 空数组 = 当前无告警；有告警时填告警码 |
| 告警码是什么 | 就是 `Alarm.Fridge` 的 `subFunction`（`refriOpenDoorAlarm` 等，14 个，见第八章） |
| 路径 | **不完整**，没抓到十位接口那样的 `/4.0/iot/<模块>/<动作>` |

**没有采用它的原因**：`detail` 的 `states` 里已经带了全部 14 个告警位的 0/1 值，
不需要再多打一个接口。这个接口只在"想知道 App 用哪套码"时有参考价值。

