import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from molecula.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
COOLIFY_SERVICES = ["fetch", "backend", "frontend"]
SETTING_KEYS = {name.upper() for name in Settings.model_fields}
PLACEHOLDER = re.compile(r"\$\{([A-Z_]+)")


def services(file_name: str) -> dict[str, Any]:
    compose = yaml.safe_load((REPO_ROOT / file_name).read_text(encoding="utf-8"))
    return compose["services"]


LOCAL = services("docker-compose.yaml")
COOLIFY = services("docker-compose.coolify.yaml")


def test_coolify_file_runs_the_local_services_but_mcp() -> None:
    assert sorted(COOLIFY) == sorted(COOLIFY_SERVICES)
    assert "mcp" in LOCAL


@pytest.mark.parametrize("name", COOLIFY_SERVICES)
def test_coolify_service_publishes_no_port(name: str) -> None:
    assert "ports" not in COOLIFY[name]


@pytest.mark.parametrize("name", COOLIFY_SERVICES)
def test_coolify_service_builds_and_runs_as_locally(name: str) -> None:
    local_context = LOCAL[name]["build"]
    coolify_context = COOLIFY[name]["build"]
    if isinstance(local_context, dict):
        local_context, coolify_context = local_context["context"], coolify_context["context"]
    assert coolify_context == local_context
    assert COOLIFY[name].get("command") == LOCAL[name].get("command")
    assert COOLIFY[name].get("depends_on") == LOCAL[name].get("depends_on")


@pytest.mark.parametrize("name", ["fetch", "backend"])
def test_coolify_backend_variables_are_settings(name: str) -> None:
    environment = COOLIFY[name]["environment"]
    assert set(environment) <= SETTING_KEYS
    for key, value in environment.items():
        assert PLACEHOLDER.findall(str(value)) in ([], [key])


def test_coolify_frontend_needs_the_api_url_from_the_server() -> None:
    args = COOLIFY["frontend"]["build"]["args"]
    assert set(args) == set(LOCAL["frontend"]["build"]["args"])
    assert args["NEXT_PUBLIC_API_URL"] == "${NEXT_PUBLIC_API_URL:?}"
    assert set(COOLIFY["frontend"]["environment"]) == set(LOCAL["frontend"]["environment"])
