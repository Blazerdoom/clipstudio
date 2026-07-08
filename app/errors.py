"""Shared error types.

`UserError` carries a message meant to be shown verbatim to the user (no stack
trace, no class-name prefix). The job runner special-cases it.
"""
from __future__ import annotations


class UserError(Exception):
    """A failure whose message is safe and useful to show directly in the UI."""
