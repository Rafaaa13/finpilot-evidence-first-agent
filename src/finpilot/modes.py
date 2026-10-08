"""High-level local research presets for novice and professional workflows."""
from __future__ import annotations
from typing import Any

PRESETS = {
    'balanced': {'profile':'balanced','method':'equal','weight_cap':.30,'label':'均衡研究','description':'规则最容易解释，组合不主动追逐单一因子。'},
    'quality': {'profile':'quality','method':'vol_inverse','weight_cap':.20,'label':'质量与分散','description':'更强调质量字段、观察波动与单票上限；不等于低风险保证。'},
    'value': {'profile':'value','method':'score_weighted','weight_cap':.30,'label':'价值敏感','description':'更强调 PE 敏感性和得分权重；需要特别审阅估值陷阱。'},
}


def preset(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise ValueError(f'unknown preset: {name}')
    return dict(PRESETS[name], preset_id=name)


def explain_preset(name: str) -> dict[str, Any]:
    p = preset(name)
    return {'preset_id': name, 'label': p['label'], 'description': p['description'],
            'profile': p['profile'], 'method': p['method'], 'weight_cap': p['weight_cap'],
            'caveat': 'Preset changes deterministic screening/weight rules only; it does not forecast returns or recommend trades.'}
