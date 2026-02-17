"""Centralized kernel logging with dim ANSI output."""

import sys

DIM = "\033[2m"
RESET = "\033[0m"


def dim(msg: str, end: str = "\n", flush: bool = True):
    """Print a dim (faint) message to stderr. Used for kernel internals."""
    print(f"{DIM}{msg}{RESET}", end=end, file=sys.stderr, flush=flush)


def dim_raw(msg: str, end: str = "", flush: bool = True):
    """Print dim text to stderr without a newline — for spinners/timers."""
    print(f"{DIM}{msg}{RESET}", end=end, file=sys.stderr, flush=flush)
