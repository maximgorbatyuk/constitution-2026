#!/usr/bin/env python3
"""
Build script for the Constitution Diff Website.
Reads old.md (1995) and new.md (2026), computes word-level diffs,
and generates a self-contained index.html.
"""

import re
import difflib
from dataclasses import dataclass, field
from typing import Optional
import html as html_mod


GITHUB_REPO_URL = "https://github.com/maximgorbatyuk/constitution-2026"
GITHUB_BRANCH = "main"


# ─── Data structures ──────────────────────────────────────────────

@dataclass
class Paragraph:
    number: str          # e.g. "1", "2", "3-1", or "" for unnumbered
    text: str            # the text content (without the number prefix)
    sub_items: list = field(default_factory=list)  # list of (label, text) tuples

@dataclass
class Article:
    number: str          # e.g. "1", "83-1", "94-2"
    title: str           # full title line, e.g. "Статья 1"
    paragraphs: list = field(default_factory=list)  # list of Paragraph
    raw_text: str = ""   # raw text for fallback

@dataclass
class Section:
    number: str          # Roman numeral: "I", "II", etc.
    title: str           # e.g. "Общие положения"
    full_title: str      # e.g. "Раздел I. Общие положения"
    articles: list = field(default_factory=list)  # list of Article

@dataclass
class Constitution:
    preamble: str = ""
    sections: list = field(default_factory=list)  # list of Section


# ─── Parser ───────────────────────────────────────────────────────

def parse_constitution(text: str) -> Constitution:
    """Parse a markdown constitution into structured data."""
    const = Constitution()
    lines = text.split('\n')

    # Extract preamble (blockquote lines at the start)
    preamble_lines = []
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith('>'):
            preamble_lines.append(line[1:].strip())
        elif line.strip() == '' and preamble_lines:
            continue
        elif preamble_lines:
            content_start = i
            break

    const.preamble = '\n'.join(preamble_lines)

    # Split into sections and articles
    current_section = None
    current_article = None
    article_lines = []

    for i in range(content_start, len(lines)):
        line = lines[i]

        # Section header: ## Раздел I. ...
        section_match = re.match(r'^## Раздел\s+([IVXLC]+)\.\s*(.+)$', line)
        if section_match:
            # Save previous article
            if current_article and current_section:
                current_article.paragraphs = parse_paragraphs(article_lines)
                current_article.raw_text = '\n'.join(article_lines)
                current_section.articles.append(current_article)
                current_article = None
                article_lines = []

            current_section = Section(
                number=section_match.group(1),
                title=section_match.group(2).strip(),
                full_title=line[3:].strip()  # remove "## "
            )
            const.sections.append(current_section)
            continue

        # Article header: ### Статья 1, ### Статья 83-1
        article_match = re.match(r'^### Статья\s+(\d+(?:-\d+)?)$', line)
        if article_match:
            # Save previous article
            if current_article and current_section:
                current_article.paragraphs = parse_paragraphs(article_lines)
                current_article.raw_text = '\n'.join(article_lines)
                current_section.articles.append(current_article)

            current_article = Article(
                number=article_match.group(1),
                title=f"Статья {article_match.group(1)}"
            )
            article_lines = []
            continue

        if current_article is not None:
            article_lines.append(line)

    # Don't forget the last article
    if current_article and current_section:
        current_article.paragraphs = parse_paragraphs(article_lines)
        current_article.raw_text = '\n'.join(article_lines)
        current_section.articles.append(current_article)

    return const


def parse_paragraphs(lines: list) -> list:
    """Parse lines into Paragraph objects."""
    paragraphs = []
    current_para = None
    current_sub_items = []
    buffer = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Flush any accumulated buffer into current paragraph
            if buffer and current_para is not None:
                current_para.text += ' ' + ' '.join(buffer)
                buffer = []
            continue

        # Check for numbered paragraph: "1.", "2.", "3-1."
        para_match = re.match(r'^(\d+(?:-\d+)?)\.\s+(.+)$', stripped)
        if para_match:
            # Save previous paragraph
            if current_para is not None:
                if buffer:
                    current_para.text += ' ' + ' '.join(buffer)
                    buffer = []
                current_para.sub_items = current_sub_items
                paragraphs.append(current_para)
                current_sub_items = []

            current_para = Paragraph(
                number=para_match.group(1),
                text=para_match.group(2)
            )
            continue

        # Check for sub-item: "1)", "2)", "1-1)"
        sub_match = re.match(r'^(\d+(?:-\d+)?)\)\s+(.+)$', stripped)
        if sub_match and current_para is not None:
            if buffer:
                current_para.text += ' ' + ' '.join(buffer)
                buffer = []
            current_sub_items.append((sub_match.group(1), sub_match.group(2)))
            continue

        # Continuation line
        if current_para is not None:
            buffer.append(stripped)
        else:
            # Unnumbered paragraph (e.g., article body without number)
            current_para = Paragraph(number="", text=stripped)

    # Save last paragraph
    if current_para is not None:
        if buffer:
            current_para.text += ' ' + ' '.join(buffer)
        current_para.sub_items = current_sub_items
        paragraphs.append(current_para)

    return paragraphs


# ─── Section mapping ──────────────────────────────────────────────

# Each entry: (old_section_number_or_None, new_section_number_or_None, label, is_new)
SECTION_MAP = [
    ("preamble", "preamble", "Преамбула", False),
    ("I",   "I",    None, False),
    ("II",  "II",   None, False),
    ("III", "III",  None, False),
    ("IV",  "IV",   None, False),
    ("V",   "V",    None, False),
    (None,  "VI",   None, True),    # Қазақстан Халық Кеңесі — new
    ("VI",  "VII",  None, False),
    ("VII", "VIII", None, False),
    ("VIII","IX",   None, False),
    (None,  "X",    None, True),    # Внесение изменений — new
    ("IX",  "XI",   None, False),
]


def find_section(const: Constitution, number: str) -> Optional[Section]:
    for s in const.sections:
        if s.number == number:
            return s
    return None


def extract_summary_sections(md_text: str) -> list:
    """Extract all level-2 summary sections as (title, markdown_body)."""
    lines = md_text.splitlines()
    sections = []
    current_title = None
    buffer = []

    for line in lines:
        if line.startswith('## '):
            if current_title is not None:
                body = '\n'.join(buffer).strip()
                if body:
                    sections.append((current_title, body))
            current_title = line[3:].strip()
            buffer = []
            continue

        if current_title is not None:
            buffer.append(line)

    if current_title is not None:
        body = '\n'.join(buffer).strip()
        if body:
            sections.append((current_title, body))

    return sections


def slugify_anchor(text: str, fallback: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug or fallback


def render_inline_markdown(text: str) -> str:
    """Render inline code spans and bold text."""
    def render_plain(segment: str) -> str:
        bold_parts = segment.split('**')
        out = []
        for i, bp in enumerate(bold_parts):
            escaped = html_mod.escape(bp)
            if i % 2 == 1:
                out.append(f'<strong>{escaped}</strong>')
            else:
                out.append(escaped)
        return ''.join(out)

    parts = text.split('`')
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            escaped = html_mod.escape(part)
            out.append(f'<code>{escaped}</code>')
        else:
            out.append(render_plain(part))
    return ''.join(out)


def render_summary_html(summary_md: str) -> str:
    """Render lightweight markdown into HTML."""
    if not summary_md.strip():
        return ""

    parts = []
    list_mode = None

    def close_list() -> None:
        nonlocal list_mode
        if list_mode == 'ul':
            parts.append('</ul>')
        elif list_mode == 'ol':
            parts.append('</ol>')
        list_mode = None

    for raw_line in summary_md.splitlines():
        line = raw_line.strip()

        if not line:
            close_list()
            continue

        if line == '---':
            close_list()
            parts.append('<hr class="summary-sep">')
            continue

        if line.startswith('### '):
            close_list()
            parts.append(f"<h4>{render_inline_markdown(line[4:].strip())}</h4>")
            continue

        if line.startswith('- '):
            if list_mode != 'ul':
                close_list()
                parts.append('<ul>')
                list_mode = 'ul'
            parts.append(f"<li>{render_inline_markdown(line[2:].strip())}</li>")
            continue

        ordered_match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if ordered_match:
            if list_mode != 'ol':
                close_list()
                parts.append('<ol>')
                list_mode = 'ol'
            parts.append(f"<li>{render_inline_markdown(ordered_match.group(2))}</li>")
            continue

        close_list()
        parts.append(f"<p>{render_inline_markdown(line)}</p>")

    close_list()

    return '\n'.join(parts)


# ─── Word-level diff ──────────────────────────────────────────────

def tokenize(text: str) -> list:
    """Split text into tokens (words and whitespace)."""
    return re.findall(r'\S+|\s+', text)


def word_diff(old_text: str, new_text: str) -> tuple:
    """
    Compute word-level diff. Returns (old_html, new_html) with
    <del>/<ins> spans for changes.
    """
    old_tokens = tokenize(old_text)
    new_tokens = tokenize(new_text)

    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens)

    old_parts = []
    new_parts = []

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            chunk = html_mod.escape(''.join(old_tokens[i1:i2]))
            old_parts.append(chunk)
            new_parts.append(chunk)
        elif op == 'delete':
            chunk = html_mod.escape(''.join(old_tokens[i1:i2]))
            old_parts.append(f'<del>{chunk}</del>')
        elif op == 'insert':
            chunk = html_mod.escape(''.join(new_tokens[j1:j2]))
            new_parts.append(f'<ins>{chunk}</ins>')
        elif op == 'replace':
            old_chunk = html_mod.escape(''.join(old_tokens[i1:i2]))
            new_chunk = html_mod.escape(''.join(new_tokens[j1:j2]))
            old_parts.append(f'<del>{old_chunk}</del>')
            new_parts.append(f'<ins>{new_chunk}</ins>')

    return (''.join(old_parts), ''.join(new_parts))


def paragraph_to_text(para: Paragraph) -> str:
    """Convert a paragraph to plain text for diffing."""
    parts = []
    if para.number:
        parts.append(f"{para.number}. {para.text}")
    else:
        parts.append(para.text)
    for label, text in para.sub_items:
        parts.append(f"{label}) {text}")
    return '\n'.join(parts)


def diff_paragraph_html(old_para: Optional[Paragraph], new_para: Optional[Paragraph]) -> tuple:
    """
    Diff two paragraphs. Returns (old_html, new_html).
    If one side is None, the other is fully marked as added/removed.
    """
    if old_para is None and new_para is None:
        return ('', '')

    if old_para is None:
        # Entirely new paragraph
        new_html = render_paragraph_with_marks(new_para, 'ins')
        return ('', new_html)

    if new_para is None:
        # Entirely removed paragraph
        old_html = render_paragraph_with_marks(old_para, 'del')
        return (old_html, '')

    # Both exist — diff them
    old_text = paragraph_to_text(old_para)
    new_text = paragraph_to_text(new_para)

    if old_text == new_text:
        # Identical
        h = render_paragraph_plain(old_para)
        return (h, h)

    old_html, new_html = word_diff(old_text, new_text)
    return (
        wrap_paragraph_number_html(old_para.number, old_html),
        wrap_paragraph_number_html(new_para.number, new_html)
    )


def wrap_paragraph_number_html(number: str, content_html: str) -> str:
    """Wrap already-diffed HTML content, extracting the number from the content
    if present and displaying it as a styled number span."""
    if number:
        # The content already starts with "number. " from paragraph_to_text
        # We need to extract that prefix from the diffed HTML
        # Since the number might be wrapped in <del>/<ins>, we handle it
        # by looking for the pattern at the start
        prefix = f"{html_mod.escape(number)}. "
        if content_html.startswith(prefix):
            rest = content_html[len(prefix):]
            return f'<span class="para-num">{html_mod.escape(number)}.</span> {rest}'
        # If the number got caught in diff markup, just render as-is with a wrapper
        return f'<div class="para">{content_html}</div>'
    return f'<div class="para">{content_html}</div>'


def render_paragraph_plain(para: Paragraph) -> str:
    """Render a paragraph as plain HTML (no diff marks)."""
    parts = []
    if para.number:
        parts.append(f'<span class="para-num">{html_mod.escape(para.number)}.</span> {html_mod.escape(para.text)}')
    else:
        parts.append(html_mod.escape(para.text))
    for label, text in para.sub_items:
        parts.append(f'<div class="sub-item"><span class="sub-label">{html_mod.escape(label)})</span> {html_mod.escape(text)}</div>')
    return '<div class="para">' + '<br>'.join(parts) + '</div>'


def render_paragraph_with_marks(para: Paragraph, tag: str) -> str:
    """Render a paragraph entirely wrapped in <del> or <ins>."""
    parts = []
    if para.number:
        parts.append(f'<span class="para-num">{html_mod.escape(para.number)}.</span> <{tag}>{html_mod.escape(para.text)}</{tag}>')
    else:
        parts.append(f'<{tag}>{html_mod.escape(para.text)}</{tag}>')
    for label, text in para.sub_items:
        parts.append(f'<div class="sub-item"><span class="sub-label">{html_mod.escape(label)})</span> <{tag}>{html_mod.escape(text)}</{tag}></div>')
    return '<div class="para">' + '<br>'.join(parts) + '</div>'


# ─── Article diffing ──────────────────────────────────────────────

def diff_articles(old_art: Optional[Article], new_art: Optional[Article]) -> tuple:
    """Diff two articles. Returns (old_html_body, new_html_body)."""
    if old_art is None and new_art is None:
        return ('', '')

    # Entirely new article — render plain, no highlights
    if old_art is None:
        new_parts = [render_paragraph_plain(p) for p in new_art.paragraphs]
        return ('', '\n'.join(new_parts))

    # Entirely removed article — render plain, no highlights
    if new_art is None:
        old_parts = [render_paragraph_plain(p) for p in old_art.paragraphs]
        return ('\n'.join(old_parts), '')

    old_paras = old_art.paragraphs
    new_paras = new_art.paragraphs
    max_len = max(len(old_paras), len(new_paras))

    old_parts = []
    new_parts = []

    for i in range(max_len):
        op = old_paras[i] if i < len(old_paras) else None
        np = new_paras[i] if i < len(new_paras) else None
        oh, nh = diff_paragraph_html(op, np)
        old_parts.append(oh)
        new_parts.append(nh)

    return ('\n'.join(old_parts), '\n'.join(new_parts))


# ─── Preamble diffing ────────────────────────────────────────────

def diff_preamble(old_text: str, new_text: str) -> tuple:
    """Diff preamble texts line-by-line. Returns (old_html, new_html)."""
    old_lines = old_text.split('\n')
    new_lines = new_text.split('\n')

    # Use SequenceMatcher to align lines first
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    old_parts = []
    new_parts = []

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for line in old_lines[i1:i2]:
                escaped = html_mod.escape(line)
                old_parts.append(escaped)
                new_parts.append(escaped)
        elif op == 'delete':
            for line in old_lines[i1:i2]:
                old_parts.append(f'<del>{html_mod.escape(line)}</del>')
        elif op == 'insert':
            for line in new_lines[j1:j2]:
                new_parts.append(f'<ins>{html_mod.escape(line)}</ins>')
        elif op == 'replace':
            # Word-diff each replaced line pair
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                ol = old_lines[i1 + k] if (i1 + k) < i2 else None
                nl = new_lines[j1 + k] if (j1 + k) < j2 else None
                if ol is not None and nl is not None:
                    oh, nh = word_diff(ol, nl)
                    old_parts.append(oh)
                    new_parts.append(nh)
                elif ol is not None:
                    old_parts.append(f'<del>{html_mod.escape(ol)}</del>')
                elif nl is not None:
                    new_parts.append(f'<ins>{html_mod.escape(nl)}</ins>')

    return ('\n'.join(old_parts), '\n'.join(new_parts))


# ─── Article change detection ────────────────────────────────────

def has_changes(old_art: Optional[Article], new_art: Optional[Article]) -> bool:
    """Check if an article pair has any differences."""
    if old_art is None or new_art is None:
        return True
    old_text = '\n'.join(paragraph_to_text(p) for p in old_art.paragraphs)
    new_text = '\n'.join(paragraph_to_text(p) for p in new_art.paragraphs)
    return old_text != new_text


# ─── HTML generation ──────────────────────────────────────────────

def generate_html(old_const: Constitution, new_const: Constitution, summaries: list = None) -> str:
    """Generate the complete HTML page."""
    if summaries is None:
        summaries = []

    # Build navigation and content
    nav_items = []
    content_sections = []
    section_idx = 0

    if summaries:
        summary_articles = []
        summary_cards = []
        for idx, (summary_title, summary_md) in enumerate(summaries, 1):
            anchor = f"summary-{slugify_anchor(summary_title, f'section-{idx}') }"
            summary_articles.append((anchor, summary_title, False))
            summary_html = render_summary_html(summary_md)
            summary_cards.append(f'''
                <article class="summary-source" id="{anchor}">
                    <h3>{html_mod.escape(summary_title)}</h3>
                    <div class="summary-content">
                        {summary_html}
                    </div>
                </article>''')

        nav_items.append(('summary', 'Краткие резюме', summary_articles))
        content_sections.append(f'''
            <section class="diff-section summary-section collapsed" id="summary">
                <div class="summary-header" onclick="toggleSummary(this)">
                    <h2>Краткие резюме изменений</h2>
                    <span class="summary-toggle-icon">▾</span>
                </div>
                <div class="summary-body">
                    {''.join(summary_cards)}
                </div>
            </section>''')

    for mapping in SECTION_MAP:
        old_key, new_key, label, is_new = mapping

        old_section = None
        new_section = None

        if old_key == "preamble":
            # Preamble
            sid = "preamble"
            nav_items.append(('preamble', 'Преамбула', []))

            old_html, new_html = diff_preamble(old_const.preamble, new_const.preamble)

            content_sections.append(f'''
            <section class="diff-section" id="preamble">
                <div class="section-header">
                    <h2>Преамбула</h2>
                </div>
                <div class="diff-columns">
                    <div class="diff-col diff-old" data-label="Конституция 1995">
                        <div class="col-label">Конституция 1995</div>
                        <blockquote>{old_html}</blockquote>
                    </div>
                    <div class="diff-col diff-new" data-label="Конституция 2026">
                        <div class="col-label">Конституция 2026</div>
                        <blockquote>{new_html}</blockquote>
                    </div>
                </div>
            </section>''')
            continue

        if old_key:
            old_section = find_section(old_const, old_key)
        if new_key:
            new_section = find_section(new_const, new_key)

        # Section ID for anchors
        sid = f"section-{new_key or old_key}"

        # Section title
        if is_new:
            section_title_html = f'''
                <h2>
                    <span class="badge badge-new">Новый раздел</span>
                    {html_mod.escape(new_section.full_title)}
                </h2>'''
            nav_label = new_section.full_title
        elif old_section and new_section and old_section.title != new_section.title:
            section_title_html = f'''
                <h2>
                    <span class="title-old">{html_mod.escape(old_section.full_title)}</span>
                    <span class="title-arrow">→</span>
                    <span class="title-new">{html_mod.escape(new_section.full_title)}</span>
                </h2>'''
            nav_label = new_section.full_title
        elif new_section:
            section_title_html = f'<h2>{html_mod.escape(new_section.full_title)}</h2>'
            nav_label = new_section.full_title
        else:
            section_title_html = f'<h2>{html_mod.escape(old_section.full_title)}</h2>'
            nav_label = old_section.full_title

        # Match articles positionally
        old_articles = old_section.articles if old_section else []
        new_articles = new_section.articles if new_section else []
        max_articles = max(len(old_articles), len(new_articles))

        articles_html = []
        nav_article_items = []

        for ai in range(max_articles):
            old_art = old_articles[ai] if ai < len(old_articles) else None
            new_art = new_articles[ai] if ai < len(new_articles) else None

            changed = has_changes(old_art, new_art)

            # Article ID
            art_num = new_art.number if new_art else old_art.number
            art_id = f"{sid}-art-{art_num}"

            # Article header
            if old_art and new_art:
                if old_art.number != new_art.number:
                    art_header = f'Статья {old_art.number} → Статья {new_art.number}'
                else:
                    art_header = f'Статья {old_art.number}'
            elif new_art:
                art_header = f'Статья {new_art.number}'
            else:
                art_header = f'Статья {old_art.number}'

            change_indicator = ''
            if changed:
                if old_art is None:
                    change_indicator = '<span class="badge badge-added">Новая</span>'
                elif new_art is None:
                    change_indicator = '<span class="badge badge-removed">Исключена</span>'
                else:
                    change_indicator = '<span class="change-dot"></span>'

            # Diff the article content
            old_body, new_body = diff_articles(old_art, new_art)

            # Left/right column content
            if is_new and old_art is None:
                old_col = '<div class="placeholder">Отсутствует в Конституции 1995 года</div>'
            elif old_art is None:
                old_col = '<div class="placeholder">Статья отсутствует</div>'
            else:
                old_col = old_body

            if new_art is None:
                new_col = '<div class="placeholder">Статья исключена</div>'
            else:
                new_col = new_body

            nav_article_items.append((art_id, art_header, changed))

            articles_html.append(f'''
                <div class="article-card" id="{art_id}">
                    <div class="article-header" onclick="toggleArticle(this)">
                        <span class="article-title">{html_mod.escape(art_header)}</span>
                        {change_indicator}
                        <span class="collapse-icon">▾</span>
                    </div>
                    <div class="article-body">
                        <div class="diff-columns">
                            <div class="diff-col diff-old" data-label="Конституция 1995">{old_col}</div>
                            <div class="diff-col diff-new" data-label="Конституция 2026">{new_col}</div>
                        </div>
                    </div>
                </div>''')

        nav_items.append((sid, nav_label, nav_article_items))

        badge_html = ''
        if is_new:
            badge_html = '<span class="section-badge-new">новый</span>'

        content_sections.append(f'''
            <section class="diff-section" id="{sid}">
                <div class="section-header">
                    {section_title_html}
                    {badge_html}
                </div>
                {''.join(articles_html)}
            </section>''')

    # Build navigation HTML
    nav_html_parts = []
    for sid, label, articles in nav_items:
        short_label = label
        # Trim long labels
        if len(short_label) > 45:
            short_label = short_label[:42] + '…'

        art_links = ''
        if articles:
            art_items = []
            for art_id, art_label, changed in articles:
                dot = '<span class="nav-change-dot"></span>' if changed else ''
                art_items.append(f'<a href="#{art_id}" class="nav-article">{dot}{html_mod.escape(art_label)}</a>')
            art_links = '<div class="nav-articles">' + ''.join(art_items) + '</div>'

        nav_html_parts.append(f'''
            <div class="nav-section">
                <a href="#{sid}" class="nav-section-link">{html_mod.escape(short_label)}</a>
                {art_links}
            </div>''')

    github_links = [
        ('Репозиторий', GITHUB_REPO_URL),
        ('old.md', f'{GITHUB_REPO_URL}/blob/{GITHUB_BRANCH}/old.md'),
        ('new.md', f'{GITHUB_REPO_URL}/blob/{GITHUB_BRANCH}/new.md'),
        ('summary.md', f'{GITHUB_REPO_URL}/blob/{GITHUB_BRANCH}/summary.md'),
        ('build.py', f'{GITHUB_REPO_URL}/blob/{GITHUB_BRANCH}/build.py'),
    ]

    nav_github_html = ''.join(
        f'<a href="{html_mod.escape(url)}" class="nav-github-link" target="_blank" rel="noopener noreferrer">{html_mod.escape(label)} ↗</a>'
        for label, url in github_links
    )

    header_github_html = ''.join(
        f'<a href="{html_mod.escape(url)}" class="site-github-link" target="_blank" rel="noopener noreferrer">{html_mod.escape(label)} ↗</a>'
        for label, url in github_links
    )

    nav_html = f'''
        <div class="nav-github">
            <div class="nav-github-title">GitHub</div>
            {nav_github_html}
        </div>
    ''' + ''.join(nav_html_parts)
    content_html = ''.join(content_sections)

    # Count stats
    total_old_articles = sum(len(s.articles) for s in old_const.sections)
    total_new_articles = sum(len(s.articles) for s in new_const.sections)

    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- Primary Meta Tags -->
<title>Сравнение Конституций Республики Казахстан 2022 и 2026</title>
<meta name="title" content="Сравнение Конституций Республики Казахстан 2022 и 2026">
<meta name="description" content="Детальное сравнение изменений в Конституции Республики Казахстан. Интерактивный анализ всех поправок, дополнений и изменений между версиями 2022 и 2026 года.">
<meta name="keywords" content="Конституция Казахстана, поправки в конституцию, изменения конституции РК, Конституция 2022, Конституция 2026, сравнение конституций, Kazakhstan constitution">
<meta name="author" content="Maxim Gorbatyuk">
<meta name="language" content="Russian">
<meta name="robots" content="index, follow">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="https://mgorbatyuk.dev/constitution-2026/">
<meta property="og:title" content="Сравнение Конституций Республики Казахстан 2022 и 2026">
<meta property="og:description" content="Детальное сравнение изменений в Конституции Республики Казахстан. Интерактивный анализ всех поправок, дополнений и изменений между версиями 2022 и 2026 года.">
<meta property="og:locale" content="ru_RU">
<meta property="og:site_name" content="Сравнение Конституций РК">

<!-- Twitter -->
<meta property="twitter:card" content="summary">
<meta property="twitter:url" content="https://mgorbatyuk.dev/constitution-2026/">
<meta property="twitter:title" content="Сравнение Конституций Республики Казахстан 2022 и 2026">
<meta property="twitter:description" content="Детальное сравнение изменений в Конституции Республики Казахстан. Интерактивный анализ всех поправок, дополнений и изменений между версиями 2022 и 2026 года.">

<!-- Canonical URL -->
<link rel="canonical" href="https://mgorbatyuk.dev/constitution-2026/">

<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-2EH82M3JKQ"></script>
<script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-2EH82M3JKQ');
</script>

<!-- Preconnect for Performance -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="dns-prefetch" href="https://fonts.googleapis.com">

<!-- Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">

<!-- Structured Data -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Сравнение Конституций Республики Казахстан 2022 и 2026",
  "description": "Детальное сравнение изменений в Конституции Республики Казахстан между версиями 2022 и 2026 года",
  "url": "https://mgorbatyuk.dev/constitution-2026/",
  "inLanguage": "ru",
  "author": {{
    "@type": "Person",
    "name": "Maxim Gorbatyuk",
    "url": "https://github.com/maximgorbatyuk"
  }},
  "publisher": {{
    "@type": "Person",
    "name": "Maxim Gorbatyuk"
  }},
  "mainEntity": {{
    "@type": "Article",
    "headline": "Сравнение Конституций Республики Казахстан",
    "about": "Конституция Республики Казахстан",
    "keywords": "Конституция Казахстана, поправки, изменения, 2022, 2026"
  }}
}}
</script>
<style>
/* ─── Reset & Base ─── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html {{
    scroll-behavior: smooth;
    -webkit-text-size-adjust: 100%;
}}

body {{
    font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
    font-size: 17px;
    line-height: 1.75;
    color: #1A1A1A;
    background: #FAFAF8;
}}

/* ─── UI Font ─── */
.ui-font,
.site-header, .sidebar, .article-header, .col-label,
.badge, .placeholder, .section-badge-new, .legend,
.mobile-toggle, .stats {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}}

/* ─── Layout ─── */
.layout {{
    display: flex;
    min-height: 100vh;
}}

/* ─── Sidebar ─── */
.sidebar {{
    position: sticky;
    top: 0;
    left: 0;
    width: 280px;
    min-width: 280px;
    height: 100vh;
    overflow-y: auto;
    background: #fff;
    border-right: 1px solid #E5E5E0;
    padding: 20px 0;
    font-size: 13px;
    z-index: 100;
    scrollbar-width: thin;
}}

.sidebar-title {{
    font-size: 14px;
    font-weight: 700;
    color: #E8751A;
    padding: 0 20px 16px;
    border-bottom: 1px solid #E5E5E0;
    margin-bottom: 8px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}}

.nav-github {{
    padding: 6px 0 10px;
    margin-bottom: 8px;
    border-bottom: 1px solid #EDEDE8;
}}

.nav-github-title {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #999;
    padding: 0 20px 8px;
}}

.nav-github-link {{
    display: block;
    padding: 5px 20px;
    color: #666;
    text-decoration: none;
    font-size: 12px;
    line-height: 1.4;
}}

.nav-github-link:hover {{
    color: #E8751A;
    background: #FFF8F2;
}}

.nav-section {{
    margin-bottom: 2px;
}}

.nav-section-link {{
    display: block;
    padding: 7px 20px;
    color: #444;
    text-decoration: none;
    font-weight: 500;
    font-size: 13px;
    line-height: 1.4;
    border-left: 3px solid transparent;
    transition: all 0.15s;
}}

.nav-section-link:hover {{
    color: #E8751A;
    background: #FFF8F2;
}}

.nav-section-link.active {{
    color: #E8751A;
    border-left-color: #E8751A;
    background: #FFF8F2;
    font-weight: 600;
}}

.nav-articles {{
    display: none;
    padding: 2px 0 4px;
}}

.nav-section.expanded .nav-articles {{
    display: block;
}}

.nav-article {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 20px 3px 32px;
    color: #777;
    text-decoration: none;
    font-size: 12px;
    line-height: 1.4;
    transition: color 0.15s;
}}

.nav-article:hover {{
    color: #E8751A;
}}

.nav-change-dot {{
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #E8751A;
    flex-shrink: 0;
}}

/* ─── Main Content ─── */
.main-content {{
    flex: 1;
    min-width: 0;
    padding: 0 40px 60px;
    max-width: 1400px;
}}

/* ─── Header ─── */
.site-header {{
    text-align: center;
    padding: 48px 20px 36px;
    border-bottom: 1px solid #E5E5E0;
    margin-bottom: 36px;
}}

.site-header h1 {{
    font-family: 'Inter', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #1A1A1A;
    margin-bottom: 8px;
    letter-spacing: -0.01em;
}}

.site-header .subtitle {{
    font-size: 15px;
    color: #888;
    margin-bottom: 14px;
}}

.site-github-links {{
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 18px;
}}

.site-github-link {{
    color: #666;
    text-decoration: none;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid #E5E5E0;
    background: #fff;
    transition: all 0.15s;
}}

.site-github-link:hover {{
    color: #E8751A;
    border-color: #F1C79D;
    background: #FFF8F2;
}}

.legend {{
    display: flex;
    justify-content: center;
    gap: 28px;
    flex-wrap: wrap;
    font-size: 13px;
    color: #666;
}}

.legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.legend-del {{
    background: #FEF0EE;
    color: #9A1B1B;
    padding: 2px 8px;
    border-radius: 3px;
    text-decoration: line-through;
    font-size: 12px;
}}

.legend-ins {{
    background: #FFF4E6;
    color: #7A4A0A;
    padding: 2px 8px;
    border-radius: 3px;
    border-bottom: 2px solid #E8A84C;
    font-size: 12px;
}}

.stats {{
    font-size: 13px;
    color: #999;
    margin-top: 12px;
}}

/* ─── Summary Block ─── */
.summary-section {{
    background: #fff;
    border: 1px solid #E5E5E0;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 28px;
}}

.summary-header h2 {{
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #1A1A1A;
    margin: 0;
}}

.summary-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    user-select: none;
    padding-bottom: 12px;
    border-bottom: 1px solid #EFEFEA;
}}

.summary-toggle-icon {{
    margin-left: auto;
    color: #bbb;
    font-size: 14px;
    transition: transform 0.2s;
}}

.summary-section.collapsed .summary-toggle-icon {{
    transform: rotate(-90deg);
}}

.summary-body {{
    padding-top: 16px;
}}

.summary-section.collapsed .summary-body {{
    display: none;
}}

.summary-source {{
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #EFEFEA;
}}

.summary-source:first-of-type {{
    margin-top: 2px;
    padding-top: 0;
    border-top: none;
}}

.summary-source h3 {{
    font-family: 'Inter', sans-serif;
    font-size: 17px;
    font-weight: 700;
    color: #1A1A1A;
    margin-bottom: 10px;
}}

.summary-content h4 {{
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 700;
    color: #E8751A;
    margin: 16px 0 8px;
}}

.summary-content p {{
    margin: 0 0 10px;
    color: #333;
}}

.summary-content ul {{
    margin: 0 0 14px 18px;
    padding: 0;
}}

.summary-content ol {{
    margin: 0 0 14px 20px;
    padding: 0;
}}

.summary-content li {{
    margin-bottom: 8px;
    color: #333;
}}

.summary-sep {{
    border: none;
    border-top: 1px solid #E5E5E0;
    margin: 14px 0;
}}

.summary-content code {{
    font-family: 'Inter', sans-serif;
    font-size: 0.92em;
    background: #F5F5F0;
    border-radius: 4px;
    padding: 1px 6px;
}}

/* ─── Sections ─── */
.diff-section {{
    margin-bottom: 48px;
}}

.section-header {{
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid #E8751A;
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
}}

.section-header h2 {{
    font-family: 'Inter', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: #1A1A1A;
    line-height: 1.4;
}}

.title-old {{
    text-decoration: line-through;
    color: #9A1B1B;
    opacity: 0.7;
}}

.title-arrow {{
    color: #E8751A;
    font-weight: 400;
    margin: 0 4px;
}}

.title-new {{
    color: #1A1A1A;
}}

.section-badge-new {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #E8751A;
    background: #FFF4E6;
    padding: 3px 10px;
    border-radius: 10px;
    white-space: nowrap;
}}

/* ─── Article Cards ─── */
.article-card {{
    background: #fff;
    border: 1px solid #E5E5E0;
    border-radius: 8px;
    margin-bottom: 12px;
    overflow: hidden;
    transition: box-shadow 0.2s;
}}

.article-card:hover {{
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}

.article-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 20px;
    cursor: pointer;
    user-select: none;
    background: #FAFAF8;
    border-bottom: 1px solid #E5E5E0;
    transition: background 0.15s;
}}

.article-header:hover {{
    background: #F5F5F0;
}}

.article-title {{
    font-weight: 600;
    font-size: 15px;
    color: #E8751A;
}}

.change-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #E8751A;
    flex-shrink: 0;
}}

.collapse-icon {{
    margin-left: auto;
    color: #bbb;
    font-size: 14px;
    transition: transform 0.2s;
}}

.article-card.collapsed .collapse-icon {{
    transform: rotate(-90deg);
}}

.article-card.collapsed .article-body {{
    display: none;
}}

.article-body {{
    padding: 16px 20px;
}}

/* ─── Diff Columns ─── */
.diff-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
}}

.diff-col {{
    min-width: 0;
}}

.col-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #999;
    margin-bottom: 12px;
}}

/* ─── Paragraphs ─── */
.para {{
    margin-bottom: 20px;
    text-align: justify;
    hyphens: auto;
}}

.para-num {{
    font-weight: 600;
    color: #E8751A;
    font-feature-settings: 'tnum';
}}

.sub-item {{
    margin-left: 24px;
    margin-top: 4px;
}}

.sub-label {{
    font-weight: 600;
    color: #E8751A;
}}

/* ─── Diff Marks ─── */
del {{
    background: #FEF0EE;
    color: #9A1B1B;
    text-decoration: line-through;
    text-decoration-color: #D4A0A0;
    border-radius: 2px;
    padding: 0 1px;
}}

ins {{
    background: #FFF4E6;
    color: #7A4A0A;
    text-decoration: none;
    border-bottom: 2px solid #E8A84C;
    border-radius: 2px;
    padding: 0 1px;
}}

/* ─── Badges ─── */
.badge {{
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.02em;
    white-space: nowrap;
}}

.badge-new {{
    background: #FFF4E6;
    color: #E8751A;
}}

.badge-added {{
    background: #E8F5E9;
    color: #2E7D32;
}}

.badge-removed {{
    background: #FEF0EE;
    color: #9A1B1B;
}}

/* ─── Placeholder ─── */
.placeholder {{
    border: 2px dashed #DDD;
    border-radius: 6px;
    padding: 24px;
    text-align: center;
    color: #AAA;
    font-size: 14px;
    font-style: italic;
}}

/* ─── Preamble ─── */
blockquote {{
    margin: 0;
    padding: 20px 24px;
    background: #FAFAF8;
    border-left: 4px solid #E8751A;
    border-radius: 0 6px 6px 0;
    line-height: 1.9;
    font-style: italic;
    white-space: pre-line;
}}

/* ─── Mobile Toggle ─── */
.mobile-toggle {{
    display: none;
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: #E8751A;
    color: #fff;
    border: none;
    font-size: 20px;
    cursor: pointer;
    z-index: 200;
    box-shadow: 0 3px 12px rgba(232,117,26,0.4);
    align-items: center;
    justify-content: center;
}}

.sidebar-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.4);
    z-index: 99;
}}

/* ─── Responsive ─── */
@media (max-width: 1100px) {{
    .sidebar {{
        position: fixed;
        transform: translateX(-100%);
        transition: transform 0.25s ease;
        box-shadow: 4px 0 20px rgba(0,0,0,0.1);
    }}
    .sidebar.open {{
        transform: translateX(0);
    }}
    .sidebar.open + .sidebar-overlay {{
        display: block;
    }}
    .mobile-toggle {{
        display: flex;
    }}
    .main-content {{
        padding: 0 24px 60px;
    }}
}}

@media (max-width: 900px) {{
    .diff-columns {{
        grid-template-columns: 1fr;
        gap: 16px;
    }}
    .diff-col::before {{
        content: attr(data-label);
        display: block;
        font-family: 'Inter', sans-serif;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #999;
        margin-bottom: 8px;
    }}
    .col-label {{
        display: none;
    }}
    .site-header h1 {{
        font-size: 20px;
    }}
    .main-content {{
        padding: 0 16px 40px;
    }}
    .article-body {{
        padding: 12px 16px;
    }}
}}

/* ─── Scrollbar ─── */
.sidebar::-webkit-scrollbar {{
    width: 4px;
}}
.sidebar::-webkit-scrollbar-thumb {{
    background: #DDD;
    border-radius: 2px;
}}
</style>
</head>
<body>

<div class="layout">
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-title">Содержание</div>
        {nav_html}
    </nav>
    <div class="sidebar-overlay" id="sidebar-overlay" onclick="toggleSidebar()"></div>

    <main class="main-content">
        <header class="site-header">
            <h1>Сравнение Конституций Республики Казахстан</h1>
            <div class="subtitle">Конституция 1995 года — Конституция 2026 года</div>
            <div class="site-github-links">{header_github_html}</div>
            <div class="legend">
                <div class="legend-item"><span class="legend-del">удалено</span> Удалённый текст</div>
                <div class="legend-item"><span class="legend-ins">добавлено</span> Добавленный текст</div>
            </div>
            <div class="stats">{total_old_articles} статей (1995) → {total_new_articles} статей (2026) · {len(old_const.sections)} разделов → {len(new_const.sections)} разделов</div>
        </header>

        {content_html}
    </main>
</div>

<button class="mobile-toggle" id="mobile-toggle" onclick="toggleSidebar()" aria-label="Навигация">☰</button>

<script>
// ─── Sidebar toggle ───
function toggleSidebar() {{
    document.getElementById('sidebar').classList.toggle('open');
}}

document.getElementById('sidebar-overlay').addEventListener('click', function() {{
    document.getElementById('sidebar').classList.remove('open');
}});

// Close sidebar when clicking a nav link on mobile
document.querySelectorAll('.sidebar a').forEach(function(a) {{
    a.addEventListener('click', function() {{
        if (window.innerWidth <= 1100) {{
            document.getElementById('sidebar').classList.remove('open');
        }}
    }});
}});

// ─── Collapse/expand articles ───
function toggleArticle(header) {{
    header.closest('.article-card').classList.toggle('collapsed');
}}

function toggleSummary(header) {{
    header.closest('.summary-section').classList.toggle('collapsed');
}}

function expandSummaryForAnchor() {{
    var hash = window.location.hash;
    if (!hash || hash.length < 2) return;

    var targetId = decodeURIComponent(hash.slice(1));
    var target = document.getElementById(targetId);
    var summary = document.getElementById('summary');

    if (target && summary && summary.contains(target)) {{
        summary.classList.remove('collapsed');
    }}
}}

expandSummaryForAnchor();
window.addEventListener('hashchange', expandSummaryForAnchor);

// ─── Scroll spy ───
(function() {{
    var sections = document.querySelectorAll('.diff-section');
    var navLinks = document.querySelectorAll('.nav-section-link');
    var navSections = document.querySelectorAll('.nav-section');

    var observer = new IntersectionObserver(function(entries) {{
        entries.forEach(function(entry) {{
            if (entry.isIntersecting) {{
                var id = entry.target.id;
                navLinks.forEach(function(link) {{
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {{
                        link.classList.add('active');
                        link.closest('.nav-section').classList.add('expanded');
                    }}
                }});
                // Collapse other sections
                navSections.forEach(function(ns) {{
                    var link = ns.querySelector('.nav-section-link');
                    if (link && link.getAttribute('href') !== '#' + id) {{
                        ns.classList.remove('expanded');
                    }}
                }});
            }}
        }});
    }}, {{
        rootMargin: '-10% 0px -80% 0px',
        threshold: 0
    }});

    sections.forEach(function(s) {{
        observer.observe(s);
    }});
}})();
</script>
</body>
</html>'''


# ─── Main ─────────────────────────────────────────────────────────

def main():
    with open('old.md', 'r', encoding='utf-8') as f:
        old_text = f.read()
    with open('new.md', 'r', encoding='utf-8') as f:
        new_text = f.read()

    summaries = []
    try:
        with open('summary.md', 'r', encoding='utf-8') as f:
            summaries = extract_summary_sections(f.read())
        if summaries:
            print(f"Loaded summaries: {len(summaries)} section(s)")
        else:
            print("summary.md found, but no level-2 summary sections were detected")
    except FileNotFoundError:
        print("summary.md not found; building without summary blocks")

    print("Parsing constitutions...")
    old_const = parse_constitution(old_text)
    new_const = parse_constitution(new_text)

    print(f"  Old: {len(old_const.sections)} sections, "
          f"{sum(len(s.articles) for s in old_const.sections)} articles")
    print(f"  New: {len(new_const.sections)} sections, "
          f"{sum(len(s.articles) for s in new_const.sections)} articles")

    print("Generating diff HTML...")
    html = generate_html(old_const, new_const, summaries)

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = len(html.encode('utf-8')) / 1024
    print(f"Generated index.html ({size_kb:.0f} KB)")
    print("Done!")


if __name__ == '__main__':
    main()
