# Constitution Diff Website

Side-by-side comparison of the Constitution of the Republic of Kazakhstan (1995 vs 2026).

## Build

Requires Python 3.8+. No external dependencies.

```
python3 build.py
```

This reads `old.md` and `new.md` from the repo root and generates `index.html` — a self-contained static page with all CSS and JS inlined.

Open `index.html` in any browser.

## Updating the text

1. Edit `new.md` (or `old.md`) — keep the markdown structure:
   - Preamble as blockquote lines (`> ...`)
   - Sections as `## Раздел I. ...`
   - Articles as `### Статья 1`
   - Numbered paragraphs as `1. ...`, `2. ...`, `3-1. ...`
   - Sub-items as `1) ...`, `2) ...`
2. Run `python3 build.py`
3. Refresh `index.html` in the browser
