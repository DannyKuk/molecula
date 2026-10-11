import pytest

from molecula.ingest.__main__ import main


def test_unknown_step_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["everything"])

    assert exit_info.value.code == 2
    assert "invalid choice: 'everything'" in capsys.readouterr().err
