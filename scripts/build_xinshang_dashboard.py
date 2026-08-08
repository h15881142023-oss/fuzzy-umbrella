"""根据初心抓取结果生成川藏一区新商评周会看板 HTML。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "data" / "xinshang" / "latest.json"
OUTS = [
    ROOT / "static" / "dashboards" / "cz1-xinshang-pingjia.html",
    ROOT / "docs" / "xinshang" / "index.html",
]

TARGET_CITIES = ["彭州市", "仁寿县", "合江县", "南溪", "叙永"]

# 能力预警 fallback（观测舱暂无川藏一区五城时使用，来源：此前考核表固化）
FALLBACK_CAPABILITY = [
    {
        "name": "彭州市",
        "level": "E3",
        "type": "外卖&拼好饭",
        "risk": "目前安全",
        "overallWarn": "(70%-90%]",
        "warnChange": "持平",
        "bands": {
            "外卖": "(70%-90%]",
            "团购": "不预警",
            "履约": "(70%-90%]",
            "零售": "(30%-50%]",
            "组织": "暂不预警",
            "商业增值": "[0%-10%]",
            "用户体验": "(70%-90%]",
            "综合治理": "暂不预警",
        },
    },
    {
        "name": "南溪",
        "level": "F3",
        "type": "外卖&拼好饭&团购",
        "risk": "目前安全",
        "overallWarn": "(70%-90%]",
        "warnChange": "持平",
        "bands": {
            "外卖": "(90%-100%]",
            "团购": "(10%-30%]",
            "履约": "(70%-90%]",
            "零售": "(30%-50%]",
            "组织": "暂不预警",
            "商业增值": "(30%-50%]",
            "用户体验": "(30%-50%]",
            "综合治理": "暂不预警",
        },
    },
    {
        "name": "合江县",
        "level": "F2",
        "type": "外卖&拼好饭",
        "risk": "目前安全",
        "overallWarn": "(50%-70%]",
        "warnChange": "下跌",
        "bands": {
            "外卖": "(50%-70%]",
            "团购": "不预警",
            "履约": "(30%-50%]",
            "零售": "(70%-90%]",
            "组织": "暂不预警",
            "商业增值": "(70%-90%]",
            "用户体验": "(30%-50%]",
            "综合治理": "暂不预警",
        },
    },
    {
        "name": "仁寿县",
        "level": "E3",
        "type": "外卖&拼好饭&团购",
        "risk": "目前安全",
        "overallWarn": "(30%-50%]",
        "warnChange": "持平",
        "bands": {
            "外卖": "(50%-70%]",
            "团购": "[0%-10%]",
            "履约": "(50%-70%]",
            "零售": "(50%-70%]",
            "组织": "暂不预警",
            "商业增值": "(30%-50%]",
            "用户体验": "(50%-70%]",
            "综合治理": "暂不预警",
        },
    },
    {
        "name": "叙永",
        "level": "F3",
        "type": "外卖&拼好饭",
        "risk": "月度高风险",
        "overallWarn": "[0%-10%]",
        "warnChange": "持平",
        "bands": {
            "外卖": "[0%-10%]",
            "团购": "不预警",
            "履约": "[0%-10%]",
            "零售": "(90%-100%]",
            "组织": "暂不预警",
            "商业增值": "(50%-70%]",
            "用户体验": "(10%-30%]",
            "综合治理": "暂不预警",
        },
    },
]

MODULES = ["外卖", "团购", "履约", "零售", "组织", "商业增值", "用户体验", "综合治理"]
MOD_MAP = {
    "waimai": "外卖",
    "tuangou": "团购",
    "fulfillment": "履约",
    "retail": "零售",
    "org": "组织",
    "commercial": "商业增值",
    "experience": "用户体验",
    "governance": "综合治理",
}

BAND_RANK = {
    "[0%-10%]": 0,
    "(10%-30%]": 1,
    "(30%-50%]": 2,
    "(50%-70%]": 3,
    "(70%-90%]": 4,
    "(90%-100%]": 5,
}


def band_class(band: str) -> str:
    b = band or ""
    if not b or b in ("—", "不预警", "暂不预警", "无预警", "不考核", ""):
        return "bna"
    if "[0%-10%]" in b:
        return "b0"
    if "(10%-30%]" in b:
        return "b1"
    if "(30%-50%]" in b:
        return "b2"
    if "(50%-70%]" in b:
        return "b3"
    if "(70%-90%]" in b:
        return "b4"
    if "(90%-100%]" in b:
        return "b5"
    if "高风险" in b or "风险" in b:
        return "brisk"
    if "安全" in b:
        return "bsafe"
    return "bwatch"


def badge(text: str) -> str:
    t = text if text not in (None, "") else "—"
    return f'<span class="badge {band_class(str(t))}">{t}</span>'


def fmt_dt(s: str | None) -> str:
    if not s:
        return "—"
    return str(s).replace("T", " ")[:19]


def band_rank(band: str | None) -> int:
    b = str(band or "")
    for k, v in BAND_RANK.items():
        if k in b:
            return v
    return 9


def risk_rank(risk: str | None) -> int:
    r = str(risk or "")
    if "高风险" in r:
        return 0
    if "关注" in r or "预警" in r:
        return 1
    if "安全" in r:
        return 3
    return 2


def capability_from_obs(cities: list[dict]) -> list[dict]:
    rows = []
    for c in cities:
        board = c.get("board") or {}
        mw = board.get("moduleWarn") or {}
        bands = {MOD_MAP[k]: (mw.get(k) or "—") for k in MOD_MAP}
        rows.append(
            {
                "name": c.get("name"),
                "level": c.get("level") or "—",
                "type": c.get("cityType") or "—",
                "risk": board.get("riskStatus") or "—",
                "overallWarn": board.get("overallWarn") or "—",
                "warnChange": board.get("warnChange") or "—",
                "bands": bands,
                "dataDate": board.get("dataDate") or "—",
            }
        )
    return rows


def weak_modules(bands: dict) -> list[str]:
    out = []
    for m, b in (bands or {}).items():
        if b and ("[0%-10%]" in b or "(10%-30%]" in b):
            out.append(m)
    return out


def dedupe_people(people: list[dict]) -> list[dict]:
    latest: dict[tuple, dict] = {}
    for p in sorted(people, key=lambda x: x.get("updatedAt") or "", reverse=True):
        key = (p.get("city"), (p.get("name") or "").strip())
        if key not in latest:
            latest[key] = p
    return list(latest.values())


def build_brief(cap_rows: list[dict], people_latest: list[dict], kpi_avg, kpi_below: int) -> tuple[list[str], list[str]]:
    conclusions: list[str] = []
    actions: list[str] = []

    high = [c for c in cap_rows if "高风险" in str(c.get("risk")) or band_rank(c.get("overallWarn")) == 0]
    for c in high:
        mods = "、".join(weak_modules(c.get("bands") or {})) or "综合大盘"
        conclusions.append(
            f"「{c['name']}」为优先盯防城：{c.get('risk')}，综合预警 {c.get('overallWarn')}，薄弱模块：{mods}。"
        )
        actions.append(
            f"「{c['name']}」本周拆解 {mods} 的具体动作（责任人、截止日、验收口径），周会复盘闭环。"
        )

    mid = [
        c
        for c in cap_rows
        if c not in high and weak_modules(c.get("bands") or {})
    ]
    for c in mid:
        mods = "、".join(weak_modules(c.get("bands") or {}))
        conclusions.append(f"「{c['name']}」局部落后：{mods}（≤30% 区间）。")
        actions.append(f"「{c['name']}」对 {mods} 做单项补强，避免拖累综合预警。")

    down = [c for c in cap_rows if "下跌" in str(c.get("warnChange"))]
    for c in down:
        conclusions.append(f"「{c['name']}」综合预警环比下跌，需核对是否过程指标滑坡。")
        actions.append(f"「{c['name']}」对比上周过程量，定位下跌模块并给回稳动作。")

    low_score = [
        p
        for p in people_latest
        if p.get("city") in TARGET_CITIES and p.get("score") is not None and float(p["score"]) < 90
    ]
    if low_score:
        names = "、".join(f"{p.get('city')}{p.get('name')}（{p.get('score')}分）" for p in low_score)
        conclusions.append(f"新商测评需关注：{names}。")
        actions.append("对 <90 分人员安排复训/补考，并在下次同步前确认是否出账。")
    else:
        conclusions.append(f"五城测评整体健康：均分 {kpi_avg}，本期无 <90 分人员。" if kpi_below == 0 else f"五城测评均分 {kpi_avg}，仍有 {kpi_below} 人 <90 分。")

    if not actions:
        actions.append("维持现状监控；各城按模块矩阵自查是否有隐性滑坡。")

    # de-dupe while preserving order
    def uniq(xs: list[str]) -> list[str]:
        seen = set()
        out = []
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return uniq(conclusions)[:6], uniq(actions)[:6]


def render(payload: dict) -> str:
    tests = payload.get("tests") or {}
    city_stats = tests.get("cityStats") or []
    people = tests.get("people") or []
    cap_cities = payload.get("capabilityCities") or []
    using_live_cap = bool(cap_cities)
    cap_rows = capability_from_obs(cap_cities) if using_live_cap else list(FALLBACK_CAPABILITY)
    scraped_at = fmt_dt(payload.get("scrapedAt"))
    obs = (payload.get("source") or {}).get("observation") or {}

    # 能力按风险/预警严重度排序（周会先看最差）
    cap_rows = sorted(
        cap_rows,
        key=lambda c: (risk_rank(c.get("risk")), band_rank(c.get("overallWarn")), c.get("name") or ""),
    )

    people_latest = dedupe_people(people)
    people_target = [p for p in people_latest if p.get("city") in TARGET_CITIES]
    people_other = [p for p in people_latest if p.get("city") not in TARGET_CITIES]
    people_target = sorted(
        people_target,
        key=lambda r: (
            0 if r.get("score") is not None and float(r["score"]) < 90 else 1,
            str(r.get("city") or ""),
            -(float(r["score"]) if r.get("score") is not None else -1),
        ),
    )
    people_other = sorted(people_other, key=lambda r: (str(r.get("city") or ""), str(r.get("name") or "")))

    target_stats = [s for s in city_stats if s.get("city") in TARGET_CITIES]
    other_stats = [s for s in city_stats if s.get("city") not in TARGET_CITIES]

    weak_cap = []
    for c in cap_rows:
        bad = weak_modules(c.get("bands") or {})
        if bad or "高风险" in str(c.get("risk")) or band_rank(c.get("overallWarn")) == 0:
            weak_cap.append((c["name"], bad, c.get("risk"), c.get("overallWarn")))

    kpi_people = sum(int(x.get("people") or 0) for x in target_stats)
    kpi_below = sum(int(x.get("below90") or 0) for x in target_stats)
    avgs = [x["avg"] for x in target_stats if x.get("avg") is not None]
    kpi_avg = round(sum(avgs) / len(avgs), 2) if avgs else "—"
    kpi_risk_cities = sum(1 for c in cap_rows if "高风险" in str(c.get("risk")) or band_rank(c.get("overallWarn")) <= 1)

    conclusions, actions = build_brief(cap_rows, people_latest, kpi_avg, kpi_below)

    city_stat_rows = "".join(
        f"<tr><td class='city'>{s['city']}</td><td>{s['people']}</td><td>{s['records']}</td>"
        f"<td class='num'>{s['avg'] if s['avg'] is not None else '—'}</td>"
        f"<td>{s['min'] if s['min'] is not None else '—'}</td>"
        f"<td>{s['max'] if s['max'] is not None else '—'}</td>"
        f"<td>{badge(str(s['below90'])+'人') if s['below90'] else '0'}</td>"
        f"<td>{fmt_dt(s.get('latestAt'))}</td></tr>"
        for s in target_stats
    )
    other_stat_rows = "".join(
        f"<tr><td class='city'>{s['city']}</td><td>{s['people']}</td><td>{s['records']}</td>"
        f"<td class='num'>{s['avg'] if s['avg'] is not None else '—'}</td>"
        f"<td>{badge(str(s['below90'])+'人') if s['below90'] else '0'}</td>"
        f"<td>{fmt_dt(s.get('latestAt'))}</td></tr>"
        for s in other_stats
    )

    attention_people = [
        p for p in people_target if p.get("score") is not None and float(p["score"]) < 90
    ]
    attention_rows = (
        "".join(
            f"<tr><td class='city'>{p.get('city') or '—'}</td><td>{p.get('name') or '—'}</td>"
            f"<td class='num'>{p.get('score')}</td><td>{badge('需关注')}</td>"
            f"<td>{p.get('note') or '—'}</td><td>{fmt_dt(p.get('updatedAt'))}</td></tr>"
            for p in attention_people
        )
        or "<tr><td colspan='6'>本期五城无 <90 分人员</td></tr>"
    )

    people_rows = "".join(
        f"<tr><td class='city'>{p.get('city') or '—'}</td><td>{p.get('name') or '—'}</td>"
        f"<td class='num'>{p.get('score') if p.get('score') is not None else '—'}</td>"
        f"<td>{badge('需关注') if (p.get('score') is not None and float(p['score']) < 90) else '—'}</td>"
        f"<td>{p.get('note') or '—'}</td><td>{fmt_dt(p.get('updatedAt'))}</td></tr>"
        for p in people_target
    )

    other_people_rows = "".join(
        f"<tr><td class='city'>{p.get('city') or '—'}</td><td>{p.get('name') or '—'}</td>"
        f"<td class='num'>{p.get('score') if p.get('score') is not None else '—'}</td>"
        f"<td>{fmt_dt(p.get('updatedAt'))}</td></tr>"
        for p in people_other
    )

    overview_cap = "".join(
        f"<tr><td class='city'>{c['name']}</td><td>{c.get('level','—')}</td><td>{c.get('type','—')}</td>"
        f"<td>{badge(c.get('risk','—'))}</td><td>{badge(c.get('overallWarn','—'))}</td>"
        f"<td>{c.get('warnChange','—')}</td>"
        f"<td class='wrap-cell'>{' '.join(badge(m+' '+c['bands'][m]) for m in MODULES if c.get('bands',{}).get(m) and ('[0%-10%]' in c['bands'][m] or '(10%-30%]' in c['bands'][m])) or '—'}</td></tr>"
        for c in cap_rows
    )

    matrix = "".join(
        "<tr><td class='city'>"
        + c["name"]
        + "</td>"
        + "".join(f"<td>{badge(c.get('bands',{}).get(m,'—'))}</td>" for m in MODULES)
        + "</tr>"
        for c in cap_rows
    )

    focus = "".join(
        f"<tr><td class='city'>{n}</td><td>{badge(str(risk))}</td><td>{badge(str(ow))}</td>"
        f"<td class='wrap-cell'>{'、'.join(bad) if bad else '—'}</td></tr>"
        for n, bad, risk, ow in weak_cap
    ) or "<tr><td colspan='4'>本期无 ≤30% 区间或高风险城市</td></tr>"

    # 模块热度：各城落后模块计数
    mod_heat = {m: 0 for m in MODULES}
    for c in cap_rows:
        for m in weak_modules(c.get("bands") or {}):
            mod_heat[m] = mod_heat.get(m, 0) + 1
    heat_rows = "".join(
        f"<tr><td>{m}</td><td class='num'>{mod_heat[m]}</td>"
        f"<td>{'优先补强' if mod_heat[m] >= 2 else ('关注' if mod_heat[m] == 1 else '暂无落后城')}</td></tr>"
        for m in sorted(MODULES, key=lambda x: (-mod_heat[x], x))
    )

    brief_html = "".join(f"<li>{x}</li>" for x in conclusions)
    action_html = "".join(f"<li>{x}</li>" for x in actions)

    cap_source = (
        f"初心观测舱实时解析（{obs.get('pageTitle') or '新商能力评价'} / {fmt_dt(obs.get('fileUpdatedAt'))}）"
        if using_live_cap
        else "观测舱暂未包含川藏一区五城，能力预警沿用考核表固化口径（待观测舱补齐后自动切换）"
    )

    other_block = ""
    if other_stats or other_people_rows:
        other_block = f"""
  <section class="section muted-sec">
    <h2>附录 · 区外/非五城记录</h2>
    <p class="desc">区域筛选为「川藏一区」时可能带出其它城市，仅作透明展示，不计入五城 KPI。</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>人数</th><th>记录</th><th>均分</th><th>&lt;90</th><th>最近更新</th></tr></thead>
      <tbody>{other_stat_rows or "<tr><td colspan='6'>—</td></tr>"}</tbody>
    </table></div>
    <div class="scroll" style="margin-top:10px"><table>
      <thead><tr><th>城市</th><th>姓名</th><th>分数</th><th>更新时间</th></tr></thead>
      <tbody>{other_people_rows or "<tr><td colspan='4'>—</td></tr>"}</tbody>
    </table></div>
  </section>
"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>川藏一区 · 新商评看板</title>
  <style>
    :root {{
      --bg:#102028; --panel:#f7faf8; --ink:#152228; --muted:#5a6b73;
      --line:#d7e0e4; --brand:#0b6b5d; --brand-deep:#074f45; --accent:#c45c26;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; color:var(--ink);
      font-family:"Source Han Sans SC","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;
      background:
        radial-gradient(1000px 480px at 8% -10%, rgba(11,107,93,.38), transparent 55%),
        radial-gradient(800px 420px at 100% 0%, rgba(196,92,38,.18), transparent 50%),
        linear-gradient(165deg,#0d1a20,#163038 52%,#1a3c46);
      padding:20px 12px 48px;
    }}
    .wrap {{ width:min(1600px,100%); margin:0 auto; }}
    .hero {{
      background:linear-gradient(135deg,#0a5a4e,#12343d 58%,#1a4550);
      color:#f4fffb; border-radius:18px; padding:22px 24px; margin-bottom:14px;
      border:1px solid rgba(255,255,255,.08);
    }}
    .hero .brand {{ font-size:clamp(1.8rem,3.2vw,2.35rem); font-weight:800; letter-spacing:.04em; margin:0 0 8px; }}
    .hero h1 {{ margin:0 0 6px; font-size:1.15rem; font-weight:600; color:rgba(244,255,251,.92); }}
    .hero p {{ margin:0; color:rgba(244,255,251,.82); line-height:1.55; max-width:78ch; font-size:.95rem; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
    .chip {{ background:rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18); border-radius:999px; padding:6px 12px; font-size:.86rem; }}
    .section {{ background:var(--panel); border-radius:14px; padding:16px 18px; margin-bottom:12px; box-shadow:0 10px 28px rgba(0,0,0,.16); }}
    .muted-sec {{ opacity:.96; }}
    .section h2 {{ margin:0 0 4px; font-size:1.18rem; color:var(--brand-deep); }}
    .desc {{ margin:0 0 12px; color:var(--muted); font-size:.9rem; }}
    .brief-grid {{ display:grid; grid-template-columns:1.2fr 1fr; gap:14px; }}
    .brief-box h3 {{ margin:0 0 8px; font-size:.98rem; color:var(--brand-deep); }}
    .brief-box ol, .brief-box ul {{ margin:0; padding-left:1.15rem; line-height:1.65; }}
    .brief-box li {{ margin-bottom:4px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }}
    .kpi {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:12px; }}
    .kpi .l {{ color:var(--muted); font-size:.8rem; }}
    .kpi .v {{ font-size:1.55rem; font-weight:800; color:var(--brand-deep); margin-top:4px; }}
    .kpi.warn .v {{ color:#8f1d14; }}
    .scroll {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:.86rem; min-width:720px; }}
    th,td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; white-space:nowrap; }}
    th {{ background:#e7f3ef; color:#35545c; position:sticky; top:0; }}
    tr:nth-child(even) td {{ background:#fbfdfc; }}
    .city {{ font-weight:700; color:var(--brand-deep); }}
    .num {{ font-weight:700; }}
    .wrap-cell {{ white-space:normal; min-width:180px; line-height:1.45; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:6px; font-size:.78rem; font-weight:700; }}
    .b0{{background:#fde8e6;color:#8f1d14}} .b1{{background:#ffedd5;color:#9a3412}}
    .b2{{background:#fef3c7;color:#92400e}} .b3{{background:#ecfccb;color:#3f6212}}
    .b4{{background:#dcfce7;color:#166534}} .b5{{background:#bbf7d0;color:#14532d}}
    .bna{{background:#eef2f4;color:#667780}} .brisk{{background:#fde8e6;color:#8f1d14}} .bsafe{{background:#e5f6ec;color:#1f7a4c}} .bwatch{{background:#fff1df;color:#b7791f}}
    .footer {{ text-align:center; color:rgba(244,255,251,.72); font-size:.82rem; margin-top:8px; }}
    @media (max-width:960px) {{
      .kpis, .brief-grid {{ grid-template-columns:1fr 1fr; }}
    }}
    @media (max-width:640px) {{
      .kpis, .brief-grid {{ grid-template-columns:1fr; }}
      .hero {{ padding:18px 16px; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brand">川藏一区</div>
    <h1>新商评周会看板</h1>
    <p>测试成绩实时同步初心后台；能力侧只看预警区间（无图表、无能力分）。按风险严重度排序，服务周二/周五周会决策。</p>
    <div class="meta">
      <div class="chip">同步时间 <strong>{scraped_at}</strong></div>
      <div class="chip">五城 <strong>彭州 / 仁寿 / 合江 / 南溪 / 叙永</strong></div>
      <div class="chip">自动更新 <strong>每周二、五 17:00</strong></div>
    </div>
  </header>

  <section class="section">
    <h2>〇、周会结论与动作</h2>
    <p class="desc">由最新测评 + 能力预警自动汇总，开会先读本段。</p>
    <div class="brief-grid">
      <div class="brief-box">
        <h3>结论</h3>
        <ol>{brief_html}</ol>
      </div>
      <div class="brief-box">
        <h3>建议动作</h3>
        <ol>{action_html}</ol>
      </div>
    </div>
  </section>

  <section class="section">
    <h2>一、五城快览</h2>
    <p class="desc">测评集合「新商评测试结果」· 区域=川藏一区；能力风险城统计来自预警矩阵。</p>
    <div class="kpis">
      <div class="kpi"><div class="l">五城参考人数</div><div class="v">{kpi_people}</div></div>
      <div class="kpi"><div class="l">五城均分</div><div class="v">{kpi_avg}</div></div>
      <div class="kpi {'warn' if kpi_below else ''}"><div class="l">低于90分人数</div><div class="v">{kpi_below}</div></div>
      <div class="kpi {'warn' if kpi_risk_cities else ''}"><div class="l">高风险/弱预警城</div><div class="v">{kpi_risk_cities}</div></div>
    </div>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>人数(去重)</th><th>记录数</th><th>均分</th><th>最低</th><th>最高</th><th>&lt;90分</th><th>最近更新</th></tr></thead>
      <tbody>{city_stat_rows}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>二、测评关注名单（&lt;90）</h2>
    <p class="desc">按人去重保留最新一条；全员名册见文末。</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>姓名</th><th>分数</th><th>关注</th><th>备注</th><th>更新时间</th></tr></thead>
      <tbody>{attention_rows}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>三、能力预警焦点（≤30% / 高风险）</h2>
    <p class="desc">{cap_source}</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>风险</th><th>综合预警</th><th>落后模块</th></tr></thead>
      <tbody>{focus}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>四、能力预警总览（严重度排序）</h2>
    <p class="desc">只展示预警区间，不展示能力得分；高风险/低区间优先。</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>等级</th><th>类型</th><th>风险</th><th>综合预警</th><th>环比</th><th>落后模块</th></tr></thead>
      <tbody>{overview_cap}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>五、八大模块预警矩阵</h2>
    <p class="desc">城市 × 模块排名区间，全部铺开便于周会对照。</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th>{''.join(f'<th>{m}</th>' for m in MODULES)}</tr></thead>
      <tbody>{matrix}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>六、模块落后热度</h2>
    <p class="desc">统计五城中落入 ≤30% 区间的模块出现次数，用于排期补强优先级。</p>
    <div class="scroll"><table>
      <thead><tr><th>模块</th><th>落后城数</th><th>优先级</th></tr></thead>
      <tbody>{heat_rows}</tbody>
    </table></div>
  </section>

  <section class="section">
    <h2>七、五城全员名册（去重最新）</h2>
    <p class="desc">同一人多条只保留最新成绩；低分优先。</p>
    <div class="scroll"><table>
      <thead><tr><th>城市</th><th>姓名</th><th>分数</th><th>关注</th><th>备注</th><th>更新时间</th></tr></thead>
      <tbody>{people_rows}</tbody>
    </table></div>
  </section>

  {other_block}

  <p class="footer">自动同步自 http://www.chuxin.city/v/admin/b7v8t424ohb · 域名页读取本文件 · 川藏一区</p>
</div>
</body>
</html>
"""


def main() -> None:
    if not LATEST.exists():
        raise SystemExit(f"missing snapshot: {LATEST}. Run scrapers/scrape_chuxin_xinshang.py first.")
    payload = json.loads(LATEST.read_text(encoding="utf-8"))
    html = render(payload)
    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()
