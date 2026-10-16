import argparse
import logging
import sys
from collections.abc import Callable

from molecula.config import Settings, get_settings
from molecula.ingest import complexes, compounds, export, fetch, index, labels, targets

STEPS: dict[str, Callable[[Settings], int]] = {
    "compounds": compounds.run,
    "targets": targets.run,
    "labels": labels.run,
    "complexes": complexes.run,
    "index": index.run,
    "export": export.run,
    "fetch": fetch.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m molecula.ingest", description="Run a build step that fills the store."
    )
    parser.add_argument("step", choices=STEPS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="fetch only: replace an existing store with the release; local updates are lost",
    )
    args = parser.parse_args(argv)
    if args.force and args.step != "fetch":
        parser.error("--force applies only to fetch")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.step == "fetch":
        return fetch.run(get_settings(), force=args.force)
    return STEPS[args.step](get_settings())


if __name__ == "__main__":
    sys.exit(main())
