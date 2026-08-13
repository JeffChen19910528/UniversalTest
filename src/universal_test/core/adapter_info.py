"""Shared adapter-description shape (ARCHITECTURE.md §7).

Factored out of `adapters/rest/adapter.py` once a second adapter
(`adapters/frontend`) needed the same shape, per that module's own
docstring; the Browser Adapter (Phase 9) is the third consumer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    version: str
    capabilities: list[str]
