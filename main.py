# main.py
"""
塔科夫Boss查询插件 v1.2.4
基于 json.tarkov.dev REST API
"""
import aiohttp
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger


# ==================== 中文翻译表 ====================

MAP_TR = {
    # 英文名 → 中文
    "customs": "海关", "woods": "森林", "lighthouse": "灯塔",
    "shoreline": "海岸线", "reserve": "储备站", "factory": "工厂",
    "interchange": "立交桥", "streets of tarkov": "塔科夫街区",
    "ground zero": "中心区", "the lab": "实验室", "laboratory": "实验室",
    "terminal": "码头", "bigmap": "海关", "sandbox": "中心区",
    "sandbox_high": "中心区(高级)", "tarkovstreets": "塔科夫街区",
    "rezervbase": "储备站", "factory4_day": "工厂", "factory4_night": "工厂(夜间)",
    # MongoDB ID → 中文 (JSON API 地图 ID 映射)
    "55f2d3fd4bdc2d5f408b4567": "工厂(夜间)",
    "56f40101d2720b2a4d8b45d6": "海关",
    "5704e3c2d2720bac5b8b4567": "森林",
    "5704e4dad2720bb55b8b4567": "灯塔",
    "5704e554d2720bac5b8b456e": "海岸线",
    "5704e5fad2720bc05b8b4567": "储备站",
    "5714dbc024597771384a510d": "立交桥",
    "5714dc692459777137212e12": "塔科夫街区",
    "59fc81d786f774390775787e": "工厂",
    "5b0fc42d86f7744a585f9105": "实验室",
    "65b8d6f5cdde2479cb2a3125": "中心区",
    "65cc8f81a9aac3e77d0cfd3e": "码头",
    "6733700029c367a3d40b02af": "实验室(暗区)",
    "69af492a4819ea4ba10a69c5": "冰breaker",
    "6a294a5b5eb5f9a1700417b7": "实验室(暗区)",
}

BOSS_TR = {
    "bossbully": "Re沙拉", "bosskilla": "Killa", "bosstagilla": "Tagilla",
    "bosskojaniy": "三枪", "bossboar": "卡班", "bosskolontay": "葛朗台",
    "bossknight": "骑士", "bosszryachiy": "小鹿", "bossgluhar": "大锤",
    "bosssanitar": "蓝色动力装甲", "bossboarsniper": "卡班狙击手",
    "partisan": "黑老登", "bosspartisan": "黑老登",
    "sectantpriest": "邪教祭司", "sectantwarrior": "邪教徒",
    "exusec": "肉鸽", "pmcbot": "PMC", "bossbullyblackdiv": "Re沙拉(黑部门)",
    "bossknightblackdiv": "骑士(黑部门)", "bosswedge": "楔子",
    "bosswedgelab": "楔子(实验室)", "blackdivision": "黑色军团",
    "vsrf": "俄军", "vsrfsniper": "俄军狙击手", "sentry": "哨兵",
    "bosstagillaagro": "Tagilla(狂暴)", "bossbigsentry": "大哨兵",
    "pmcbotblackdiv": "PMC(黑部门)",
}

PART_TR = {
    "Head": "头", "Chest": "胸", "Stomach": "腹",
    "LeftArm": "左臂", "RightArm": "右臂",
    "LeftLeg": "左腿", "RightLeg": "右腿",
}


def tr_map(name: str) -> str:
    """地图名翻译（支持英文名和MongoDB ID）"""
    key = name.strip()
    # 先尝试精确匹配（ID）
    if key in MAP_TR:
        return MAP_TR[key]
    # 再尝试小写匹配（英文名）
    return MAP_TR.get(key.lower(), name)


def tr_boss(name: str) -> str:
    """Boss名翻译（支持内部ID和显示名）"""
    key = name.strip()
    # 先精确匹配
    if key in BOSS_TR:
        return BOSS_TR[key]
    # 再小写匹配
    key_lower = key.lower().replace(" ", "")
    if key_lower in BOSS_TR:
        return BOSS_TR[key_lower]
    return name


def tr_part(part: str) -> str:
    return PART_TR.get(part, part)


# ==================== 插件类 ====================

@register("tarkov_boss", "xiaotang01", "查询塔科夫各模式Boss刷新率与详情", "1.2.4")
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
    async def cmd_all(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "all"):
            yield r

    @filter.command("tmap", alias=["map", "地图boss", "地图查询", "查地图"])
    async def cmd_map(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "map"):
            yield r

    @filter.command("tfind", alias=["find", "找boss", "boss在哪", "查具体boss"])
    async def cmd_find(self, event: AstrMessageEvent, args: str = ""):
        async for r in self._handle(event, args, "find"):
            yield r

    @filter.command("tmode", alias=["mode", "模式", "切换模式", "t模式"])
    async def cmd_mode(self, event: AstrMessageEvent, args: str = ""):
        args = args.strip().lower()
        mm = {"regular": "regular", "普通": "regular", "pvp": "regular", "pve": "pve"}
        if args in mm:
            self._config["default_mode"] = mm[args]
            cn = "PvE" if mm[args] == "pve" else "普通(PvP)"
            yield event.plain_result(f"✅ 默认模式已设置为: {cn}")
        else:
            cur = self._config.get("default_mode", "regular")
            cn = "PvE" if cur == "pve" else "普通(PvP)"
            yield event.plain_result(f"🎮 当前默认模式: {cn}\n📌 用法: tmode <regular/pve>")

    # ==================== 处理 ====================

    async def _handle(self, event, args, qtype):
        try:
            args = args.strip()
            mode = self._config.get("default_mode", "regular")

            if qtype == "all":
                mode = self._parse_mode(args) or mode
                data = await self._fetch(mode)
                if not data:
                    yield event.plain_result("❌ Tarkov API暂时不可用，请稍后再试")
                    return
                yield event.plain_result(self._fmt_all(data, mode))

            elif qtype == "map":
                name, mode = self._parse_args(args, mode)
                if not name:
                    yield event.plain_result("❌ 请指定地图名\n📌 用法: tmap <地图名> [模式]\n📖 海关/森林/灯塔/海岸线/储备站/工厂/立交桥/街区/中心区/实验室")
                    return
                data = await self._fetch(mode)
                if not data:
                    yield event.plain_result("❌ Tarkov API暂时不可用")
                    return
                yield event.plain_result(self._fmt_map(data, name, mode))

            elif qtype == "find":
                name, mode = self._parse_args(args, mode)
                if not name:
                    yield event.plain_result("❌ 请指定Boss名\n📌 用法: tfind <Boss名> [模式]\n📖 大锤/三枪/Re沙拉/Killa/蓝色动力装甲/卡班/葛朗台/黑老登")
                    return
                data = await self._fetch(mode)
                if not data:
                    yield event.plain_result("❌ Tarkov API暂时不可用")
                    return
                yield event.plain_result(self._fmt_find(data, name, mode))

        except Exception as e:
            logger.error(f"TarkovBoss异常: {e}")
            yield event.plain_result(f"❌ 查询出错: {str(e)}")

    # ==================== 参数 ====================

    def _parse_mode(self, args):
        if not args:
            return None
        m = {"regular": "regular", "普通": "regular", "pvp": "regular", "pve": "pve"}
        return m.get(args.strip().lower())

    def _parse_args(self, args, default_mode):
        if not args:
            return None, default_mode
        parts = args.strip().split()
        mode = default_mode
        name = None
        for p in parts:
            m = self._parse_mode(p)
            if m:
                mode = m
            elif not name:
                name = p
        return name, mode

    # ==================== API ====================

    async def _fetch(self, mode: str) -> Optional[Dict]:
        cache_key = f"maps_{mode}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[0] < self._cache_ttl:
            return cached[1]

        url = f"{self.api_url}/{mode}/maps"
        headers = {"Accept": "application/json", "User-Agent": "AstrBot-TarkovBoss/1.2.4"}

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                        body = await resp.text()
                        if resp.status == 200:
                            raw = json.loads(body)
                            result = raw.get("data", raw)
                            self._cache[cache_key] = (time.time(), result)
                            return result
                        else:
                            logger.warning(f"Tarkov API HTTP {resp.status}, 重试{attempt+1}/3")
                            await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Tarkov API异常: {e}, 重试{attempt+1}/3")
                await asyncio.sleep(2)

        if cached:
            logger.warning("使用过期缓存")
            return cached[1]
        return None

    # ==================== 数据解析 ====================

    def _parse(self, data: Dict) -> Tuple[Dict, Dict]:
        """返回 (maps_dict, mobs_dict)，mobs 用于查找 boss 真实名称"""
        maps = data.get("maps", {})
        mobs = data.get("mobs", {})
        return maps, mobs

    def _boss_name(self, mobs: Dict, mob_id: str) -> str:
        """从 mobs 字典获取 boss 真实名称并翻译"""
        mob = mobs.get(mob_id, {})
        name = mob.get("name", mob_id)
        return tr_boss(name)

    def _boss_health(self, mobs: Dict, mob_id: str) -> List:
        mob = mobs.get(mob_id, {})
        return mob.get("health", [])

    # ==================== 格式化 ====================

    def _fmt_all(self, data: Dict, mode: str) -> str:
        maps, mobs = self._parse(data)
        if not maps:
            return "❌ 没有获取到地图数据"

        mode_cn = "PvE" if mode == "pve" else "普通"
        lines = [f"📊 塔科夫Boss刷新率 [{mode_cn}]", "━" * 24]

        for map_id, map_info in sorted(maps.items(), key=lambda x: x[1].get("name", "")):
            bosses = map_info.get("bosses", [])
            if not bosses:
                continue

            map_name = MAP_TR.get(map_id, map_info.get("name", map_id))
            lines.append(f"\n🗺️ {map_name}")

            for bs in bosses:
                mob_id = bs.get("mob", "")
                name = self._boss_name(mobs, mob_id)
                pct = bs.get("spawnChance", 0) * 100
                lines.append(f"  👾 {name}: {pct:.0f}%")

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev")
        return "\n".join(lines)

    def _fmt_map(self, data: Dict, map_name: str, mode: str) -> str:
        maps, mobs = self._parse(data)
        if not maps:
            return "❌ 没有获取到地图数据"

        # 查找地图
        target = None
        target_id = None
        q = map_name.lower().strip().replace(" ", "")
        for mid, minfo in maps.items():
            name = minfo.get("name", mid)
            if (q == name.lower().replace(" ", "") or
                q == MAP_TR.get(mid, name).lower().replace(" ", "") or
                q in MAP_TR.get(mid, name).lower().replace(" ", "")):
                target = minfo
                target_id = mid
                break

        if not target:
            avail = [MAP_TR.get(k, m.get("name", k)) for k, m in maps.items() if m.get("bosses")]
            return f"❌ 未找到地图: {map_name}\n📌 可用: {' / '.join(sorted(set(avail)))}"

        mode_cn = "PvE" if mode == "pve" else "普通"
        map_cn = MAP_TR.get(target_id, target.get("name", target_id))
        bosses = target.get("bosses", [])
        lines = [f"🗺️ {map_cn} Boss [{mode_cn}]", "━" * 24]

        if not bosses:
            lines.append("  该地图无Boss刷新")
        else:
            for bs in bosses:
                mob_id = bs.get("mob", "")
                name = self._boss_name(mobs, mob_id)
                pct = bs.get("spawnChance", 0) * 100
                line = f"👾 {name}: {pct:.0f}%"

                locs = bs.get("spawnLocations", [])
                if locs:
                    parts = [f"{l.get('name','')}({l.get('chance',0)*100:.0f}%)" for l in locs if l.get("name") and l.get("chance", 0) > 0]
                    if parts:
                        line += f"\n   📍 {', '.join(parts)}"

                escorts = bs.get("escorts", [])
                if escorts:
                    ep = []
                    for e in escorts:
                        en = self._boss_name(mobs, e.get("mob", ""))
                        amts = e.get("amount", [])
                        cnt = amts[0].get("count", 1) if amts else 1
                        ep.append(f"{en}x{cnt}")
                    if ep:
                        line += f"\n   🛡️ {', '.join(ep)}"

                lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev")
        return "\n".join(lines)

    def _fmt_find(self, data: Dict, boss_name: str, mode: str) -> str:
        maps, mobs = self._parse(data)
        if not maps:
            return "❌ 没有获取到地图数据"

        mode_cn = "PvE" if mode == "pve" else "普通"
        q = boss_name.lower().strip().replace(" ", "")
        found = []
        found_cn = None
        found_health = []

        for map_id, map_info in maps.items():
            for bs in map_info.get("bosses", []):
                mob_id = bs.get("mob", "")
                mob = mobs.get(mob_id, {})
                mob_name = mob.get("name", mob_id)
                mob_norm = mob.get("normalizedName", "")
                mob_cn = tr_boss(mob_name)

                if (q == mob_name.lower().replace(" ", "") or
                    q == mob_norm.lower().replace(" ", "") or
                    q == mob_cn.lower().replace(" ", "") or
                    q in mob_cn.lower().replace(" ", "")):
                    found_cn = mob_cn
                    found_health = mob.get("health", [])
                    found.append({
                        "map_cn": MAP_TR.get(map_id, map_info.get("name", map_id)),
                        "chance": bs.get("spawnChance", 0),
                        "locations": bs.get("spawnLocations", []),
                        "escorts": bs.get("escorts", []),
                    })

        if not found:
            all_bosses = set()
            for map_info in maps.values():
                for bs in map_info.get("bosses", []):
                    all_bosses.add(self._boss_name(mobs, bs.get("mob", "")))
            return f"❌ 未找到Boss: {boss_name}\n📌 可用: {' / '.join(sorted(all_bosses))}"

        lines = [f"🔍 {found_cn} [{mode_cn}]", "━" * 24]

        # 血量
        if found_health:
            hp_parts = []
            total = 0
            for hp in found_health:
                val = hp.get("max", 0)
                total += val
                hp_parts.append(f"{tr_part(hp.get('bodyPart', ''))}{val}")
            lines.append(f"❤️ 总血量: {total}")
            lines.append(f"   {' | '.join(hp_parts)}")

        lines.append("")
        for entry in found:
            pct = entry["chance"] * 100
            line = f"🗺️ {entry['map_cn']}: {pct:.0f}%"

            locs = entry.get("locations", [])
            if locs:
                parts = [f"{l.get('name','')}({l.get('chance',0)*100:.0f}%)" for l in locs if l.get("name") and l.get("chance", 0) > 0]
                if parts:
                    line += f"\n   📍 {', '.join(parts)}"

            escorts = entry.get("escorts", [])
            if escorts:
                ep = []
                for e in escorts:
                    en = self._boss_name(mobs, e.get("mob", ""))
                    amts = e.get("amount", [])
                    cnt = amts[0].get("count", 1) if amts else 1
                    ep.append(f"{en}x{cnt}")
                if ep:
                    line += f"\n   🛡️ {', '.join(ep)}"

            lines.append(line)

        lines.append("\n" + "━" * 24)
        lines.append("📌 数据来源: tarkov.dev")
        return "\n".join(lines)

    async def terminate(self):
        self._cache.clear()
