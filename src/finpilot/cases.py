"""Unit-aware historical facts and explicit what-if calculations. Never a trade signal."""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[2] / 'examples' / 'real_cases'
_CASE_PATH = _DATA / 'historical_reference_snapshots.json'
_FINANCIAL_CASE_PATH = _DATA / 'financial_casebook.json'


def historical_case_catalog(path=None):
    data=json.loads(Path(path or _CASE_PATH).read_text(encoding='utf-8'))
    if data.get('data_status')!='public_reference_snapshot': raise ValueError('snapshot type missing')
    for case in data['cases']:
        obs=case['observations']
        if len(obs)<2 or not case['source_urls']: raise ValueError('case needs values and sources')
        if any(not isinstance(x['value'],(int,float)) or not math.isfinite(x['value']) or x['value']<=0 for x in obs): raise ValueError('invalid observed value')
    return data


def analyze_reference_case(case):
    obs=case.get('observations',[])
    if len(obs)<2:return {'status':'insufficient','case_id':case.get('case_id')}
    start,end=float(obs[0]['value']),float(obs[-1]['value'])
    result={'status':'valid','case_id':case['case_id'],'asset':case['asset'],'start_date':obs[0]['date'],
            'end_date':obs[-1]['date'],'start_value':start,'end_value':end,'unit':case['currency'],
            'source_urls':case['source_urls'],'data_status':'public_reference_snapshot',
            'caveat':'Sparse historical reference points; not a complete series, forecast, backtest, or investment recommendation.'}
    if case['currency']=='percent':
        result.update(change_percentage_points=end-start,change_bps=(end-start)*100,
                      formula='change_bps = (yield_percent_end - yield_percent_start) * 100',
                      interpretation='收益率变动不是债券回报，禁止把相对涨幅当持债收益。')
    else:
        trough=min(float(o['value']) for o in obs);i=[float(o['value']) for o in obs].index(trough)
        result.update(trough_value=trough,trough_date=obs[i]['date'],peak_to_trough_change=trough/start-1,
                      trough_to_end_change=end/trough-1,start_to_end_change=end/start-1,
                      formula='endpoint_change = end / start - 1',
                      interpretation='仅所选点位区间价格变化，不含分红、费用；稀疏点位不能估计波动、VaR或完整最大回撤。')
    return result


def analyze_all_reference_cases(path=None):
    return [analyze_reference_case(c) for c in historical_case_catalog(path)['cases']]


def financial_casebook(path=None):
    data=json.loads(Path(path or _FINANCIAL_CASE_PATH).read_text(encoding='utf-8'))
    if data.get('data_status')!='official_public_snapshot':raise ValueError('casebook type missing')
    for c in data['cases']:
        if not c.get('source_urls') or not c.get('questions'):raise ValueError('sources and questions required')
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in c['metrics'].values()):raise ValueError('invalid fact')
    return data


def financial_case_metrics(case):
    m=case['metrics'];derived={};formulas={};revenue=m.get('revenue',m.get('total_net_sales'))
    if revenue:
        if 'net_income' in m:
            derived['net_margin']=m['net_income']/revenue;formulas['net_margin']='net_income / revenue'
        if 'operating_income' in m:
            derived['operating_margin']=m['operating_income']/revenue;formulas['operating_margin']='operating_income / revenue'
    if 'one_time_tax_charge_approx' in m:
        derived['one_time_tax_charge_as_pct_net_income']=m['one_time_tax_charge_approx']/m['net_income']
        formulas['one_time_tax_charge_as_pct_net_income']='approximate tax charge / GAAP net income; not adjusted net income'
    return {'case_id':case['case_id'],'company_or_instrument':case.get('company',case.get('instrument')),
            'metrics':m,'derived_metrics':derived,'formulas':formulas,'questions':case['questions'],
            'source_urls':case['source_urls'],'data_status':case['data_status'],'unit':case['currency']}


def all_financial_cases(path=None):
    return [financial_case_metrics(c) for c in financial_casebook(path)['cases']]


def endpoint_exposure(start, end, exposure=.6, capital=100000):
    vals=(start,end,exposure,capital)
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):raise ValueError('finite numbers required')
    if start<=0 or end<=0 or not 0<=exposure<=1 or capital<=0:raise ValueError('invalid exposure scenario')
    change=end/start-1
    return {'asset_price_change':change,'portfolio_change':exposure*change,'hypothetical_pnl':capital*exposure*change,
            'ending_value':capital*(1+exposure*change),'assumptions':'起点买入后持有，现金零收益、不再平衡、无分红费用；情景而非真实组合收益。'}


def futures_pnl(entry=20.,settlement=-37.63,contracts=1,unit_size=1000,margin=10000.):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in [entry,settlement,contracts,unit_size,margin]):raise ValueError('finite numbers required')
    if contracts<1 or contracts!=int(contracts) or unit_size<=0 or margin<=0:raise ValueError('invalid contract assumptions')
    pnl=(settlement-entry)*contracts*unit_size
    return {'pnl':pnl,'pnl_to_hypothetical_margin':pnl/margin,'assumptions':'仅多头期货价差示例；入场价、张数、合约单位、保证金均为用户假设。未建模逐日盯市、追加保证金、展期及交割。'}
