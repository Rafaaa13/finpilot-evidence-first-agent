"""Distributable public market snapshot helpers."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

_ROOT=Path(__file__).resolve().parents[2]
_PATH=_ROOT/'data/public/sp500_shiller_monthly_2018_2023.csv'


def load_sp500_snapshot()->dict[str,Any]:
    with _PATH.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    if len(rows)!=72: raise ValueError('expected 72 monthly public snapshot rows')
    parsed=[]
    for r in rows:
        parsed.append({k: (r[k] if k in {'date'} else float(r[k])) for k in r})
    return {'dataset_id':'sp500_shiller_monthly_2018_2023','source':'datasets/s-and-p-500','source_url':'https://github.com/datasets/s-and-p-500','license_note':'Upstream applies ODC-PDDL 1.0 but notes original-source licensing should be checked.','data_kind':'public_snapshot','verified':False,'frequency':'monthly','rows':parsed,'caveat':'Monthly index context, not individual-security prices, not real-time and not a trade signal.'}


def market_case_windows()->list[dict[str,Any]]:
    data=load_sp500_snapshot(); rows=data['rows']; cases=[]
    for case_id,title,start,end in [('pre_covid_covid','2018-01 to 2020-12','2018-01-01','2020-12-01'),('rate_shock_2022','2021-12 to 2022-12','2021-12-01','2022-12-01'),('recovery_2023','2022-12 to 2023-12','2022-12-01','2023-12-01')]:
        sub=[r for r in rows if start<=r['date']<=end]; vals=[r['sp500'] for r in sub]; startv=vals[0]; peak=max(vals); trough=min(vals); endv=vals[-1]
        cases.append({'case_id':case_id,'title':title,'start':sub[0]['date'],'end':sub[-1]['date'],'observations':len(sub),'start_value':startv,'peak_value':peak,'trough_value':trough,'end_value':endv,'return':endv/startv-1,'drawdown_from_peak':trough/peak-1,'rows':sub,'source':data['source_url'],'caveat':data['caveat']})
    return cases
