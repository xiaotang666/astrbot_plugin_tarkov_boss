# 塔科夫Boss刷新率查询插件

AstrBot插件，查询塔科夫(EFT)各模式Boss刷新率与详细信息。

## 功能

- 📊 全图Boss刷新率一览
- 🗺️ 指定地图Boss详情（刷新点、护卫、出生时间）
- 🔍 特定Boss完整档案（血量、掉落、出现地图）
- 🎮 支持 Regular / PvE 两种游戏模式
- 🌐 中英文指令和名称
- ⚡ 5分钟缓存

## 指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `tboss [模式]` | boss, boss查询, boss刷率, 查boss, 查刷率 | 全图Boss刷新率 |
| `tmap <地图> [模式]` | map, 地图boss, 地图查询, 查地图 | 指定地图Boss |
| `tfind <Boss名> [模式]` | find, 找boss, boss在哪, 查具体boss | Boss详情档案 |
| `tmode [模式]` | mode, 模式, 切换模式, t模式 | 设置/查看默认模式 |

## 使用示例

```
tboss              → 全部Boss刷新率
tboss pve          → PvE全部Boss
tmap 海关           → 海关Boss（含刷新点/护卫/出生时间）
tmap customs pve   → PvE模式Customs
tfind 大锤          → Tagilla档案（血量/掉落/出现地图）
find reshala       → Re沙ala档案
tfind 三枪 pve     → PvE模式Shturman
tmode pve          → 设置默认模式为PvE
```

## Boss详情（tfind）

查询特定Boss时会显示：
- ❤️ 各部位血量（头/胸/腹/左臂/右臂/左腿/右腿）
- 💎 战局专属掉落（跳蚤市场不可交易）
- 🎒 普通掉落物品
- 🗺️ 出现地图及刷新率
- 📍 刷新位置
- 🛡️ 护卫信息
- 🕐 出生时间

## 地图名

**中文：** 海关 / 森林 / 灯塔 / 海岸线 / 储备站 / 工厂 / 立交桥 / 街区 / 中心区 / 实验室

**英文：** Customs / Woods / Lighthouse / Shoreline / Reserve / Factory / Interchange / Streets of Tarkov / Ground Zero / The Lab

## 配置

| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| default_mode | string | regular | 默认游戏模式 (regular/pve) |
| timeout | int | 15 | API超时秒数 |

## 数据来源

[Tarkov.dev API](https://tarkov.dev/api/) — 社区GraphQL API

## 版本历史

- v1.2.0 — Boss详情（血量/掉落），移除帮助指令
- v1.1.0 — 支持PvE/Regular模式，缓存，修复422
- v1.0.0 — 初始版本
