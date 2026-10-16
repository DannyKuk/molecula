import pytest

from molecula.config import Settings
from molecula.ingest import fetch
from molecula.ingest.__main__ import main


def test_unknown_step_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["everything"])

    assert exit_info.value.code == 2
    assert "invalid choice: 'everything'" in capsys.readouterr().err


def test_force_is_only_for_fetch(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["index", "--force"])

    assert exit_info.value.code == 2
    assert "--force applies only to fetch" in capsys.readouterr().err


@pytest.mark.parametrize(("argv", "force"), [(["fetch"], False), (["fetch", "--force"], True)])
def test_fetch_gets_the_force_flag(
    monkeypatch: pytest.MonkeyPatch, argv: list[str], force: bool
) -> None:
    calls: list[bool] = []

    def fake_run(settings: Settings, *, force: bool = False) -> int:
        calls.append(force)
        return 0

    monkeypatch.setattr(fetch, "run", fake_run)

    assert main(argv) == 0
    assert calls == [force]
