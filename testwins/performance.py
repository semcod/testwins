"""Optional, explicitly separate Chromium CDP telemetry. Not Core Web Vitals."""
from __future__ import annotations
import math


async def measure(cdp, config: dict) -> dict:
    if not config['enabled']: return {'status':'disabled'}
    if cdp is None:
        return {'status':'incomplete' if config['required'] else 'unavailable','reason':'CDP_metrics_require_Chromium'}
    try:
        raw=await cdp.send('Performance.getMetrics')
        metrics={m['name']:m['value'] for m in raw['metrics']}
        selected={k:metrics[k] for k in config['budgets']}
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in selected.values()):raise ValueError('Invalid metric')
    except Exception:
        return {'status':'incomplete' if config['required'] else 'unavailable','reason':'CDP_metrics_unavailable'}
    checks=[{'metric':k,'actual':v,'maximum':config['budgets'][k],
             'status':'passed' if v<=config['budgets'][k] else 'failed'} for k,v in selected.items()]
    return {'status':'failed' if any(c['status']=='failed' for c in checks) else 'passed','checks':checks,
            'source':'CDP Performance.getMetrics','scope':'browser counters at this capture; cumulative counters are not per-step deltas'}
