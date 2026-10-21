from collections.abc import Iterator

import pytest

from molecula.main import app


@pytest.fixture(autouse=True)
def login_off() -> Iterator[None]:
    """The routes run without a login, as with an empty CLERK_JWT_KEY; tests of the login set
    their own."""
    app.state.login = None
    yield
    del app.state.login
