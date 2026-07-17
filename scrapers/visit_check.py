"""拜访质量检核引擎（对齐《拜访检核标准文档》v3）。"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, time
from typing import Any

from config import normalize_city

# 数量不检核（质量仍检核）
QTY_EXEMPT_BDS = {"李雪", "袁敏", "瞿慧", "张天平", "雍丹"}
# 门前三分钟不检核
B_PART_EXEMPT_BDS = {"王蕴哲", "舒鑫"}

B_EXEMPT_KEYWORDS = [
    "无b+",
    "無b+",
    "未上竞对",
    "没上竞对",
    "未入驻b+",
    "没有b+",
    "暂未上线",
    "无竞对",
    "没竞对",
    "未上b+",
    "没上b+",
]

SHEET_TO_CITY = {
    "仁寿": "仁寿县",
    "南溪": "南溪",
    "叙永": "叙永",
    "彭州": "彭州市",
    "合江": "合江县",
}

A_PATTERNS = {
    "规划": re.compile(r"规划|規劃"),
    "拜访目的": re.compile(r"拜访目的|拜訪目的|(?:^|[\s:：])目的[:：]"),
    "拜访过程": re.compile(r"拜访过程|拜訪過程|过程[:：]|過程[:：]|内容[:：]|內容[:：]"),
    "拜访结果": re.compile(r"拜访结果|拜訪結果|结果[:：]|結果[:：]"),
}

B_FIELDS = [
    ("b+月售", re.compile(r"b\+?\s*月售|月售", re.I)),
    ("减配力度", re.compile(r"减配|減配")),
    ("top1主营商品及原价", re.compile(r"top\s*1|主营商品|主營商品", re.I)),
    ("神券", re.compile(r"神券|神卷")),
    ("起送价", re.compile(r"起送")),
]


def _parse_dt(raw: str) -> datetime | None:
    s = (raw or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _has_b_exempt_keyword(desc: str) -> bool:
    d = (desc or "").lower().replace("＋", "+")
    for kw in B_EXEMPT_KEYWORDS:
        if kw.lower() in d:
            return True
    return False


def _extract_b_values(desc: str) -> dict[str, str]:
    text = desc or ""
    found: dict[str, str] = {}
    # split by lines / numbered items
    chunks = re.split(r"[\n；;]", text)
    for name, pat in B_FIELDS:
        for ch in chunks:
            if pat.search(ch):
                m = re.search(r"[:：]\s*(.+)$", ch.strip())
                val = (m.group(1) if m else "").strip()
                if not val:
                    m2 = re.search(pat.pattern + r"[:：]?\s*(\S+)", ch, re.I)
                    val = ((m2.group(1) if m2 else "") or "").strip()
                found[name] = val
                break
    return found


def _check_a_part(desc: str) -> list[str]:
    issues = []
    text = desc or ""
    for name, pat in A_PATTERNS.items():
        if not pat.search(text):
            issues.append(f"工作描述缺A部分「{name}」")
    return issues


def _check_b_part(desc: str, bd: str) -> list[str]:
    if bd in B_PART_EXEMPT_BDS:
        return []
    if _has_b_exempt_keyword(desc):
        return []
    issues = []
    vals = _extract_b_values(desc)
    for name, _ in B_FIELDS:
        if name not in vals or vals[name] == "":
            issues.append(f"工作描述缺B部分「{name}」")
    # reasonableness
    zeros = 0
    for name, v in vals.items():
        vv = (v or "").strip()
        if vv in {"0", "０"}:
            zeros += 1
        if name.startswith("top1") and vv in {"0", "０", "无", "無", "无意义", "/"}:
            issues.append("门前三分钟 top1主营商品无效（0/无）")
    if zeros >= 3:
        issues.append("门前三分钟超过3项填0")
    return issues


def _check_time(dt: datetime) -> list[str]:
    t = dt.time()
    if t < time(9, 0) or t > time(21, 0):
        return [f"拜访时间不合规（{dt.strftime('%H:%M')}，需在09:00-21:00）"]
    return []


def _interval_minutes(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 60.0


def _check_intervals(records: list[dict]) -> dict[int, list[str]]:
    """返回 {record_index: issues}。records 需已按时间排序并带 _dt。"""
    issues_map: dict[int, list[str]] = defaultdict(list)
    if not records:
        return issues_map

    # 上午/下午分段
    morning = [r for r in records if r["_dt"].time() < time(13, 0)]
    afternoon = [r for r in records if r["_dt"].time() >= time(13, 0)]

    def check_seq(seq: list[dict], skip_first: bool) -> None:
        for i, cur in enumerate(seq):
            if i == 0 and skip_first:
                continue
            if i == 0:
                continue
            prev = seq[i - 1]
            mins = _interval_minutes(prev["_dt"], cur["_dt"])
            after_18 = cur["_dt"].time() >= time(18, 0) and prev["_dt"].time() >= time(18, 0)
            if mins < 5:
                issues_map[cur["_idx"]].append(f"拜访间隔过短（{mins:.0f}分钟，需≥5分钟）")
            elif mins > 60:
                if after_18:
                    # 18点后不检核>1小时
                    continue
                issues_map[cur["_idx"]].append(f"拜访间隔过长（{mins:.0f}分钟，需≤60分钟）")

    check_seq(morning, skip_first=True)
    check_seq(afternoon, skip_first=True)
    # 午休：上下午交界不检核（已通过分段自然跳过）
    return issues_map


def check_city_day(sheet_name: str, records: list[dict], check_date: str) -> dict[str, Any]:
    city = normalize_city(SHEET_TO_CITY.get(sheet_name, sheet_name)) or sheet_name
    if not records:
        return {
            "city": city,
            "sheet": sheet_name,
            "check_date": check_date,
            "has_data": False,
            "status": "无数据",
            "bd_total": 0,
            "bd_compliant": 0,
            "visit_total": 0,
            "visit_compliant": 0,
            "coop_count": 0,
            "noncoop_count": 0,
            "bds": [],
            "issues": [],
        }

    # normalize
    prepared = []
    for i, r in enumerate(records):
        dt = _parse_dt(r.get("time") or "")
        if not dt:
            continue
        prepared.append(
            {
                "_idx": i,
                "_dt": dt,
                "target": (r.get("target") or "").strip(),
                "type": (r.get("type") or "").strip(),
                "time": r.get("time") or "",
                "bd": (r.get("bd") or "").strip(),
                "desc": r.get("desc") or "",
            }
        )

    by_bd: dict[str, list[dict]] = defaultdict(list)
    for r in prepared:
        by_bd[r["bd"] or "未知BD"].append(r)
    for bd in by_bd:
        by_bd[bd].sort(key=lambda x: x["_dt"])

    issues: list[dict] = []
    bd_rows: list[dict] = []
    visit_ok = 0
    visit_total = len(prepared)

    for bd, visits in sorted(by_bd.items(), key=lambda x: x[0]):
        interval_issues = _check_intervals(visits)
        # per-record quality
        record_flags = []
        for r in visits:
            reasons: list[str] = []
            reasons.extend(_check_time(r["_dt"]))
            reasons.extend(interval_issues.get(r["_idx"], []))
            is_coop = "已合作" in r["type"]
            if is_coop:
                reasons.extend(_check_a_part(r["desc"]))
                reasons.extend(_check_b_part(r["desc"], bd))
            ok = len(reasons) == 0
            record_flags.append(ok)
            if not ok:
                issues.append(
                    {
                        "city": city,
                        "bd": bd,
                        "target": r["target"],
                        "type": r["type"],
                        "time": r["time"],
                        "desc": r["desc"],
                        "reasons": reasons,
                    }
                )

        n = len(visits)
        # >9 时：只需前9条按时间顺序中有足够合规；文档：超出部分默认合规
        if n > 9:
            # 质量：前9条都需尽量合规；统计合规数时超出默认合规
            first9_ok = sum(1 for x in record_flags[:9] if x)
            compliant_count = first9_ok + (n - 9)
            quality_ok = first9_ok >= 9
        else:
            compliant_count = sum(1 for x in record_flags if x)
            quality_ok = compliant_count == n

        coop = sum(1 for r in visits if "已合作" in r["type"])
        noncoop = sum(1 for r in visits if "未合作" in r["type"])
        qty_exempt = bd in QTY_EXEMPT_BDS
        qty_ok = True
        qty_issues = []
        if not qty_exempt:
            if coop < 7:
                qty_ok = False
                qty_issues.append(f"已合作拜访不足（{coop}/7）")
            if noncoop < 2:
                qty_ok = False
                qty_issues.append(f"未合作拜访不足（{noncoop}/2）")
            if n < 9:
                qty_ok = False
                qty_issues.append(f"当日拜访总数不足（{n}/9）")

        bd_ok = quality_ok and qty_ok
        visit_ok += compliant_count
        for qi in qty_issues:
            issues.append(
                {
                    "city": city,
                    "bd": bd,
                    "target": "—",
                    "type": "数量检核",
                    "time": check_date,
                    "desc": "",
                    "reasons": [qi],
                }
            )

        bd_rows.append(
            {
                "bd": bd,
                "visit_total": n,
                "visit_compliant": compliant_count,
                "coop": coop,
                "noncoop": noncoop,
                "qty_exempt": qty_exempt,
                "qty_ok": qty_ok,
                "quality_ok": quality_ok,
                "ok": bd_ok,
                "rate": round(compliant_count / n * 100, 1) if n else 0,
            }
        )

    bd_compliant = sum(1 for b in bd_rows if b["ok"])
    return {
        "city": city,
        "sheet": sheet_name,
        "check_date": check_date,
        "has_data": True,
        "status": "已检核",
        "bd_total": len(bd_rows),
        "bd_compliant": bd_compliant,
        "bd_rate": round(bd_compliant / len(bd_rows) * 100, 1) if bd_rows else 0,
        "visit_total": visit_total,
        "visit_compliant": visit_ok,
        "visit_rate": round(visit_ok / visit_total * 100, 1) if visit_total else 0,
        "coop_count": sum(1 for r in prepared if "已合作" in r["type"]),
        "noncoop_count": sum(1 for r in prepared if "未合作" in r["type"]),
        "bds": bd_rows,
        "issues": issues,
    }


def check_payload(payload: dict) -> dict[str, Any]:
    check_date = payload.get("targetDate") or payload.get("check_date")
    cities_in = payload.get("cities") or {}
    results = []
    for sheet, block in cities_in.items():
        records = block.get("records") or []
        results.append(check_city_day(sheet, records, check_date))

    # region rollup
    with_data = [r for r in results if r["has_data"]]
    region = {
        "check_date": check_date,
        "city_total": len(results),
        "city_with_data": len(with_data),
        "city_no_data": [r["city"] for r in results if not r["has_data"]],
        "bd_total": sum(r["bd_total"] for r in with_data),
        "bd_compliant": sum(r["bd_compliant"] for r in with_data),
        "visit_total": sum(r["visit_total"] for r in with_data),
        "visit_compliant": sum(r["visit_compliant"] for r in with_data),
    }
    if region["bd_total"]:
        region["bd_rate"] = round(region["bd_compliant"] / region["bd_total"] * 100, 1)
    else:
        region["bd_rate"] = 0
    if region["visit_total"]:
        region["visit_rate"] = round(region["visit_compliant"] / region["visit_total"] * 100, 1)
    else:
        region["visit_rate"] = 0

    return {"ok": True, "check_date": check_date, "region": region, "cities": results}
