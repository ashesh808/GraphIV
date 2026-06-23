"""Emit the flagship deep-research report as a review-structured LaTeX document.

A pragmatic Markdown->LaTeX converter (headings, emphasis, lists, arXiv ids) wrapped in an
article preamble with a title, auto abstract, the narrated body, and a References section
built from the landmark set. Aim: a file that compiles to a paper-looking PDF — not a
full CommonMark implementation.
"""

from __future__ import annotations

import re

_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITAL = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_ARXIV = re.compile(r"arXiv:\s?([a-zA-Z][a-zA-Z.\-]+/\d{7}|\d{4}\.\d{4,5}|\d{7})")
_IMG = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")


def _esc(text: str) -> str:
    out: list[str] = []
    for ch in text:
        out.append(_SPECIALS.get(ch, ch))
    return "".join(out)


def _inline(text: str) -> str:
    """Escape specials, then re-apply emphasis + monospace arXiv ids on the escaped text."""
    s = _esc(text)
    s = _BOLD.sub(lambda m: r"\textbf{" + m.group(1) + "}", s)
    s = _ITAL.sub(lambda m: r"\textit{" + m.group(1) + "}", s)
    s = _ARXIV.sub(lambda m: r"\texttt{arXiv:" + m.group(1) + "}", s)
    return s


def _md_to_tex(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(r"\end{itemize}")
            in_list = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            out.append("")
            continue
        img = _IMG.match(line)
        if img:
            close_list()
            out.append(
                r"\begin{center}\includegraphics[width=0.75\textwidth,"
                r"height=0.4\textheight,keepaspectratio]{"
                + img.group(1)
                + "}\\end{center}"
            )
        elif line.startswith("#### "):
            close_list()
            out.append(r"\subsubsection*{" + _inline(line[5:]) + "}")
        elif line.startswith("### "):
            close_list()
            out.append(r"\subsubsection{" + _inline(line[4:]) + "}")
        elif line.startswith("## "):
            close_list()
            out.append(r"\subsection{" + _inline(line[3:]) + "}")
        elif line.startswith("# "):
            close_list()
            out.append(r"\section{" + _inline(line[2:]) + "}")
        elif line.lstrip().startswith(("- ", "* ")):
            if not in_list:
                out.append(r"\begin{itemize}")
                in_list = True
            item = line.lstrip()[2:]
            out.append(r"  \item " + _inline(item))
        else:
            close_list()
            out.append(_inline(line))
    close_list()
    return "\n".join(out)


def _year_key(lm: dict[str, object]) -> int:
    y = lm.get("year")
    return y if isinstance(y, int) else 0


def _references(landmarks: list[dict[str, object]]) -> str:
    """A plain enumerated reference list from the landmark metadata (year-ordered)."""
    rows = sorted(landmarks, key=_year_key)
    out: list[str] = [r"\section*{References}", r"\begin{enumerate}\small"]
    for lm in rows:
        aid = str(lm.get("arxiv_id", ""))
        title = _esc(str(lm.get("title", "")))
        year = lm.get("year")
        yr = f" ({year})" if year else ""
        out.append(rf"  \item {title}{yr}. \texttt{{arXiv:{aid}}}")
    out.append(r"\end{enumerate}")
    return "\n".join(out)


def to_tex(
    question: str,
    report_md: str,
    landmarks: list[dict[str, object]],
    abstract: str,
) -> str:
    """Wrap the narrated markdown report into a compilable review-structured LaTeX doc."""
    preamble = (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{hyperref}\n"
        "\\usepackage{enumitem}\n"
        "\\setlength{\\parskip}{0.5em}\n"
        "\\setlength{\\parindent}{0pt}\n"
    )
    title = _esc(question)
    body = _md_to_tex(report_md)
    abs_tex = (
        _inline(abstract)
        if abstract
        else "A grounded, chronological literature review."
    )
    return (
        f"{preamble}\n"
        f"\\title{{{title}}}\n"
        "\\author{arXiv GraphRAG --- phase-6 deep research}\n"
        "\\date{\\today}\n\n"
        "\\begin{document}\n"
        "\\maketitle\n\n"
        f"\\begin{{abstract}}\n{abs_tex}\n\\end{{abstract}}\n\n"
        f"{body}\n\n"
        f"{_references(landmarks)}\n\n"
        "\\end{document}\n"
    )
