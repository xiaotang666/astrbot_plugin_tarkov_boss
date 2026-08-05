# 更新日志

## v1.2.1 (2026-08-04)

### 修复
- metadata.yaml name 从 `tarkov-boss` 改为 `tarkov_boss`（合法Python标识符）
- @register name 同步修改，与 metadata.yaml 保持一致


## v1.2.0 (2026-08-04)

### 新增
- Boss详情查询：血量（按部位）、掉落物品、战局专属物品
- 出生时间信息（开局即刷 / 延迟秒数）
- 从API获取Boss详细数据（bosses查询）
- tfind指令现显示完整Boss档案

### 移除
- 移除 thelp 帮助指令（由其他插件替代）

### 优化
- 分离地图查询和Boss查询的API缓存
- 地图模糊匹配改进（去除空格比较）

## v1.1.0 (2026-08-04)

### 新增
- 支持 PvE 和 Regular 两种游戏模式查询
- 新增 tmode 指令设置默认模式
- 显示Boss刷新点位置和护卫信息
- 5分钟API缓存

### 修复
- 修复GraphQL查询结构（boss { name } 替代 name）
- 修复422状态码错误

## v1.0.0 (初始版本)

- 基础Boss刷新率查询
- 中英文地图/Boss名翻译
