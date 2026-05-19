from pathlib import Path


def test_oracle_deploy_preserves_runtime_data_directories() -> None:
    workflow = Path(".github/workflows/deploy-oracle.yml").read_text(encoding="utf-8")

    assert "--exclude 'data/'" in workflow
    assert "--exclude 'reports/wagn/'" in workflow
