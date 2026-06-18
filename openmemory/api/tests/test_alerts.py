"""Validation of Prometheus alert rules (task_09 / ADR-004).

promtool não está disponível no ambiente de teste; aqui validamos a estrutura das
regras e que cada métrica referenciada existe em app/utils/metrics.py.
"""

import os
import re
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import yaml

_API_ROOT = Path(__file__).resolve().parents[1]
_ALERTS = _API_ROOT.parent / "compose" / "alerts.yml"
_METRICS_SRC = (_API_ROOT / "app" / "utils" / "metrics.py").read_text(encoding="utf-8")

# Métricas (nome Prometheus base) usadas pelos alertas.
_REFERENCED = [
    "mcp_search_latency_seconds",
    "write_queue_depth",
    "governance_job_errors_total",
    "backup_last_success_timestamp",
    "project_size_over_threshold",
    "write_worker_error_total",
]


def _rules():
    doc = yaml.safe_load(_ALERTS.read_text(encoding="utf-8"))
    return [r for g in doc["groups"] for r in g["rules"]]


def test_alerts_file_parses_and_has_rules():
    rules = _rules()
    assert len(rules) >= 5


def test_each_rule_is_well_formed():
    for r in _rules():
        assert r.get("alert"), f"regra sem nome: {r}"
        assert r.get("expr"), f"{r['alert']} sem expr"
        assert r["labels"]["severity"] in {"warning", "critical"}
        assert r["annotations"]["summary"]


def test_referenced_metrics_exist_in_metrics_module():
    for metric in _REFERENCED:
        assert metric in _METRICS_SRC, f"métrica ausente em metrics.py: {metric}"


def test_referenced_metrics_appear_in_alert_exprs():
    exprs = " ".join(r["expr"] for r in _rules())
    for metric in _REFERENCED:
        # histograma usa o sufixo _bucket no expr
        base = metric
        assert re.search(re.escape(base), exprs), f"métrica não usada nos alertas: {metric}"
