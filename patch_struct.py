"""Structured patch views (codeflux fork improvement).

:class:`StructuredPatchSet` subclasses :class:`patch.PatchSet` to add
machine-readable access for streaming pipelines. ``patch.py`` itself is
untouched — pure addition:

- accepts ``str`` *or* bytes input (upstream ``fromstring`` only takes bytes
  on Python 3 — ``StringIO`` there is really ``BytesIO``)
- :meth:`to_dict` / :meth:`to_json`: files, hunks and tagged (+/-/
  context) lines as JSON-safe data (bytes decoded)
- :meth:`apply_report`: apply without raising; per-file results instead
"""
from __future__ import annotations

import io
import json
from typing import Any

from patch import PatchSet


def _s(x: Any) -> Any:
    if isinstance(x, (bytes, bytearray)):
        return bytes(x).decode("utf-8", "replace")
    return x


def _tag(line: str) -> str:
    return {"+": "add", "-": "del"}.get(line[:1], "ctx")


class StructuredPatchSet(PatchSet):
    def __init__(self, stream: Any = None):
        if isinstance(stream, str):
            stream = io.BytesIO(stream.encode("utf-8"))
        elif isinstance(stream, io.StringIO):
            stream = io.BytesIO(stream.getvalue().encode("utf-8"))
        super().__init__(stream)

    def to_dict(self) -> dict[str, Any]:
        files = []
        for p in self:
            hunks = []
            for h in p.hunks:
                lines = []
                for ln in h.text:
                    t = _s(ln)
                    lines.append({"tag": _tag(t),
                                  "text": t[1:] if t[:1] in "+-" else t})
                hunks.append({
                    "startsrc": h.startsrc, "linessrc": h.linessrc,
                    "starttgt": h.starttgt, "linestgt": h.linestgt,
                    "invalid": h.invalid, "desc": _s(h.desc), "lines": lines,
                })
            files.append({
                "source": _s(p.source), "target": _s(p.target),
                "type": _s(p.type), "hunks": hunks,
            })
        return {"errors": self.errors, "warnings": self.warnings,
                "files": files}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def apply_report(self, root: str = ".", strip: int = 1) -> dict[str, Any]:
        """Apply hunks under ``root``; never raises, reports per file."""
        if self.errors:
            return {"ok": False, "files": [],
                    "error": "parse errors: %d" % self.errors}
        try:
            ok = self.apply(strip=strip, root=root)
        except Exception as exc:  # noqa: BLE001 - report, don't raise
            return {"ok": False, "files": [], "error": str(exc)[:300]}
        return {
            "ok": bool(ok),
            "files": [{"source": _s(p.source), "target": _s(p.target)}
                      for p in self],
        }
