#!/usr/bin/env python3
"""Assemble the single-file site.

A published artifact cannot fetch anything, so the template, the data payload and the
application code are concatenated into one HTML file.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

out = (
    (SITE / "index.template.html").read_text(encoding="utf-8")
    + "\n<script>\n" + (SITE / "payload.js").read_text(encoding="utf-8")
    + "\n</script>\n<script>\n" + (SITE / "app.js").read_text(encoding="utf-8")
    + "\n</script>\n"
)
(SITE / "index.html").write_text(out, encoding="utf-8")
print(f"wrote {SITE / 'index.html'} ({len(out) / 1e6:.2f} MB)")
