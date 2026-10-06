from __future__ import annotations
import json
from pathlib import Path
from .pipeline import run_fixture
from .evaluation import evaluate
from .serialization import json_safe


def build_workbench(server: bool = False) -> str:
    payload = {'server': server, 'runs': {d:run_fixture('DEMO',d,output_dir=None) for d in ['2025-12-31','2023-12-31','2021-06-30']}, 'evaluation': evaluate()}
    raw = json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    marker = '<script id="payload" type="application/json">__PAYLOAD__</script>'
    return Path(__file__).with_name('workbench.html').read_text(encoding='utf-8').replace(marker, '<script id="payload" type="application/json">' + raw + '</script>')


def render_html(result: dict) -> str:
    return build_workbench()


if __name__ == '__main__':
    print(build_workbench())
