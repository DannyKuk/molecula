import argparse
import logging
import sys
from collections.abc import Callable

from molecula.config import Settings, get_settings
from molecula.ingest import compounds, labels, targets

STEPS: dict[str, Callable[[Settings], int]] = {
    "compounds": compounds.run,
    "targets": targets.run,
    "labels": labels.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m molecula.ingest", description="Run a build step that fills the store."
    )
    parser.add_argument("step", choices=STEPS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return STEPS[args.step](get_settings())


if __name__ == "__main__":
    sys.exit(main())
