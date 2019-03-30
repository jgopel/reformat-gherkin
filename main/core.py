import traceback
from functools import partial
from pathlib import Path
from typing import Set, Tuple

import click

from .errors import BaseError, NothingChanged
from .options import Options, WriteBackMode
from .parser import parse
from .utils import diff, dump_to_file

out = partial(click.secho, bold=True, err=True)
err = partial(click.secho, fg="red", err=True)

REPORT_URL = "https://github.com/ducminh-phan/reformat-gherkin/issues"


def find_sources(src: Tuple[str]) -> Set[Path]:
    sources: Set[Path] = set()

    for s in src:
        path = Path(s).resolve()
        if path.is_dir():
            sources.update(path.rglob("*.feature"))
        elif path.is_file():
            # If a file was explicitly given, we don't care about its extension
            sources.add(path)
        else:
            err(f"invalid path: {s}")

    return sources


def reformat_single_file(src: Path, *, options: Options) -> bool:
    with open(src, "r", encoding="utf-8") as f:
        src_contents = f.read()

    try:
        dst_contents = format_file_contents(src_contents, options=options)
    except NothingChanged:
        return False

    if options.write_back == WriteBackMode.INPLACE:
        with open(src, "w", encoding="utf-8") as f:
            f.write(dst_contents)

    return True


def format_file_contents(src_contents: str, *, options: Options) -> str:
    """
    Reformat the contents a file and return new contents.
    """
    if src_contents.strip() == "":
        raise NothingChanged

    dst_contents = format_str(src_contents, options=options)
    if src_contents == dst_contents:
        raise NothingChanged

    if not options.fast:
        assert_equivalent(src_contents, dst_contents)
        assert_stable(src_contents, dst_contents, options=options)

    return dst_contents


def format_str(src_contents: str, *, options: Options) -> str:
    return ""


def assert_equivalent(src: str, dst: str) -> None:
    """
    Raise AssertionError if `src` and `dst` aren't equivalent.
    """
    src_model = parse(src)

    try:
        dst_model = parse(dst)
    except BaseError as exc:
        log = dump_to_file("".join(traceback.format_tb(exc.__traceback__)), dst)
        raise AssertionError(
            f"INTERNAL ERROR: Invalid file contents are produced: {exc}. "
            f"Please report a bug on {REPORT_URL}. "
            f"This invalid output might be helpful: {log}"
        ) from None

    if src_model != dst_model:
        log = dump_to_file(diff(src_model, dst_model, "src", "dst"))
        raise AssertionError(
            f"INTERNAL ERROR: Black produced code that is not equivalent to "
            f"the source. "
            f"Please report a bug on {REPORT_URL}. "
            f"This diff might be helpful: {log}"
        ) from None


def assert_stable(src: str, dst: str, *, options: Options) -> None:
    """
    Raise AssertionError if `dst` reformats differently the second time.
    """
    newdst = format_str(dst, options=options)
    if dst != newdst:
        log = dump_to_file(
            diff(src, dst, "source", "first pass"),
            diff(dst, newdst, "first pass", "second pass"),
        )
        raise AssertionError(
            f"INTERNAL ERROR: Different contents are produced on the second pass "
            f"of the formatter. "
            f"Please report a bug on {REPORT_URL}. "
            f"This diff might be helpful: {log}"
        ) from None
