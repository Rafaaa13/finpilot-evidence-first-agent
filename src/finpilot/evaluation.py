"""Versioned offline acceptance cases; not a live-model benchmark."""
from __future__ import annotations
import math
import hashlib
import json
import copy
from pathlib import Path
from .pipeline import run_fixture, _numeric_consistency
from .data import FixtureProvider, validate_ticker, validate_as_of
from .backtest import leakage_check
from .risk import credit_losses, bond_price, bond_risk, black_scholes_price, _auc
from .serialization import json_safe
from .runtime import run_agent


def evaluate() -> dict:
    cases = []
    def check(name, actual, expected=True):
        cases.append({'name': name, 'passed': bool(actual == expected), 'actual': actual, 'expected': expected})
    def rejects(name, fn):
        try:
            fn()
            check(name, False)
        except (ValueError, TypeError):
            check(name, True)
    run = run_fixture('DEMO', output_dir=None)
    other = run_fixture('DEMO', output_dir=None)
    check('相同输入的内容哈希一致', run['result_hash'] == other['result_hash'])
    check('每次运行有独立ID', run['run_id'] != other['run_id'])
    check('正常截止日门禁通过', run['leakage_check']['passed'])
    check('模板数字与引用逐项校验', _numeric_consistency(run)['passed'])
    bad = copy.deepcopy(run); bad['claims'][0]['text'] += ' 盈利100%'
    check('被篡改叙述应阻断', not _numeric_consistency(bad)['passed'])
    bad = copy.deepcopy(run); bad['claims'][0]['evidence_ids'] = ['invented']
    check('伪造证据ID应阻断', not _numeric_consistency(bad)['passed'])
    early = run_fixture('DEMO', '2021-06-30', output_dir=None, include_risk_lab=False)
    check('无数据时拒答而非补0', not early['claims'] and early['score']['score'] is None)
    check('未来财报披露必须阻断', not leakage_check([{'metric':'revenue','effective_at':'2024-01-01','filed_at':'2025-02-01'}], '2024-12-31','2025-01-02')['passed'])
    check('同日信号成交必须阻断', not leakage_check([], '2024-01-01','2024-01-01')['passed'])
    old = FixtureProvider().load('DEMO','2023-12-31').observations
    new = FixtureProvider().load('DEMO','2025-12-31').observations
    check('调整as-of不改变历史数据', {o.raw_ref for o in old}.issubset({o.raw_ref for o in new}))
    rejects('拒绝路径形ticker', lambda:validate_ticker('../AAPL'))
    rejects('拒绝非法日期', lambda:validate_as_of('2025-02-30'))
    loans = [{'pd':.1,'lgd':.5,'ead':100}, {'pd':.2,'lgd':.25,'ead':900}]
    check('两笔贷款手算EL=50', math.isclose(credit_losses(loans)['expected_loss_amount'], 50))
    check('压力PD/LGD截断在1', credit_losses(loans,10,1)['expected_loss_amount'] == 1000)
    rejects('缺PD不能默认为零', lambda:credit_losses([{'lgd':.5,'ead':100}]))
    check('平价债券价格等于面值', math.isclose(bond_price(1000,.04,.04,5), 1000, abs_tol=1e-8))
    check('零息债凸性含贴现分母平方', math.isclose(bond_risk(100,0,.05,1,1)['convexity'], 2/1.05**2))
    c=black_scholes_price(100,100,.05,.2,1); p=black_scholes_price(100,100,.05,.2,1,'put')
    check('看涨看跌平价', math.isclose(c-p,100-100*math.exp(-.05),abs_tol=1e-8))
    check('含并列分数AUC=0.875', _auc([1,0,1,0],[.8,.4,.4,.1]) == .875)
    check('严格JSON非有限值转null', json_safe({'a':float('nan')}) == {'a':None})
    check('真实成本造成非负拖累', run['backtest']['ablation']['fee_drag'] >= -1e-9)
    check('所有成交晚于信号', all(t['execution_date']>t['signal_date'] for t in run['backtest']['executions']))
    check('离线Agent选用信用工具', 'credit' in next(t['tools'] for t in run_agent(run,'信用压力损失')['trace'] if 'tools' in t))
    check('信用样本切分为120/120', run['risk_lab']['summary']['train_count']==120 and run['risk_lab']['summary']['validation_count']==120)
    return {'suite':'offline-acceptance-v0.2', 'suite_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'status':'pass' if all(c['passed'] for c in cases) else 'fail', 'passed':sum(c['passed'] for c in cases), 'total':len(cases), 'cases':cases, 'scope':'Deterministic offline invariants only; live model / external users / MCP real-service tests not run.'}
