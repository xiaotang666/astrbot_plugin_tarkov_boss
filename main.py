# main.py
import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger


@register("tarkov_boss", "xiaotang01", "查询塔科夫各模式Boss刷新率与详情", "1.2.3")
class TarkovBossPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self._config = dict(config)
        self.api_url = "https://json.tarkov.dev"
        self.timeout = self._config.get("timeout", 15)
        self._cache = {}
        self._cache_ttl = 300

    # ==================== 指令 ====================

    @filter.command("tboss", alias=["boss", "boss查询", "boss刷率", "查boss", "查刷率"])
    async def cmd_boss_all(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "all"):
            yield r

    @filter.command("tmap", alias=["map", "地图boss", "地图查询", "查地图"])
    async def cmd_boss_map(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "map"):
            yield r

    @filter.command("tfind", alias=["find", "找boss", "boss在哪", "查具体boss"])
    async def cmd_boss_find(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "find"):
            yield r

    @filter.command("tmode", alias=["mode", "模式", "切换模式", "t模式"])
    async def cmd_mode(self, event: AstrMessageEvent, args: str = ""):
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
                    yield event.plain_result("❌ Tarkov API暂时不可用，请稍后再试")
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
                    yield event.plain_result("❌ Tarkov API暂时不可用，请稍后再试")
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
                data = await self._fetch_maps(mode)
                if not data:
                    yield event.plain_result("❌ Tarkov API暂时不可用，请稍后再试")
                    return
                yield event.plain_result(self._fmt_find(data, boss_name, mode))

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
        """从 JSON REST API 获取地图和Boss数据"""
        cache_key = f"maps_{mode}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        url = f"{self.api_url}/{mode}/maps"
        headers = {"Accept": "application/json", "User-Agent": "AstrBot-TarkovBoss/1.2.3"}
        last_err = None

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as resp:
                        body = await resp.text()
                        if resp.status == 200:
                            raw = json.loads(body)
                            result = raw.get("data", raw)
                            self._cache[cache_key] = (time.time(), result)
                            return result
                        else:
                            last_err = f"HTTP {resp.status}: {body[:200]}"
                            await asyncio.sleep(2)
                            continue
            except asyncio.TimeoutError:
                last_err = "请求超时"
                await asyncio.sleep(1)
                continue
            except Exception as e:
                last_err = str(e)
                await asyncio.sleep(1)
                continue

        logger.error(f"Tarkov API重试3次失败: {last_err}")
        if cached:
            logger.warning("使用缓存数据")
            return cached[1]
        return None

    # ==================== 数据处理 ====================

    def _get_maps_list(self, data: Dict) -> List[Dict]:
        """将 API 返回的 maps dict 转为 list，并关联 mob 数据"""
        maps_raw = data.get("maps", {})
        mobs_raw = data.get("mobs", {})

        if isinstance(maps_raw, list):
            return maps_raw

        maps = []
        for map_id, map_data in maps_raw.items():
            map_data["_id"] = map_id
            # 关联 boss 的 mob 信息
            for boss in map_data.get("bosses", []):
                mob_id = boss.get("mob", "")
                mob = mobs_raw.get(mob_id, {})
                boss["_mob_name"] = mob.get("name", mob_id)
                boss["_mob_normalized"] = mob.get("normalizedName", "")
                boss["_mob_health"] = mob.get("health", [])
                # 关联 escort 的 mob 信息
                for escort in boss.get("escorts", []):
                    e_mob_id = escort.get("mob", "")
                    e_mob = mobs_raw.get(e_mob_id, {})
                    escort["_mob_name"] = e_mob.get("name", e_mob_id)
            maps.append(map_data)
        return maps

    # ==================== 格式化 ====================

    def _fmt_all(self, data: Dict, mode: str) -> str:
        maps = self._get_maps_list(data)
        if not maps:
            return "❌ 没有获取到地图数据"
        mode_cn = "PvE" if mode == "pve" else "普通"
        lines = [f"📊 塔科夫Boss刷新率 [{mode_cn}]", "━" * 24]
        for m in sorted(maps, key=lambda x: x.get("name", "")):
            bosses = m.get("bosses", [])
            if not bosses:
                continue
            map_cn = self._tr_map(m.get("name", ""))
            lines.append(f"\n🗺️ {map_cn}")
            for bs in sorted(bosses, key=lambda x: x.get("_mob_name", "")):
                cn = self._tr_boss(bs.get("_mob_name", ""))
                pct = bs.get("spawnChance", 0) * 100
                lines.append(f"  👾 {cn}: {pct:.0f}%")
        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev JSON API")
        return "\n".join(lines)

    def _fmt_map(self, data: Dict, map_name: str, mode: str) -> str:
        maps = self._get_maps_list(data)
        if not maps:
            return "❌ 没有获取到地图数据"

        target = self._find_map(maps, map_name)
        if not target:
            avail = [self._tr_map(m.get("name", "")) for m in maps if m.get("bosses")]
            return f"❌ 未找到地图: {map_name}\n📌 可用: {' / '.join(avail)}"

        mode_cn = "PvE" if mode == "pve" else "普通"
        map_cn = self._tr_map(target.get("name", ""))
        bosses = target.get("bosses", [])
        lines = [f"🗺️ {map_cn} Boss [{mode_cn}]", "━" * 24]

        if not bosses:
            lines.append("  该地图无Boss刷新")
        else:
            for bs in sorted(bosses, key=lambda x: x.get("_mob_name", "")):
                cn = self._tr_boss(bs.get("_mob_name", ""))
                pct = bs.get("spawnChance", 0) * 100
                line = f"👾 {cn}: {pct:.0f}%"

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

                escorts = bs.get("escorts", [])
                if escorts:
                    e_parts = []
                    for e in escorts:
                        en = self._tr_boss(e.get("_mob_name", ""))
                        amts = e.get("amount", [])
                        if amts:
                            e_parts.append(f"{en}x{amts[0].get('count', 1)}")
                    if e_parts:
                        line += f"\n   🛡️ {', '.join(e_parts)}"

                lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev JSON API")
        return "\n".join(lines)

    def _fmt_find(self, data: Dict, boss_name: str, mode: str) -> str:
        maps = self._get_maps_list(data)
        if not maps:
            return "❌ 没有获取到地图数据"

        mode_cn = "PvE" if mode == "pve" else "普通"
        boss_name_lower = boss_name.lower().strip()

        found_maps = []
        found_boss_cn = None
        found_boss_health = []

        for m in maps:
            for bs in m.get("bosses", []):
                mob_name = bs.get("_mob_name", "")
                mob_norm = bs.get("_mob_normalized", "")
                if self._match(mob_name, mob_norm, boss_name_lower):
                    found_boss_cn = self._tr_boss(mob_name)
                    found_boss_health = bs.get("_mob_health", [])
                    found_maps.append({
                        "map_cn": self._tr_map(m.get("name", "")),
                        "chance": bs.get("spawnChance", 0),
                        "locations": bs.get("spawnLocations", []),
                        "escorts": bs.get("escorts", []),
                    })

        if not found_maps:
            all_bosses = set()
            for m in maps:
                for bs in m.get("bosses", []):
                    all_bosses.add(self._tr_boss(bs.get("_mob_name", "")))
            return f"❌ 未找到Boss: {boss_name}\n📌 可用: {' / '.join(sorted(all_bosses))}"

        lines = [f"🔍 {found_boss_cn} [{mode_cn}]", "━" * 24]

        # 血量信息
        if found_boss_health:
            hp_parts = []
            total_hp = 0
            for hp in found_boss_health:
                part = hp.get("bodyPart", "")
                val = hp.get("max", 0)
                total_hp += val
                hp_parts.append(f"{self._tr_body_part(part)}{val}")
            lines.append(f"❤️ 总血量: {total_hp}")
            lines.append(f"   {' | '.join(hp_parts)}")

        # 地图信息
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
                    en = self._tr_boss(e.get("_mob_name", ""))
                    amts = e.get("amount", [])
                    if amts:
                        e_parts.append(f"{en}x{amts[0].get('count', 1)}")
                if e_parts:
                    line += f"\n   🛡️ {', '.join(e_parts)}"

            lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev JSON API")
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

    def _match(self, mob_name: str, mob_norm: str, query: str) -> bool:
        q = query.replace(" ", "")
        cn = self._tr_boss(mob_name).lower().replace(" ", "")
        return (q == mob_name.lower().replace(" ", "") or
                q == mob_norm.lower().replace(" ", "") or
                q == cn or q in cn)

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
