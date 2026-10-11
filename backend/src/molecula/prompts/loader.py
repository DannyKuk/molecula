import re
import string
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
NAME = re.compile(r"[a-z0-9_]+(/[a-z0-9_]+)*")


class PromptError(Exception):
    """Base for every error the prompt loader raises."""


class PromptNotFound(PromptError):
    """No prompt file has this name, or the name isn't a valid prompt name."""


class PromptFormatError(PromptError):
    """The prompt file has a placeholder that isn't a plain `{name}`, or an unescaped brace."""


class PromptVariableError(PromptError):
    """The variables passed to `load` don't match the prompt's placeholders."""


@dataclass(frozen=True)
class Template:
    name: str
    # Literal text alternating with placeholder names, as `string.Formatter.parse` splits it.
    parts: tuple[tuple[str, str | None], ...]

    @property
    def placeholders(self) -> frozenset[str]:
        return frozenset(field for _, field in self.parts if field is not None)

    def render(self, variables: dict[str, object]) -> str:
        missing = self.placeholders - variables.keys()
        unused = variables.keys() - self.placeholders
        if missing or unused:
            raise PromptVariableError(
                f"prompt {self.name!r}: missing variables {sorted(missing)}, "
                f"unused variables {sorted(unused)}"
            )
        return "".join(
            literal + ("" if field is None else str(variables[field]))
            for literal, field in self.parts
        )


def parse(name: str, text: str) -> Template:
    """Split a prompt into literal text and `{name}` placeholders; `{{` and `}}` are literal
    braces. Anything else in braces (JSON, `{0}`, `{a.b}`, `{a!r}`, `{a:>3}`) is an error."""
    try:
        fields = list(string.Formatter().parse(text))
    except ValueError as e:
        raise PromptFormatError(
            f"prompt {name!r}: {e}; write literal braces as {{{{ and }}}}"
        ) from e
    for _, field, spec, conversion in fields:
        if field is not None and (not field.isidentifier() or spec or conversion):
            written = (
                field + (f"!{conversion}" if conversion else "") + (f":{spec}" if spec else "")
            )
            raise PromptFormatError(
                f"prompt {name!r}: bad placeholder {{{written}}}; placeholders are {{name}} "
                "and literal braces are written as {{ and }}"
            )
    return Template(name, tuple((literal, field) for literal, field, _, _ in fields))


class PromptLoader:
    """Loads prompts from the `.md` files under `root`, reading and parsing each file once."""

    def __init__(self, root: Path = PROMPTS_DIR) -> None:
        self.root = root
        self._templates: dict[str, Template] = {}

    def load(self, name: str, /, **variables: object) -> str:
        """The prompt `name` (e.g. "agent/system" for `agent/system.md`) with its
        `{placeholders}` filled from `variables`; every placeholder must get a variable and
        every variable must be used."""
        return self.template(name).render(variables)

    def template(self, name: str) -> Template:
        """The parsed prompt; the file is read on first use and kept until the process ends."""
        if name not in self._templates:
            self._templates[name] = parse(name, self._read(name))
        return self._templates[name]

    def names(self) -> list[str]:
        """The name of every `.md` file under `root`, valid or not."""
        return sorted(
            path.relative_to(self.root).with_suffix("").as_posix()
            for path in self.root.rglob("*.md")
        )

    def _read(self, name: str) -> str:
        # The name pattern has no dots, backslashes or leading slash, so it can't leave root.
        if not NAME.fullmatch(name):
            raise PromptNotFound(
                f"{name!r} is not a prompt name; names are lowercase path segments like "
                "'agent/system'"
            )
        path = self.root / f"{name}.md"
        if not path.is_file():
            raise PromptNotFound(f"no prompt {name!r} (looked for {path})")
        return path.read_text(encoding="utf-8")


default_loader = PromptLoader()


def load(name: str, /, **variables: object) -> str:
    """The prompt `name` with its `{placeholders}` filled; see `PromptLoader.load`."""
    return default_loader.load(name, **variables)
