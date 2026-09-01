# File: cli/sessions/book.py
"""Console tab for browsing the FORMS Book (docs/book/).

Pages through the authored manual like a book: open a chapter, open a page,
turn pages with ``--next`` / ``--prev``, and toggle the machine-readable
``--ai`` view. The same :class:`forms.core.book.Book` engine backs the GUI
reader; every page result also carries a structured ``data`` payload so the
Zenith bridge can render it richly without re-parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.text import Text

import formslab.bridge as bridge
import formslab.console.style as style
from formslab.console.sessions.base import CLIResult, ConsoleSession

# No root constant. `Book()` defaults to the bundled `forms/resources/book`,
# resolved from the library's install location -- which is the only thing that
# can be right once the console no longer lives inside the FORMS checkout. The
# path this used to compute (`python/docs/book`) had already stopped existing.


class BookSession(ConsoleSession):
    """Navigable reader over the FORMS Book."""

    def __init__(self):
        # No external handler: this session routes its own commands.
        super().__init__("book", lambda parts: CLIResult(content=""))
        self._book = bridge.book().Book()
        self._current: Optional[str] = None  # doc_id of the open page
        self._ai_view = False

    # -- chrome ------------------------------------------------------

    def help(self):
        return self._toc_result()

    def banner(self):
        return Text("BOOK tab ready. --toc lists pages; open one by doc_id.", style=style.TEXT)

    def prompt(self):
        from formslab.console.style import ACCENT1, PROMPT_SUFFIX

        crumb = f" {self._current}" if self._current else ""
        return f"[bold {ACCENT1.color}]book{crumb}{PROMPT_SUFFIX} [/] "

    # -- routing -----------------------------------------------------

    def handle(self, raw: str, payload: Optional[dict] = None) -> CLIResult:
        parts = raw.strip().split()
        if not parts:
            return self._toc_result()

        cmd = parts[0].lower()
        if cmd in ("--toc", "toc", "--index", "index"):
            return self._toc_result()
        if cmd in ("--ai", "ai"):
            target = parts[1] if len(parts) > 1 else self._current
            return self._page_result(target, ai=True) if target else self._toc_result()
        if cmd in ("--next", "next"):
            return self._step(+1)
        if cmd in ("--prev", "prev", "--back", "back"):
            return self._step(-1)
        if cmd in ("--search", "search"):
            return self._search_result(" ".join(parts[1:]))
        if cmd in ("--glossary", "glossary"):
            return self._glossary_result()
        if cmd in ("--source", "source"):
            target = parts[1] if len(parts) > 1 else None
            return self._source_result(target) if target else self._toc_result()

        # Otherwise treat the token as a chapter id or a page locator.
        token = parts[0]
        if self._is_chapter(token):
            return self._chapter_result(token)
        return self._open(token)

    # -- actions -----------------------------------------------------

    def _open(self, token: str) -> CLIResult:
        doc_id = self._resolve(token)
        if doc_id is None:
            return self._search_result(token)
        return self._page_result(doc_id, ai=False)

    def _step(self, delta: int) -> CLIResult:
        if not self._current:
            return self._toc_result()
        nav = self._book.navigation(self._current)
        target = nav["next"] if delta > 0 else nav["prev"]
        if not target:
            edge = "last" if delta > 0 else "first"
            return CLIResult(content=Text(f"At the {edge} page of the chapter.", style=style.DIM))
        return self._page_result(target["doc_id"], ai=self._ai_view)

    # -- rendering ---------------------------------------------------

    def _page_result(self, doc_id: str, *, ai: bool) -> CLIResult:
        page = self._book.page(doc_id)
        if page is None:
            return self._search_result(doc_id)

        self._current = page.doc_id
        self._ai_view = ai
        markdown = self._book.render_human(page.doc_id)
        ai_text = self._book.render_ai(page.doc_id)
        nav = self._book.navigation(page.doc_id)
        shown = ai_text if ai else markdown

        try:
            from rich.markdown import Markdown

            body = Markdown(shown or "_(empty)_")
        except Exception:
            body = Text(shown)

        footer = self._nav_footer(nav, ai)
        from rich.console import Group

        content = Group(body, Text(""), footer)
        data = {
            "kind": "book_page",
            "doc_id": page.doc_id,
            "title": page.title,
            "chapter": page.chapter,
            "topic": page.topic,
            "layer": page.layer,
            "task": page.task,
            "symbols": page.frontmatter.get("symbols", []) or [],
            "markdown": markdown,
            "ai": ai_text,
            "view": "ai" if ai else "human",
            "nav": nav,
        }
        return CLIResult(content=content, data=data)

    def _toc_result(self) -> CLIResult:
        toc = self._book.toc()
        lines = Text()
        lines.append(f"{toc['title']}\n", style=style.HEADER)
        any_pages = False
        for part in toc["parts"]:
            if part.get("title"):
                lines.append(f"\n{part['title']}\n", style=style.HEADER)
            for chapter in part["chapters"]:
                pages = chapter["pages"]
                if not pages:
                    continue
                any_pages = True
                lines.append(f"\n  {chapter['title']}\n", style=style.ACCENT1)
                for stub in pages:
                    lines.append(f"    {stub['doc_id']}", style=style.VALUE)
                    if stub.get("summary"):
                        lines.append(f"  {stub['summary']}", style=style.DIM)
                    lines.append("\n")
        if not any_pages:
            lines.append("\n  (no pages found)\n", style=style.DIM)
        for warning in toc.get("warnings", []):
            lines.append(f"! {warning}\n", style=style.WARNING)
        return CLIResult(content=lines, data={"kind": "book_toc", "toc": toc})

    def _chapter_result(self, chapter_id: str) -> CLIResult:
        toc = self._book.toc()
        chapter = next(
            (c for part in toc["parts"] for c in part["chapters"] if c["id"] == chapter_id),
            None,
        )
        if chapter is None:
            return self._toc_result()
        lines = Text()
        lines.append(f"{chapter['title']}\n", style=style.HEADER)
        for stub in chapter["pages"]:
            lines.append(f"  {stub['doc_id']}", style=style.VALUE)
            if stub.get("summary"):
                lines.append(f"  {stub['summary']}", style=style.DIM)
            lines.append("\n")
        return CLIResult(content=lines, data={"kind": "book_chapter", "chapter": chapter})

    def _search_result(self, query: str) -> CLIResult:
        payload = self._book.search(query)
        matches = payload["matches"]
        lines = Text()
        if not matches:
            lines.append(f"No Book pages match '{query}'.", style=style.DIM)
            return CLIResult(content=lines, data={"kind": "book_search", "result": payload})
        lines.append(f"Book pages matching '{query}':\n", style=style.HEADER)
        for stub in matches:
            lines.append(f"  {stub['doc_id']}", style=style.VALUE)
            if stub.get("summary"):
                lines.append(f"  {stub['summary']}", style=style.DIM)
            lines.append("\n")
        return CLIResult(content=lines, data={"kind": "book_search", "result": payload})

    def _glossary_result(self) -> CLIResult:
        glossary = self._book.glossary_index()
        lines = Text()
        lines.append(f"Glossary ({len(glossary)} terms)\n", style=style.HEADER)
        for term in sorted(glossary):
            entry = glossary[term]
            lines.append(f"  {term}", style=style.VALUE)
            uses = len(entry.get("pages", []))
            if uses:
                lines.append(f"  ({uses})", style=style.INFO)
            lines.append(f"  {entry['definition']}\n", style=style.DIM)
        return CLIResult(content=lines, data={"kind": "book_glossary", "glossary": glossary})

    def _source_result(self, symbol: str) -> CLIResult:
        find_symbols = bridge.catalog().find_symbols

        raw = find_symbols(symbol, limit=25).get("matches", []) or []
        match = next((m for m in raw if m.get("symbol") == symbol), None)
        if match is None:
            match = next((m for m in raw if symbol in str(m.get("symbol", ""))), None)
        if match is None:
            return CLIResult(
                content=Text(f"No symbol '{symbol}' in the API catalog.", style=style.DIM),
                data={"kind": "book_source", "found": False, "symbol": symbol},
            )

        file_rel = str(match.get("file") or "")
        line = match.get("line")
        source, end_line = self._read_source(file_rel, line)
        data = {
            "kind": "book_source",
            "found": True,
            "symbol": match.get("symbol"),
            "signature": match.get("signature"),
            "summary": match.get("summary"),
            "doc_id": match.get("doc_id"),
            "file": file_rel,
            "line": line,
            "end_line": end_line,
            "source": source,
        }
        text = Text()
        text.append(f"{match.get('symbol')}\n", style=style.VALUE)
        if match.get("signature"):
            text.append(f"{match['signature']}\n", style=style.DIM)
        text.append(f"{file_rel}:{line}\n\n", style=style.INFO)
        text.append(source or "(source unavailable)", style=style.TEXT)
        return CLIResult(content=text, data=data)

    @staticmethod
    def _read_source(file_rel: str, line: Optional[int]):
        """Read a symbol's exact source span via the file's own AST.

        Uses ``end_lineno`` of the def/class node at ``line`` -- no catalog
        change needed. Falls back to a fixed window if the node isn't found.
        """
        import ast

        if not file_rel or not line:
            return "", None
        path = _BOOK_ROOT.parents[1] / file_rel  # python/ workspace root
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return "", None
        rows = text.splitlines()
        end = None
        try:
            for node in ast.walk(ast.parse(text)):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ) and getattr(node, "lineno", None) == line:
                    end = getattr(node, "end_lineno", None)
                    break
        except Exception:
            pass
        start = max(0, int(line) - 1)
        stop = end if end else min(len(rows), start + 40)
        return "\n".join(rows[start:stop]), end

    def _nav_footer(self, nav: dict, ai: bool) -> Text:
        footer = Text()
        view = "AI view" if ai else "reading view"
        footer.append(f"[{view}]  ", style=style.INFO)
        if nav.get("prev"):
            footer.append(f"<- --prev {nav['prev']['doc_id']}   ", style=style.DIM)
        if nav.get("next"):
            footer.append(f"--next {nav['next']['doc_id']} ->", style=style.DIM)
        if not ai:
            footer.append("    (--ai for machine view)", style=style.DIM)
        return footer

    # -- resolution --------------------------------------------------

    def _is_chapter(self, token: str) -> bool:
        toc = self._book.toc()
        return any(
            c["id"] == token for part in toc["parts"] for c in part["chapters"]
        )

    def _resolve(self, token: str) -> Optional[str]:
        """Map a user token to a doc_id: exact, then by trailing path segment."""
        norm = token.strip().strip("/").replace("\\", "/")
        if self._book.page(norm) is not None:
            return norm
        # Match by last path segment (e.g. "sgp4" -> "models/sgp4" or "sgp4.x").
        for stub in self._all_stubs():
            doc_id = stub["doc_id"]
            tail = doc_id.split("/")[-1]
            if tail == norm or tail.split(".")[0] == norm or doc_id.endswith("/" + norm):
                return doc_id
        return None

    def _all_stubs(self):
        toc = self._book.toc()
        for part in toc["parts"]:
            for chapter in part["chapters"]:
                for stub in chapter["pages"]:
                    yield stub
