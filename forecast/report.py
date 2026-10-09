"""產生可列印（瀏覽器另存 PDF）的 HTML 試算報告。"""
from __future__ import annotations

import datetime as dt
from html import escape

from .engine import Settings
from .fmt import money, nice_ticks, short_money

COLORS = {"悲觀": "#DC2626", "基準": "#2563EB", "樂觀": "#0F9D8A"}


def _svg_chart(results: dict, retire_age: float, w: int = 900, h: int = 320) -> str:
    L, R, T, B = 70, 20, 30, 34
    base = results["基準"].rows
    ages = [x.age for x in base]
    series = {k: [x.net_worth for x in v.rows] for k, v in results.items()}
    vals = [v for s in series.values() for v in s] + [0]
    ticks = nice_ticks(min(vals), max(vals), 4)
    lo, hi = ticks[0], ticks[-1]
    x0, x1 = ages[0], ages[-1]

    def px(a):
        return L + (a - x0) / max(x1 - x0, 1e-9) * (w - L - R)

    def py(v):
        return T + (hi - v) / (hi - lo) * (h - T - B)
    out = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-size="11" '
           f'font-family="sans-serif">']
    for tv in ticks:
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{py(tv):.1f}" y2="{py(tv):.1f}" stroke="#e5e9f0"/>')
        out.append(f'<text x="{L - 6}" y="{py(tv) + 4:.1f}" text-anchor="end" fill="#6b7280">{short_money(tv)}</text>')
    step = 5 if (x1 - x0) > 25 else 2 if (x1 - x0) > 10 else 1
    a = int(x0 // step * step)
    while a <= x1:
        if a >= x0:
            out.append(f'<text x="{px(a):.1f}" y="{h - B + 16}" text-anchor="middle" fill="#6b7280">{a}</text>')
        a += step
    out.append(f'<line x1="{L}" x2="{w - R}" y1="{py(0):.1f}" y2="{py(0):.1f}" stroke="#9aa5b8"/>')
    if x0 <= retire_age <= x1:
        out.append(f'<line x1="{px(retire_age):.1f}" x2="{px(retire_age):.1f}" y1="{T - 8}" y2="{h - B}" '
                   f'stroke="#d97706" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{px(retire_age) + 4:.1f}" y="{T - 12}" fill="#d97706">退休 {retire_age:g}</text>')
    for name in ("悲觀", "樂觀", "基準"):
        pts = " ".join(f"{px(a_):.1f},{py(v):.1f}" for a_, v in zip(ages, series[name]))
        dash = "" if name == "基準" else ' stroke-dasharray="6 4"'
        out.append(f'<polyline points="{pts}" fill="none" stroke="{COLORS[name]}" '
                   f'stroke-width="{3 if name == "基準" else 2}"{dash}/>')
    lx = L
    for name in ("悲觀", "基準", "樂觀"):
        out.append(f'<line x1="{lx}" x2="{lx + 22}" y1="10" y2="10" stroke="{COLORS[name]}" stroke-width="3"/>')
        out.append(f'<text x="{lx + 28}" y="14" fill="#1f2937">{name}</text>')
        lx += 80
    out.append("</svg>")
    return "".join(out)


def build_report(s: Settings, results: dict) -> str:
    base = results["基準"]
    end = base.rows[-1]
    e = escape
    ret = next((x for x in base.rows if abs(x.age - s.retire_age) < 0.01), None)
    status = (f"約 {base.depleted_age:.1f} 歲資產耗盡" if base.depleted_age
              else f"流動資產可支撐至 {s.life_expectancy:g} 歲")
    kpis = [
        (f"{s.retire_age:g} 歲退休時淨資產", f"NT$ {short_money(base.retire_net_worth)}",
         f"今日購買力 NT$ {short_money(base.retire_real_net_worth)}"),
        (f"{s.life_expectancy:g} 歲時淨資產", f"NT$ {short_money(end.net_worth)}",
         f"今日購買力 NT$ {short_money(end.real_net_worth)}"),
        ("資產狀態（基準）", status, "全程以流動資產支應生活費"),
        ("退休後固定月收入", f"NT$ {money(base.li_monthly + (0 if s.lp_lump_sum else base.lp_monthly))}",
         f"勞保年金 {money(base.li_monthly)}"),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="k">{e(a)}</div><div class="v">{e(b)}</div>'
                       f'<div class="s">{e(c)}</div></div>' for a, b, c in kpis)
    sc_rows = "".join(
        f"<tr><td>{n}</td><td class='r'>{money(results[n].retire_net_worth)}</td>"
        f"<td class='r'>{money(results[n].rows[-1].net_worth)}</td>"
        f"<td class='r'>{money(results[n].rows[-1].liquid_net_worth)}</td>"
        f"<td>{('約 %.0f 歲' % results[n].depleted_age) if results[n].depleted_age else '無'}</td></tr>"
        for n in ("悲觀", "基準", "樂觀"))
    assume = [
        ("目前 / 退休 / 預期壽命", f"{s.current_age:g} / {s.retire_age:g} / {s.life_expectancy:g} 歲"),
        ("實領月薪（預扣所得稅）", f"NT$ {money(s.salary_net)}（{money(s.salary_withheld)}）；年調薪 {s.income_growth:g}%"),
        ("年終獎金", f"{s.bonus_months:g} 個月（{int(s.bonus_month)} 月發放）" if s.bonus_months else "無"),
        ("每月生活支出（今日幣值）", f"目前 {money(s.monthly_expense)}；退休後 {money(s.retire_expense)}"),
        ("通膨 / 活存利率", f"{s.inflation:g}% / {s.savings_rate:g}%"),
        ("投資帳戶", "、".join(f"{a.name}（{money(a.cash)}）" for a in s.accounts) or "無"),
        ("額外收入", "、".join(f"{x.name}（{money(x.amount)}/{'年' if x.freq == 'year' else '月'}，"
                              f"{x.start_age:g}–{x.end_age:g} 歲）" for x in s.extra_incomes) or "無"),
        ("其他固定支出", "、".join(f"{x.name}（{money(x.amount)}/{'年' if x.freq == 'year' else '月'}，"
                                f"{x.start_age:g}–{x.end_age:g} 歲）" for x in s.extra_expenses) or "無"),
        ("一次性收支", "、".join(f"{x.name}（{'+' if x.kind == 'in' else '−'}{money(x.amount)}，{x.age:g} 歲）"
                              for x in s.one_offs) or "無"),
        ("保險", "、".join(f"{x.name}（{money(x.premium)}/{'年' if x.freq == 'year' else '月'}，"
                         f"{x.start_age:g}–{x.end_age:g} 歲）" for x in s.insurances) or "無"),
        ("貸款", "、".join(l.name for l in s.loans) or "無"),
        ("不動產", "、".join(f"{p.name}（{money(p.value)}）" for p in s.properties) or "無"),
        ("退休後生活費帳戶", f"每年年初補足 NT$ {money(s.bucket_amount)}" + ("（今日幣值，隨通膨調整）" if s.bucket_inflate else "")),
        ("醫療費用", f"{s.medical_start_age:g} 歲起每月 NT$ {money(s.medical_monthly)}（今日幣值），每年多成長 {s.medical_growth:g}%"),
        ("情境", f"悲觀 / 樂觀 = 投資報酬率 ∓ {s.scenario_delta:g} 個百分點"),
    ]
    dflt = "預設（退休前活存、退休後生活費帳戶）"
    assume.insert(1, ("資金流向", f"薪水存入 {s.salary_account or dflt}；生活支出/醫療由 {s.expense_account or dflt} 支付；"
                                f"年金存入 {s.pension_account or dflt}"))
    rules = []
    for p_ in s.policies:
        if p_.account != "生活費帳戶" and p_.mode == "cap" and p_.overflow_to:
            rules.append(f"{p_.account} 上限 {money(p_.limit)} → 超出轉入 {p_.overflow_to}")
        elif p_.account != "生活費帳戶" and p_.mode == "fixed":
            rules.append(f"{p_.account} 每年 1 月固定 {money(p_.limit)}")
    if rules:
        assume.insert(2, ("帳戶規則", "；".join(rules)))
    assume_html = "".join(f"<tr><th>{e(a)}</th><td>{e(b)}</td></tr>" for a, b in assume)
    heads = ["年齡", "實領薪水", "額外收入", "年金/退休金月領", "生活+其他支出", "保險", "醫療", "貸款",
             "不動產", "淨資產（不含不動產）", "淨資產", "今日購買力"]
    body = ""
    for x in base.rows:
        cls = ' class="ret"' if abs(x.age - s.retire_age) < 0.01 else ""
        cells = [f"{x.age:g}", money(x.income), money(x.extra_income), money(x.pension_income),
                 money(x.expense + x.extra_expense), money(x.insurance), money(x.medical), money(x.loan_paid),
                 money(x.property_value), money(x.liquid_net_worth), money(x.net_worth), money(x.real_net_worth)]
        body += f"<tr{cls}>" + "".join(f"<td class='r'>{c}</td>" for c in cells) + "</tr>"
    head_html = "".join(f"<th>{h}</th>" for h in heads)
    cf = base.cashflow
    inc = cf["salary"] + cf["extra"] + cf["pension"] + cf["tax"] + cf["oneoff"]
    out = cf["living"] + cf["xexp"] + cf["insurance"] + cf["loan"] + cf["medical"] + cf["invest"]
    cf_rows = [("實領薪水", cf["salary"]), ("額外收入", cf["extra"]), ("年金 / 退休金月領", cf["pension"]),
               ("稅款結算", cf["tax"]), ("一次性收支淨額", cf["oneoff"]), ("收入合計", inc),
               ("生活支出", cf["living"]), ("其他固定支出", cf["xexp"]), ("保險保費", cf["insurance"]),
               ("貸款還款", cf["loan"]), ("醫療費用", cf["medical"]), ("每月投資加碼", cf["invest"]),
               ("支出與投資合計", out), ("每月淨現金流", inc - out)]
    cf_html = "".join(f"<tr><th>{e(a)}</th><td class='r'>{money(b)}</td></tr>" for a, b in cf_rows)
    sales = base.property_sales
    sales_html = ""
    if sales:
        srows = "".join(
            f"<tr><td>{e(x['name'])}</td><td class='r'>{x['age']:g} 歲</td><td class='r'>{money(x['price'])}</td>"
            f"<td class='r'>{money(x['cost'])}</td><td class='r'>{money(x['payoff'])}</td>"
            f"<td class='r'>{money(x['tax'])}</td><td class='r'>{money(x['net_cash'])}</td>"
            f"<td class='r'>{money(x['gain']) if x['gain'] is not None else '—'}</td>"
            f"<td class='r'>{money(x['gain_after_tax']) if x['gain_after_tax'] is not None else '—'}</td></tr>"
            for x in sales)
        sales_html = ("<h2>不動產出售試算</h2><div class='card'><table><thead><tr><th>名稱</th><th>出售年齡</th>"
                      "<th>預估售價</th><th>交易成本</th><th>償還貸款</th><th>獲利稅</th><th>實拿現金</th>"
                      f"<th>獲利（稅前）</th><th>獲利（稅後）</th></tr></thead><tbody>{srows}</tbody></table></div>")
    warn = "".join(f"<li>{e(w)}</li>" for w in base.warnings)
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>退休收益預測報告</title>
<style>
body{{font-family:"Microsoft JhengHei","PingFang TC",sans-serif;color:#1f2937;margin:0;background:#f3f5f9}}
.wrap{{max-width:1000px;margin:0 auto;padding:24px}}
header{{background:#17304f;color:#fff;padding:22px 28px;border-radius:8px}}
header h1{{margin:0;font-size:24px}} header p{{margin:4px 0 0;color:#9fb3cf;font-size:13px}}
h2{{font-size:16px;color:#17304f;border-left:4px solid #2563eb;padding-left:8px;margin:26px 0 10px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}}
.kpi{{background:#fff;border:1px solid #d9dee7;border-radius:8px;padding:12px 14px}}
.kpi .k{{font-size:12px;color:#6b7280}} .kpi .v{{font-size:20px;font-weight:700;color:#17304f;margin:4px 0}}
.kpi .s{{font-size:12px;color:#6b7280}}
.card{{background:#fff;border:1px solid #d9dee7;border-radius:8px;padding:14px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{padding:6px 8px;border-bottom:1px solid #e5e9f0;text-align:left}}
thead th{{background:#17304f;color:#fff;text-align:center}}
td.r{{text-align:right}} tr.ret td{{background:#fff4d6}}
.assume th{{width:200px;color:#6b7280;font-weight:600}}
.note{{font-size:11px;color:#6b7280;margin-top:18px;line-height:1.7}}
@media print{{body{{background:#fff}} .wrap{{padding:0}} .card,.kpi{{break-inside:avoid}}}}
</style></head><body><div class="wrap">
<header><h1>退休收益預測報告</h1><p>產生日期 {dt.date.today():%Y-%m-%d} · 幣別：新台幣 · 以基準情境為主</p></header>
<div class="kpis">{kpi_html}</div>
<h2>淨資產走勢（含不動產，名目金額）</h2><div class="card">{_svg_chart(results, s.retire_age)}</div>
<h2>情境比較</h2><div class="card"><table><thead><tr><th>情境</th><th>退休時淨資產</th><th>壽命時淨資產</th>
<th>壽命時（不含不動產）</th><th>資產耗盡</th></tr></thead><tbody>{sc_rows}</tbody></table></div>
<h2>目前每月現金流明細（第一年平均）</h2><div class="card"><table class="assume">{cf_html}</table></div>
{sales_html}<h2>主要假設</h2><div class="card"><table class="assume">{assume_html}</table></div>
{f'<h2>提醒</h2><div class="card"><ul>{warn}</ul></div>' if warn else ''}
<h2>逐年明細（基準情境）</h2><div class="card"><table><thead><tr>{head_html}</tr></thead><tbody>{body}</tbody></table></div>
<p class="note">本報告為依輸入假設之估算，非投資、稅務或保險建議。所得稅以有效稅率簡化；不動產出售不含房地合一稅；
勞保年金以公式估算且未含 CPI 調整；實際金額以主管機關與契約為準。</p>
</div></body></html>"""
