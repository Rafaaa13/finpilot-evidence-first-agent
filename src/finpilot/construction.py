from __future__ import annotations
import csv,io,math
import pandas as pd
from .portfolio import portfolio_stress


def _n(v,label,low=0,high=1):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high: raise ValueError(f'{label} must be in [{low},{high}]')
    return float(v)


def construct(result, prices_csv='', selected=None, method='equal', cash_floor=.1, asset_cap=.3, sector_cap=.5, capital=100000., manual=None, current=None, fee_bps=10.):
    cash_floor=_n(cash_floor,'cash_floor'); asset_cap=_n(asset_cap,'asset_cap',.001); sector_cap=_n(sector_cap,'sector_cap',.001); capital=_n(capital,'capital',1,1e12); fee_bps=_n(fee_bps,'fee_bps',0,500)
    if method not in {'equal','score_weighted','vol_inverse','manual'}: raise ValueError('unknown method')
    rows={r['symbol']:r for r in result['screen']['rows']}; ids=list(result['screen']['selected'] if selected is None else selected)[:5]
    if len(set(ids))!=len(ids) or any(i not in rows or not rows[i]['passed'] for i in ids): raise ValueError('select only distinct passing candidates')
    sectors={i:rows[i]['sector'] for i in ids}; weights=dict.fromkeys(ids,0.); budget=1-cash_floor
    if method=='manual':
        manual=manual or {}
        if any(i not in ids for i in manual): raise ValueError('manual symbol not selected')
        for i in ids: weights[i]=_n(manual.get(i,0),'manual weight')
        sector_total={}
        for i,w in weights.items():
            if w>asset_cap+1e-10: raise ValueError('manual weight exceeds single-name cap')
            sector_total[sectors[i]]=sector_total.get(sectors[i],0)+w
        if sum(weights.values())>budget+1e-10 or any(v>sector_cap+1e-10 for v in sector_total.values()): raise ValueError('manual weights violate cash or sector constraint')
    else:
        raw={i:1. if method=='equal' else max(0,rows[i]['score']['score'] or 0) if method=='score_weighted' else 1/max(rows[i]['market']['volatility_20d'] or 1e-12,1e-12) for i in ids}
        for _ in range(len(ids)*3+3):
            sector_total={}
            for i,w in weights.items(): sector_total[sectors[i]]=sector_total.get(sectors[i],0)+w
            rem=budget-sum(weights.values()); free=[i for i in ids if raw[i]>0 and weights[i]<asset_cap-1e-12 and sector_total.get(sectors[i],0)<sector_cap-1e-12]
            if rem<=1e-12 or not free: break
            total=sum(raw[i] for i in free); delta={i:rem*raw[i]/total for i in free}; scale=1.
            for i in free: scale=min(scale,(asset_cap-weights[i])/delta[i])
            for sec in {sectors[i] for i in free}:
                prop=sum(delta[i] for i in free if sectors[i]==sec); scale=min(scale,(sector_cap-sector_total.get(sec,0))/prop)
            for i in free: weights[i]+=max(0,scale)*delta[i]
    current=current or {}
    if any(i not in rows for i in current): raise ValueError('current position symbol missing')
    if sum(current.values())>1+1e-10: raise ValueError('current weights exceed 100%')
    holdings=[{'entity_id':i,'sector':sectors[i],'weight':weights[i],'price':rows[i]['price'],'amount':capital*weights[i],'reference_shares':capital*weights[i]/rows[i]['price'],'evidence_ids':rows[i]['evidence_ids']} for i in ids]
    frames={}
    if prices_csv.strip():
        for r in csv.DictReader(io.StringIO(prices_csv.lstrip('﻿'))):
            if r['symbol'] in ids and r['date']<=result['as_of']: frames.setdefault(r['symbol'],[]).append({'date':r['date'],'close':float(r['adj_close'])})
    for i in list(frames):
        frames[i]=pd.DataFrame(frames[i]);
        if not frames[i].empty and (pd.Timestamp(result['as_of'])-pd.to_datetime(frames[i]['date']).max()).days>7: del frames[i]
    risk=portfolio_stress(holdings,frames)
    current=current or {}; trades=[{'symbol':i,'current':current.get(i,0),'target':weights.get(i,0),'delta':weights.get(i,0)-current.get(i,0),'amount':capital*(weights.get(i,0)-current.get(i,0))} for i in sorted(set(ids)|set(current))]
    gross=sum(abs(t['amount']) for t in trades); fees=gross*fee_bps/10000; cash=max(0,1-sum(weights.values()))
    return {'schema_version':'construction-v1','method':method,'holdings':holdings,'cash_weight':cash,'weights_sum':sum(weights.values()),'risk':risk,'constraints':{'cash_floor':cash_floor,'asset_cap':asset_cap,'sector_cap':sector_cap},'capital':capital,'trades':trades,'gross_traded_notional':gross,'turnover_one_way':gross/capital/2,'estimated_fees':fees,'cash_after_estimated_fees':capital*cash-fees,'feasibility':'review_cost_cash' if capital*cash<fees else 'feasible_before_execution','caveat':'配置及再平衡草案；不执行交易；无税、流动性和滑点模型。'}
