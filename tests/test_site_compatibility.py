"""Static-site compatibility gates for schema-v2/v3 deployment payloads."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mom_index.cli import _cmd_validate
from mom_index.config import PROJECT_ROOT
from scripts import build_site, check_site


def _payload_copy(tmp_path, version: int):
    payload = json.loads(
        (PROJECT_ROOT / "data" / "dashboard_data.json").read_text(encoding="utf-8")
    )
    payload["schema_version"] = version
    if version == 2:
        payload.pop("market_context", None)
        payload.get("methodology", {}).pop("confidence_model_version", None)
        latest = payload.get("latest")
        sectors = latest.get("sectors") if isinstance(latest, dict) else None
        if isinstance(sectors, dict):
            for sector_value in sectors.values():
                if isinstance(sector_value, dict):
                    sector_value.pop("sample_quality", None)
    payload_path = tmp_path / f"dashboard-v{version}.json"
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload_path


@pytest.mark.parametrize("version", [2, 3])
def test_build_and_check_supported_payloads(tmp_path, monkeypatch, version):
    payload_path = _payload_copy(tmp_path, version)
    monkeypatch.setattr(build_site, "PAYLOAD_SRC", payload_path)
    site = tmp_path / f"site-v{version}"

    build_site.build(site)
    check_site.check(site)

    copied = json.loads(
        (site / "data" / "dashboard_data.json").read_text(encoding="utf-8")
    )
    assert copied["schema_version"] == version


def test_build_rejects_unknown_payload_version(tmp_path, monkeypatch):
    payload_path = _payload_copy(tmp_path, 99)
    monkeypatch.setattr(build_site, "PAYLOAD_SRC", payload_path)

    with pytest.raises(ValueError, match="schema-v2 or schema-v3"):
        build_site.build(tmp_path / "unsupported-site")


def test_cli_does_not_mislabel_legacy_payload(tmp_path, capsys):
    payload_path = _payload_copy(tmp_path, 2)

    assert _cmd_validate(SimpleNamespace(payload=str(payload_path))) == 0

    output = capsys.readouterr().out
    assert "valid dashboard payload" in output
    assert "legacy schema v2 compatibility view" in output
    assert "valid schema-v3 payload" not in output
