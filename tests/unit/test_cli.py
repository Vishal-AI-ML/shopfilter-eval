from pathlib import Path

from typer.testing import CliRunner

from packages.cli.app import app

runner = CliRunner()


def test_evaluate_command_writes_artifact_and_returns_review(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--dataset",
            "golden-v1",
            "--system",
            "demo-v1",
            "--top-k",
            "10",
            "--artifact-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 2
    assert "ShopFilter Evaluation Summary" in result.output
    assert "Cases: 20 | Passed: 19 | Failed: 1" in result.output
    assert "Verdict: REVIEW" in result.output
    assert len(list(tmp_path.glob("run-*.json"))) == 1


def test_unsupported_system_returns_execution_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "evaluate",
            "--system",
            "unknown-system",
            "--artifact-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 3
    assert "EXECUTION ERROR" in result.output
