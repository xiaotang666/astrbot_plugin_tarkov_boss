# main.py
import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger


@register("tarkov-boss", "xiaotang666", "查询塔科夫各模式Boss刷新率与详情", "1.2.0")
class TarkovBossPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self._config = dict(config)
        self.api_url = "https://api.tarkov.dev/graphql"
        self.timeout = self._config.get("timeout", 15)
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存

    # ==================== 指令 ====================

    @filter.command("tboss", alias=["boss", "boss查询", "boss刷率", "查boss", "查刷率"])
    async def cmd_boss_all(self, event: AstrMessageEvent, args: str = ""):
        """查询所有Boss刷新率"""
        async for r in self._handle(event, args, "all"):
            yield r

    @filter.command("tmap", alias=["map", "地图boss", "地图查询", "查地图"])
    async def cmd_boss_map(self, event: AstrMessageEvent, args: str = ""):
        """查询指定地图的Boss"""
        async for r in self._handle(event, args, "map"):
            yield r

    @filter.command("tfind", alias=["find", "找boss", "boss在哪", "查具体boss"])
    async def cmd_boss_find(self, event: AstrMessageEvent, args: str = ""):
        """查询特定Boss详情"""
        async for r in self._handle(event, args, "find"):
            yield r

    @filter.command("tmode", alias=["mode", "模式", "切换模式", "t模式"])
    async def cmd_mode(self, event: AstrMessageEvent, args: str = ""):
        """设置默认游戏模式"""
        args = args.strip().lower()
        mode_map = {
            "regular": "regular", "普通": "regular", "pvp": "regular",
            "pve": "pve",
        }
        if args in mode_map:
            self._config["default_mode"] = mode_map[args]
            mode_cn = "PvE" if mode_map[args] == "pve" else "普通(PvP)"
            yield event.plain_result(f"✅ 默认模式已设置为: {mode_cn}")
        else:
            cur = self._get_default_mode()
            cur_cn = "PvE" if cur == "pve" else "普通(PvP)"
            yield event.plain_result(
                f"🎮 当前默认模式: {cur_cn}\n\n"
                f"📌 用法: tmode <模式>\n"
                f"  regular / 普通 / pvp — 标准PvP模式\n"
                f"  pve — PvE模式"
            )

    # ==================== 统一处理 ====================

    async def _handle(self, event: AstrMessageEvent, args: str, qtype: str):
        try:
            args = args.strip()
            mode = self._get_default_mode()

            if qtype == "all":
                mode = self._extract_mode(args) or mode
                data = await self._fetch_maps(mode)
                if not data:
                    yield event.plain_result("❌ 获取数据失败，请稍后重试")
                    return
                yield event.plain_result(self._fmt_all(data, mode))

            elif qtype == "map":
                map_name, mode = self._parse_args(args, mode)
                if not map_name:
                    yield event.plain_result(
                        "❌ 请指定地图名\n"
                        "📌 用法: tmap <地图名> [模式]\n"
                        "📖 海关/森林/灯塔/海岸线/储备站/工厂/立交桥/街区/中心区/实验室"
                    )
                    return
                data = await self._fetch_maps(mode)
                if not data:
                    yield event.plain_result("❌ 获取数据失败，请稍后重试")
                    return
                yield event.plain_result(self._fmt_map(data, map_name, mode))

            elif qtype == "find":
                boss_name, mode = self._parse_args(args, mode)
                if not boss_name:
                    yield event.plain_result(
                        "❌ 请指定Boss名\n"
                        "📌 用法: tfind <Boss名> [模式]\n"
                        "📖 大锤/三枪/Re沙拉/Killa/蓝色动力装甲/卡班/葛朗台/黑老登/小鹿"
                    )
                    return
                maps_data, bosses_data = await asyncio.gather(
                    self._fetch_maps(mode), self._fetch_bosses(mode)
                )
                if not maps_data:
                    yield event.plain_result("❌ 获取数据失败，请稍后重试")
                    return
                yield event.plain_result(self._fmt_find(maps_data, bosses_data, boss_name, mode))

        except Exception as e:
            logger.error(f"TarkovBoss异常: {e}")
            yield event.plain_result(f"❌ 查询出错: {str(e)}")

    # ==================== 参数解析 ====================

    def _get_default_mode(self) -> str:
        return self._config.get("default_mode", "regular")

    def _extract_mode(self, args: str) -> Optional[str]:
        if not args:
            return None
        m = {"regular": "regular", "普通": "regular", "pvp": "regular", "pve": "pve"}
        for k, v in m.items():
            if args.strip().lower() == k:
                return v
        return None

    def _parse_args(self, args: str, default_mode: str) -> Tuple[Optional[str], str]:
        if not args:
            return None, default_mode
        parts = args.strip().split()
        mode = default_mode
        name = None
        for p in parts:
            m = self._extract_mode(p)
            if m:
                mode = m
            elif not name:
                name = p
        return name, mode

    # ==================== API ====================

    async def _fetch_maps(self, mode: str) -> Optional[Dict]:
        """获取地图+Boss刷新数据"""
        cache_key = f"maps_{mode}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        query = """
        query($mode: GameMode) {
          maps(gameMode: $mode) {
            name
            normalizedName
            bosses {
              boss {
                id
                name
                normalizedName
              }
              spawnChance
              spawnLocations {
                name
                chance
              }
              escorts {
                boss { name }
                amount { count chance }
              }
              spawnTime
              spawnTimeRandom
            }
          }
        }
        """
        result = await self._gql(query, {"mode": mode})
        if result:
            self._cache[cache_key] = (time.time(), result)
        return result

    async def _fetch_bosses(self, mode: str) -> Optional[List]:
        """获取Boss详细信息（血量、装备、物品）"""
        cache_key = f"bosses_{mode}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        query = """
        query($mode: GameMode) {
          bosses(gameMode: $mode) {
            id
            name
            normalizedName
            health {
              bodyPart
              max
            }
            items {
              name
              shortName
              types
              avg24hPrice
              lastLowPrice
              sellFor { priceRUB }
            }
          }
        }
        """
        result = await self._gql(query, {"mode": mode})
        if result and "bosses" in result:
            boss_list = result["bosses"]
            self._cache[cache_key] = (time.time(), boss_list)
            return boss_list
        return None

    async def _gql(self, query: str, variables: Dict = None) -> Optional[Dict]:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AstrBot-TarkovBoss/1.2.0",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Tarkov API HTTP {resp.status}")
                        return None
                    data = await resp.json()
                    if "errors" in data:
                        logger.error(f"Tarkov API错误: {data['errors']}")
                        return None
                    return data.get("data")
        except asyncio.TimeoutError:
            logger.error("Tarkov API超时")
            return None
        except Exception as e:
            logger.error(f"Tarkov API异常: {e}")
            return None

    # ==================== 格式化：全部Boss ====================

    def _fmt_all(self, data: Dict, mode: str) -> str:
        maps = data.get("maps", [])
        if not maps:
            return "❌ 没有获取到地图数据"
        mode_cn = "PvE" if mode == "pve" else "普通"
        lines = [f"📊 塔科夫Boss刷新率 [{mode_cn}]", "━" * 24]
        for m in sorted(maps, key=lambda x: x.get("name", "")):
            bosses = m.get("bosses", [])
            if not bosses:
                continue
            lines.append(f"\n🗺️ {self._tr_map(m['name'])}")
            for bs in sorted(bosses, key=lambda x: x.get("boss", {}).get("name", "")):
                cn = self._tr_boss(bs["boss"]["name"])
                pct = bs.get("spawnChance", 0) * 100
                lines.append(f"  👾 {cn}: {pct:.0f}%")
        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev API")
        return "\n".join(lines)

    # ==================== 格式化：地图Boss ====================

    def _fmt_map(self, data: Dict, map_name: str, mode: str) -> str:
        maps = data.get("maps", [])
        if not maps:
            return "❌ 没有获取到地图数据"

        target = self._find_map(maps, map_name)
        if not target:
            avail = [self._tr_map(m["name"]) for m in maps if m.get("bosses")]
            return f"❌ 未找到地图: {map_name}\n📌 可用: {' / '.join(avail)}"

        mode_cn = "PvE" if mode == "pve" else "普通"
        map_cn = self._tr_map(target["name"])
        bosses = target.get("bosses", [])
        lines = [f"🗺️ {map_cn} Boss [{mode_cn}]", "━" * 24]

        if not bosses:
            lines.append("  该地图无Boss刷新")
        else:
            for bs in sorted(bosses, key=lambda x: x.get("boss", {}).get("name", "")):
                cn = self._tr_boss(bs["boss"]["name"])
                pct = bs.get("spawnChance", 0) * 100
                line = f"👾 {cn}: {pct:.0f}%"

                # 刷新点
                locs = bs.get("spawnLocations", [])
                if locs:
                    parts = []
                    for loc in locs:
                        n = loc.get("name", "")
                        c = loc.get("chance", 0)
                        if n and c > 0:
                            parts.append(f"{n}({c*100:.0f}%)")
                    if parts:
                        line += f"\n   📍 {', '.join(parts)}"

                # 护卫
                escorts = bs.get("escorts", [])
                if escorts:
                    e_parts = []
                    for e in escorts:
                        en = self._tr_boss(e["boss"]["name"])
                        amts = e.get("amount", [])
                        if amts:
                            e_parts.append(f"{en}x{amts[0]['count']}")
                    if e_parts:
                        line += f"\n   🛡️ {', '.join(e_parts)}"

                # 出生时间
                st = bs.get("spawnTime")
                if st is not None:
                    if st == -1:
                        line += "\n   🕐 开局即刷"
                    else:
                        rnd = "随机" if bs.get("spawnTimeRandom") else ""
                        line += f"\n   🕐 {st}秒{rnd}"

                lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev API")
        return "\n".join(lines)

    # ==================== 格式化：Boss详情 ====================

    def _fmt_find(self, maps_data: Dict, bosses_data: Optional[List], boss_name: str, mode: str) -> str:
        maps = maps_data.get("maps", [])
        if not maps:
            return "❌ 没有获取到地图数据"

        mode_cn = "PvE" if mode == "pve" else "普通"
        boss_name_lower = boss_name.lower().strip()

        # 从地图数据中找Boss出现信息
        found_maps = []
        found_boss_cn = None
        found_boss_id = None
        for m in maps:
            for bs in m.get("bosses", []):
                b = bs.get("boss", {})
                if self._match_boss(b, boss_name_lower):
                    found_boss_cn = self._tr_boss(b["name"])
                    found_boss_id = b.get("id")
                    found_maps.append({
                        "map_cn": self._tr_map(m["name"]),
                        "chance": bs.get("spawnChance", 0),
                        "locations": bs.get("spawnLocations", []),
                        "escorts": bs.get("escorts", []),
                        "spawnTime": bs.get("spawnTime"),
                        "spawnTimeRandom": bs.get("spawnTimeRandom"),
                    })

        if not found_maps:
            all_bosses = set()
            for m in maps:
                for bs in m.get("bosses", []):
                    all_bosses.add(self._tr_boss(bs["boss"]["name"]))
            return f"❌ 未找到Boss: {boss_name}\n📌 可用: {' / '.join(sorted(all_bosses))}"

        lines = [f"🔍 {found_boss_cn} [{mode_cn}]", "━" * 24]

        # 如果有boss详细数据，显示血量和掉落
        boss_detail = None
        if bosses_data and found_boss_id:
            for b in bosses_data:
                if b.get("id") == found_boss_id:
                    boss_detail = b
                    break

        if boss_detail:
            # 血量信息
            health = boss_detail.get("health", [])
            if health:
                hp_parts = []
                total_hp = 0
                for hp in health:
                    part = hp.get("bodyPart", "")
                    val = hp.get("max", 0)
                    total_hp += val
                    part_cn = self._tr_body_part(part)
                    hp_parts.append(f"{part_cn}{val}")
                lines.append(f"❤️ 总血量: {total_hp}")
                lines.append(f"   {' | '.join(hp_parts)}")

            # 掉落物品
            items = boss_detail.get("items", [])
            if items:
                # 分类：战局专属(noFlea) vs 普通
                no_flea = []
                normal = []
                for item in items:
                    types = item.get("types", [])
                    name = item.get("name", "")
                    if "noFlea" in types:
                        no_flea.append(name)
                    else:
                        normal.append(name)

                if no_flea:
                    lines.append(f"💎 战局专属: {', '.join(no_flea[:10])}")
                if normal:
                    lines.append(f"🎒 普通掉落: {', '.join(normal[:10])}")

        # 地图刷新信息
        lines.append("")
        for entry in found_maps:
            pct = entry["chance"] * 100
            line = f"🗺️ {entry['map_cn']}: {pct:.0f}%"

            locs = entry.get("locations", [])
            if locs:
                parts = []
                for loc in locs:
                    n = loc.get("name", "")
                    c = loc.get("chance", 0)
                    if n and c > 0:
                        parts.append(f"{n}({c*100:.0f}%)")
                if parts:
                    line += f"\n   📍 {', '.join(parts)}"

            escorts = entry.get("escorts", [])
            if escorts:
                e_parts = []
                for e in escorts:
                    en = self._tr_boss(e["boss"]["name"])
                    amts = e.get("amount", [])
                    if amts:
                        e_parts.append(f"{en}x{amts[0]['count']}")
                if e_parts:
                    line += f"\n   🛡️ {', '.join(e_parts)}"

            st = entry.get("spawnTime")
            if st is not None:
                if st == -1:
                    line += "\n   🕐 开局即刷"
                else:
                    rnd = "随机" if entry.get("spawnTimeRandom") else ""
                    line += f"\n   🕐 {st}秒{rnd}"

            lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev API")
        return "\n".join(lines)

    # ==================== 工具函数 ====================

    def _find_map(self, maps: List, name: str) -> Optional[Dict]:
        nl = name.lower().strip().replace(" ", "")
        for m in maps:
            en = m.get("name", "").lower().replace(" ", "")
            norm = m.get("normalizedName", "").lower().replace(" ", "")
            cn = self._tr_map(m.get("name", "")).lower().replace(" ", "")
            if nl == en or nl == norm or nl == cn or nl in cn:
                return m
        return None

    def _match_boss(self, boss: Dict, query: str) -> bool:
        en = boss.get("name", "").lower()
        norm = boss.get("normalizedName", "").lower()
        cn = self._tr_boss(boss.get("name", "")).lower()
        q = query.replace(" ", "")
        return (q == en.replace(" ", "") or q == norm.replace(" ", "") or
                q in cn or q == cn)

    def _tr_map(self, name: str) -> str:
        t = {
            "Customs": "海关", "Woods": "森林", "Lighthouse": "灯塔",
            "Shoreline": "海岸线", "Reserve": "储备站", "Factory": "工厂",
            "Interchange": "立交桥", "Streets of Tarkov": "塔科夫街区",
            "Ground Zero": "中心区", "The Lab": "实验室", "Laboratory": "实验室",
            "Terminal": "码头",
        }
        return t.get(name, name)

    def _tr_boss(self, name: str) -> str:
        t = {
            "Reshala": "Re沙拉", "Killa": "Killa", "Tagilla": "Tagilla",
            "Shturman": "三枪", "Sanitar": "蓝色动力装甲",
            "Glukhar": "大锤", "Kaban": "卡班", "Kollontay": "葛朗台",
            "Knight": "骑士", "Big Pipe": "大根", "Birdeye": "鸟眼",
            "Partisan": "黑老登", "Zryachiy": "小鹿",
            "Cultist Priest": "邪教祭司", "Cultist": "邪教徒",
            "Rogue": "肉鸽", "Raider": "Raider掠夺者",
            "Smuggler": "走私者", "Minotaur": "牛头大锤",
            "Black Division": "黑色军团", "Russian": "俄军",
        }
        return t.get(name, name)

    def _tr_body_part(self, part: str) -> str:
        t = {
            "Head": "头", "Chest": "胸", "Stomach": "腹",
            "LeftArm": "左臂", "RightArm": "右臂",
            "LeftLeg": "左腿", "RightLeg": "右腿",
        }
        return t.get(part, part)

    async def terminate(self):
        self._cache.clear()
