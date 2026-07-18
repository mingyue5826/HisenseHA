# 海信智能家居（HisenseHA）
![Hisense](hisense-electronics.png)

[English](README.md)


面向 **海信（Hisense）** 云端智能设备的 Home Assistant 自定义集成。目前主要支持 **空调**和**冰箱**。若你希望支持更多设备类型，欢迎提交PR共同扩展本集成。



## 环境要求

- **Home Assistant** 2025.6 或更高版本（若使用更旧的核心，请查看[发行说明](https://github.com/manymuch/HisenseHA/releases)）。
- 能在官方手机 App 中正常登录的 **海信账号**（用户名与密码一致）。
- 空调需已在 App 中完成配网，并归属到某个 **家庭**。

## 安装集成

### 方式一：HACS

[![Open your Home Assistant instance and add this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mingyue5826&repository=HisenseHA&category=integration)

点上面的按钮一键添加，或者手动操作：

1. 在 Home Assistant 中打开 **HACS**。
2. 进入 **集成** → 右上角菜单（⋮）→ **自定义仓库**。
3. 添加仓库 `https://github.com/manymuch/HisenseHA`，类别选 **集成（Integration）**。
4. 在 **Hisense Smart Devices** 卡片中点击 **下载**。
5. 按提示 **重启** Home Assistant。

### 方式二：手动安装

1. 将Release中的的文件解压后复制到 Home Assistant 配置目录下：

   `config/custom_components/hisense/`

2. **重启** Home Assistant。

## 添加设备

1. 打开 **设置** → **设备与服务** → **添加集成**。
2. 搜索 **Hisense Smart Devices**（或 **Hisense**）并选择。
3. 输入 **海信 App 的用户名和密码**（若错误会提示认证失败）。
4. 选择包含空调所在的 **家庭**。
5. 勾选要添加的一台或多台 **设备**，完成向导。

## 状态同步

本集成与海信 **云端** 通信。界面上的设备状态 **主要在你对实体执行操作之后** 才会更新（例如调节温度、开关机、改模式等）；并 **不会** 在后台按固定间隔持续拉取整机状态。

每台设备在「诊断」类实体中提供两个按钮：

- **刷新令牌**：向海信服务器用刷新令牌换取新的访问令牌,一般有效期为几个月，且会自动更新，该按钮仅供开发者调试；**不要**无意义地频繁点击。
- **刷新状态**：主动向海信云端 **请求一次当前状态**。每次按下都会产生 **真实的云端访问**，请 **不要** 用自动化做成「每隔几秒/几分钟轮询」，以免海信限流或彻底封禁api端口。

若你需要 **实时状态**，推荐将同一台海信设备 **同时接入米家**，在 Home Assistant 里使用 [XiaomiMiot](https://github.com/al-one/hass-xiaomi-miot) 或 [XiaomiHome](https://github.com/xiaomi/ha_xiaomi_home) 订阅米家侧的状态变化，再通过 **自动化** 在小米实体变化时 **调用本集成对应设备的「刷新状态」按钮**，从而间接同步海信实体。