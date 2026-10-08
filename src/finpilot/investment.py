"""Local investment research: user CSV -> explainable shortlist -> risk memo.

No download, model call, return forecast or trading execution occurs here.
"""
from __future__ import annotations
import csv
import datetime as dt
import hashlib
import io
import json
import math
import random
import re
from typing import Any
import numpy as np
import pandas as pd
from .portfolio import build_portfolio, portfolio_stress

STOCK_FIELDS = ['symbol','name','sector','currency','price_as_of','price','eps_ttm','revenue_growth','operating_margin','fcf_margin','debt_to_equity','period_end','filed_at','source']
PRICE_FIELDS = ['date','symbol','adj_close']
PROFILES = {'balanced':(.4,.3,.3), 'quality':(.6,.2,.2), 'value':(.3,.2,.5)}
NUMERIC = ['price','eps_ttm','revenue_growth','operating_margin','fcf_margin','debt_to_equity']
REASONS = {
 'future_filing':'披露日期晚于研究日', 'future_price':'快照价格晚于研究日',
 'stale_price':'快照价格距研究日超过120天', 'stale_filing':'披露距研究日超过550天',
 'missing_metrics':'缺少必要财务字段', 'nonpositive_eps':'TTM每股收益不为正，PE不适用',
 'pe_above_limit':'PE超过上限', 'growth_below_limit':'收入增长低于下限',
 'debt_above_limit':'债务/权益比超过上限', 'negative_equity_proxy':'负债权益比为负，不适用此筛选框架',
 'nonpositive_margin':'营业利润率或自由现金流率不为正',
}


def _date(value, label):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError(f'{label}: 必须为 YYYY-MM-DD')
    try: return dt.date.fromisoformat(value)
    except ValueError as exc: raise ValueError(f'{label}: 日期不存在') from exc


def _num(value, label, allow_missing=False):
    if allow_missing and (value is None or value==''): return None
    if isinstance(value,bool): raise ValueError(f'{label}: 布尔值不是数字')
    try: number=float(value)
    except (ValueError,TypeError) as exc: raise ValueError(f'{label}: 需要数值，百分比请写小数如0.12') from exc
    if not math.isfinite(number): raise ValueError(f'{label}: 拒绝 NaN/Inf')
    return number


def _symbol(value,label):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,14}',value):
        raise ValueError(f'{label}: 代码须为1–15位大写字母、数字、点或连字符')
    return value


def _csv(text,fields,label,max_rows):
    if not isinstance(text,str) or not text.strip(): raise ValueError(f'{label}: 文件为空')
    if len(text.encode('utf-8'))>2_000_000: raise ValueError(f'{label}: 文件不得超过2MB')
    try:
        reader=csv.DictReader(io.StringIO(text.lstrip('﻿')),strict=True)
        if reader.fieldnames != fields: raise ValueError(f'{label}: 表头及顺序须为 '+','.join(fields))
        rows=[]
        for i,row in enumerate(reader,2):
            if i>max_rows+1: raise ValueError(f'{label}: 超过{max_rows}行')
            if None in row or any(v is None for v in row.values()): raise ValueError(f'{label}第{i}行: 列数不匹配')
            rows.append({k:v.strip() for k,v in row.items()})
        if not rows: raise ValueError(f'{label}: 没有数据行')
        return rows
    except csv.Error as exc: raise ValueError(f'{label}: 无法解析CSV') from exc


def _clip(v): return min(1.,max(0.,v))


def score_components(row, pe, profile):
    """Absolute, fixed thresholds; no cross-sectional statistical claims."""
    q=100*(.4*_clip(row['operating_margin']/.30)+.4*_clip(row['fcf_margin']/.20)+.2*(1-_clip(row['debt_to_equity']/2)))
    g=100*_clip(row['revenue_growth']/.30)
    v=100*_clip((40-pe)/30)
    w=PROFILES[profile]
    return {'quality':q,'growth':g,'value':v,'total':w[0]*q+w[1]*g+w[2]*v,'weights':list(w)}


def valuation_sensitivity(rows, multiples=(10, 15, 20, 25, 30, 35, 40)):
    """EPS × hypothetical PE table; a descriptive sensitivity, not a target price."""
    output = []
    for row in rows:
        eps = row.get("eps_ttm")
        if eps is None or eps <= 0 or row.get("price") is None or row["price"] <= 0:
            output.append({"symbol": row.get("symbol"), "status": "not_applicable", "reason": "EPS must be positive"})
            continue
        points = []
        for multiple in multiples:
            implied = float(eps) * float(multiple)
            points.append({"multiple": int(multiple), "implied_price": implied, "upside_vs_current": implied / float(row["price"]) - 1.0})
        output.append({"symbol": row.get("symbol"), "status": "descriptive", "current_price": float(row["price"]), "eps_ttm": float(eps), "points": points, "caveat": "Hypothetical PE sensitivity only; not a target price or valuation recommendation."})
    return output


def analyze_investment(stocks_csv, prices_csv='', as_of='2025-12-31', profile='balanced', max_pe=35., min_growth=0., max_debt=2., weight_cap=.30, max_names=5, method='equal', data_kind='user_import'):
    cutoff=_date(as_of,'研究日')
    if cutoff>dt.date.today(): raise ValueError('研究日不得晚于今天')
    if profile not in PROFILES: raise ValueError('未知筛选偏好')
    max_pe=_num(max_pe,'PE上限'); min_growth=_num(min_growth,'收入增长下限'); max_debt=_num(max_debt,'负债权益比上限')
    if not 0<max_pe<=200 or not -1<=min_growth<=2 or not 0<=max_debt<=20: raise ValueError('筛选条件超出允许范围')
    if isinstance(max_names,bool) or not isinstance(max_names,int) or not 1<=max_names<=50: raise ValueError('最大持仓数须为1–50整数')
    raw_stocks=_csv(stocks_csv,STOCK_FIELDS,'stocks.csv',200)
    stocks=[]; known=set(); currencies=set()
    for i,raw in enumerate(raw_stocks,2):
        r=dict(raw); symbol=_symbol(r['symbol'],f'stocks第{i}行symbol')
        if symbol in known: raise ValueError(f'stocks第{i}行: 重复代码{symbol}')
        known.add(symbol)
        for f in ['name','sector','source']:
            if not r[f] or len(r[f])>500: raise ValueError(f'stocks第{i}行{f}: 必须非空且小于500字')
        if not re.fullmatch(r'[A-Z]{3}',r['currency']): raise ValueError(f'stocks第{i}行currency: 须为3位币种如USD')
        currencies.add(r['currency'])
        for field in ['price_as_of','period_end','filed_at']: _date(r[field],f'stocks第{i}行{field}')
        if r['period_end']>r['filed_at']: raise ValueError(f'stocks第{i}行: 报告期末不能晚于披露日')
        for field in NUMERIC: r[field]=_num(r[field],f'stocks第{i}行{field}',field!='price')
        if r['price']<=0: raise ValueError(f'stocks第{i}行price: 价格须大于0')
        stocks.append(r)
    if len(currencies)!=1: raise ValueError('只支持单币种股票池；请先统一价格与EPS币种，不能直接混合')
    history={s:[] for s in known}; future_prices=0; seen=set()
    if prices_csv and prices_csv.strip():
        for i,r in enumerate(_csv(prices_csv,PRICE_FIELDS,'prices.csv',80000),2):
            _date(r['date'],f'prices第{i}行date');symbol=_symbol(r['symbol'],f'prices第{i}行symbol')
            if symbol not in known: raise ValueError(f'prices第{i}行: {symbol}未在stocks中定义')
            key=(symbol,r['date'])
            if key in seen: raise ValueError(f'prices第{i}行: 重复日期与代码{key}')
            seen.add(key); price=_num(r['adj_close'],f'prices第{i}行adj_close')
            if price<=0: raise ValueError(f'prices第{i}行adj_close: 价格须大于0')
            if r['date']>as_of: future_prices+=1;continue
            history[symbol].append({'date':r['date'],'close':price})
    rows=[]; evidence=[]; price_frames={}
    for r in stocks:
        symbol=r['symbol'];reasons=[]
        if r['filed_at']>as_of:reasons.append('future_filing')
        if r['price_as_of']>as_of:reasons.append('future_price')
        if (cutoff-_date(r['price_as_of'],'price_as_of')).days>120:reasons.append('stale_price')
        if (cutoff-_date(r['filed_at'],'filed_at')).days>550:reasons.append('stale_filing')
        missing=[f for f in NUMERIC if r[f] is None]
        if missing:reasons.append('missing_metrics')
        pe=r['price']/r['eps_ttm'] if r['eps_ttm'] is not None and r['eps_ttm']>0 else None
        if r['eps_ttm'] is not None and r['eps_ttm']<=0:reasons.append('nonpositive_eps')
        if pe is not None and pe>max_pe:reasons.append('pe_above_limit')
        if r['revenue_growth'] is not None and r['revenue_growth']<min_growth:reasons.append('growth_below_limit')
        if r['debt_to_equity'] is not None and r['debt_to_equity']>max_debt:reasons.append('debt_above_limit')
        if r['debt_to_equity'] is not None and r['debt_to_equity']<0:reasons.append('negative_equity_proxy')
        if any(r[f] is not None and r[f]<=0 for f in ['operating_margin','fcf_margin']):reasons.append('nonpositive_margin')
        components=score_components(r,pe,profile) if not missing and pe is not None and r['debt_to_equity']>=0 else None
        bars=sorted(history[symbol],key=lambda x:x['date']); warnings=[]
        vol=drawdown=momentum=None
        if len(bars)>1:
            p=np.array([b['close'] for b in bars]);ret=p[1:]/p[:-1]-1
            if len(ret)>=20:vol=float(np.std(ret[-20:],ddof=1)*math.sqrt(252))
            if len(p)>20:momentum=float(p[-1]/p[-21]-1)
            drawdown=float(np.min(p/np.maximum.accumulate(p)-1))
        if len(bars)<41:warnings.append('不足41个价格观测，不能估计共同40期风险')
        price_stale = bars and (cutoff-_date(bars[-1]['date'],'date')).days>7
        if price_stale:warnings.append('历史价格末日距研究日超过7天，已停止本标的组合压力计算')
        if bars and not price_stale:price_frames[symbol]=pd.DataFrame(bars)
        eid='stock-'+symbol
        evidence.append({'evidence_id':eid,'source':r['source'],'filed_at':r['filed_at'],'period_end':r['period_end'],'price_as_of':r['price_as_of'],'inputs':r,'raw_hash':hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest(),'verified':False})
        rows.append({**r,'entity_id':symbol,'pe':pe,'passed':not reasons,'exclusions':reasons,'reasons':[REASONS[x] for x in reasons],'missing':missing,'warnings':warnings,'components':components,'score':{'score':components['total'] if components else None},'market':{'volatility_20d':vol,'return_20d':momentum,'max_drawdown':drawdown,'observations':len(bars)},'evidence_ids':[eid]})
    selected=[r['symbol'] for r in sorted(rows,key=lambda x:(-(x['score']['score'] or 0),x['symbol'])) if r['passed']]
    screen={'rows':rows,'selected':selected,'excluded':[{'symbol':r['symbol'],'reasons':r['reasons']} for r in rows if not r['passed']], 'criteria':{'profile':profile,'max_pe':max_pe,'min_growth':min_growth,'max_debt':max_debt,'positive_eps_and_margins':True},'universe_size':len(rows)}
    portfolio=build_portfolio(screen,method=method,max_names=max_names,min_names=1,weight_cap=_num(weight_cap,'单票上限'))
    risk=portfolio_stress(portfolio['holdings'],price_frames)
    valuation=valuation_sensitivity(rows)
    warnings=['比较必须使用一致的TTM、会计与复权口径；本工具不核验来源真实性。','当前权重历史重放不是历史可交易回测，不证明收益。','该财务规则主要用于非金融企业，不适用于银行、保险、REIT等需要专门指标的行业。']
    if future_prices:warnings.append(f'{future_prices}条未来价格已排除')
    if any(r['source'].startswith('demo:') for r in stocks):data_kind='synthetic'
    elif data_kind!='synthetic':data_kind='user_import'
    result={'schema_version':'investment-v0.3','as_of':as_of,'data_kind':data_kind,'data_label':'合成示例，非真实证券' if data_kind=='synthetic' else '用户提供，未独立核验','currency':next(iter(currencies)),'screen':screen,'portfolio':portfolio,'risk':risk,'valuation_sensitivity':valuation,'warnings':warnings,'evidence_ledger':evidence,'parameters':{'profile':profile,'max_pe':max_pe,'min_growth':min_growth,'max_debt':max_debt,'weight_cap':weight_cap,'max_names':max_names,'method':method},'trace':[{'step':'校验数据','result':f'{len(rows)}家公司，{len(seen)}条价格'}, {'step':'筛选候选','result':f'{len(selected)}家通过规则；通过不等于推荐买入'}, {'step':'配置研究组合','result':f'{len(portfolio["holdings"])}个候选，现金{portfolio["cash_weight"]:.1%}'}, {'step':'压力诊断','result':risk['status']}], 'input_hash':hashlib.sha256((stocks_csv+'\n'+prices_csv).encode()).hexdigest()}
    result['content_hash']=hashlib.sha256(json.dumps(result,sort_keys=True,allow_nan=False,ensure_ascii=False).encode()).hexdigest()
    result['memo']=investment_memo(result)
    return result


def investment_memo(r):
    s,p=r['screen'],r['portfolio']; params=r['parameters']
    lines=['# FinPilot 投资研究备忘录',f'研究截止日：{r["as_of"]}；数据：{r["data_label"]}；币种：{r["currency"]}。',
           '本报告是研究辅助，不构成个性化投资建议。核心无需LLM。',
           '## 候选筛选',f'输入{s["universe_size"]}家公司，{len(s["selected"])}家通过。PE≤{params["max_pe"]}，收入增长≥{params["min_growth"]:.1%}，债务权益比≤{params["max_debt"]}，要求正EPS及正利润/现金流率。',
           '排序为固定阈值的描述性评分，不是盈利概率。']
    for row in s['rows']:
        score='—' if row['score']['score'] is None else f'{row["score"]["score"]:.2f}'
        lines.append(f'{row["symbol"]} {row["name"]}：'+('通过' if row['passed'] else '排除：'+'；'.join(row['reasons']))+f'；评分{score}；来源{row["source"]}；披露{row["filed_at"]}。')
    lines+=['## 配置草案',f'规则{p["method"]}，单票上限{params["weight_cap"]:.1%}，现金{p["cash_weight"]:.1%}。']
    for h in p['holdings']:lines.append(f'{h["entity_id"]}：{h["weight"]:.2%}，行业{h["sector"]}。')
    lines+=['## 估值敏感性','以下为 EPS × 假设 PE 的情景表，不是目标价：']
    for item in r.get('valuation_sensitivity', []):
        if item.get('status') == 'descriptive':
            lines.append(item['symbol']+'：'+', '.join(f'{p["multiple"]}x→{p["implied_price"]:.2f}（相对当前{p["upside_vs_current"]:.1%}）' for p in item['points']))
        else:
            lines.append(item.get('symbol','?')+'：不可适用（'+item.get('reason','')+'）')
    lines+=['## 风险诊断','参数尾部量为零均值正态一日估计；历史20期按当前权重逐期再平衡重放，不是回测收益。']
    for x in r['risk']['scenarios']:
        loss='不可计算' if x['portfolio_loss'] is None else f'{x["portfolio_loss"]:.2%}'
        lines.append(f'{x["name"]}（{x.get("horizon_label", "")}）：损失{loss}。正数损失、负数收益。')
    lines+=['## 人工核对',*r['warnings'],*r['risk']['warnings'],'后续仍需分析商业模式、盈利可持续性、治理、估值可比性和组合适配；不自动下单。',f'内容哈希：{r["content_hash"]}']
    return '\n\n'.join(lines)+'\n'


def demo_inputs(as_of='2025-12-31'):
    """Deterministic synthetic stock pool for an offline, fully runnable case."""
    cutoff=_date(as_of,'演示截止日')
    out=io.StringIO();w=csv.writer(out);w.writerow(STOCK_FIELDS)
    specs=[('DEMO01','示例云服务','软件',40,2,.18,.24,.18,.25),('DEMO02','示例医疗设备','医疗器械',60,3,.11,.2,.14,.45),('DEMO03','示例高估值芯片','半导体',120,2,.3,.22,.08,.6),('DEMO04','示例亏损消费','可选消费',20,-1,-.05,-.08,-.1,1.2),('DEMO05','示例工业自动化','工业',50,2.5,.07,.16,.12,.8),('DEMO06','示例网络设备','通信设备',36,2.4,.13,.18,.16,.4),('DEMO07','示例高杠杆材料','原材料',24,1.2,.02,.1,.03,3.8),('DEMO08','示例初创设备','电子设备',30,1.5,.16,.18,.1,.5)]
    filed=(cutoff-dt.timedelta(days=45)).isoformat();period=(cutoff-dt.timedelta(days=120)).isoformat()
    for symbol,name,sector,price,eps,g,op,fcf,debt in specs:
        # DEMO08 is a deliberate future-filing/insufficient-history case.
        filing=(cutoff+dt.timedelta(days=15)).isoformat() if symbol=='DEMO08' else filed
        w.writerow([symbol,name,sector,'USD',as_of,price,eps,g,op,fcf,debt,period,filing,'demo://synthetic/'+symbol])
    hist=io.StringIO();pw=csv.writer(hist);pw.writerow(PRICE_FIELDS)
    start=dt.date(max(2018,cutoff.year-4),1,2);dates=pd.bdate_range(start,cutoff);common=random.Random(901);shocks=[common.gauss(0,.008) for _ in dates]
    for i,spec in enumerate(specs):
        symbol,_,_,end_price,*_=spec;rng=random.Random(1000+i);path=[];price=100.
        for j,date in enumerate(dates): price*=1+max(-.15,min(.15,shocks[j]+rng.gauss(0,.005+i*.001)));path.append(price)
        begin=max(0,len(dates)-20) if i==7 else 0
        for j in range(begin,len(dates)):pw.writerow([dates[j].date().isoformat(),symbol,f'{path[j]/path[-1]*end_price:.6f}'])
    return {'stocks_csv':out.getvalue(),'prices_csv':hist.getvalue(),'as_of':as_of,'data_kind':'synthetic'}
