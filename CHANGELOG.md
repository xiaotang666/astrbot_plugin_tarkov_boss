# 更新日志

## v1.2.5 (2026-08-05)

### 修复
- 地图名改用 MongoDB ID 映射，不再依赖 API 的 name 字段
- 补全 Boss 翻译：bosspartisan→黑老登、bosstagillaagro→Tagilla(狂暴)
- 修复 tr_map/tr_boss 查找逻辑（先精确匹配 ID，再小写匹配）

## v1.2.4 (2026-08-05)

### 修复
- 切换到 json.tarkov.dev REST API（GraphQL 已停服）
- 添加中英文翻译映射表
- metadata.yaml 补全 display_name/repo 字段

## v1.2.3 (2026-08-05)

### 修复
- 增加 API 重试机制（3次）和缓存兜底

## v1.2.2 (2026-08-05)

### 修复
- 简化 GraphQL 查询修复 422 错误

## v1.2.1 (2026-08-04)

### 修复
- metadata.yaml name 从 tarkov-boss 改为 tarkov_boss

## v1.2.0 (2026-08-04)

### 新增
- Boss 详情查询（血量、掉落、出现地图）
- 移除 thelp 帮助指令

## v1.1.0 (2026-08-04)

### 新增
- 支持 PvE/Regular 模式
- tmode 指令设置默认模式

## v1.0.0 (2026-08-04)

- 初始版本
