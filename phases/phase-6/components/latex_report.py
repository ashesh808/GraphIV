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


def _bib_title(title: str) -> str:
    return title.replace("\\", "").replace("{", "").replace("}", "").strip()


def _bib_authors(raw: str) -> str:
    """Kaggle comma-separated author string -> bibtex 'A and B and C'."""
    parts = [
        p.strip() for p in re.split(r",\s*|\s+and\s+", _bib_title(raw)) if p.strip()
    ]
    return " and ".join(parts)


def refs_bib(landmarks: list[dict[str, object]]) -> str:
    """A refs.bib of @misc arXiv entries keyed by arxiv id, from the landmark metadata.

    An unresolvable key is a compile error (a second grounding tripwire)."""
    out: list[str] = []
    for lm in sorted(landmarks, key=_year_key):
        aid = str(lm.get("arxiv_id", ""))
        if not aid:
            continue
        year = lm.get("year")
        authors = lm.get("authors")
        fields = [
            f"  title = {{{{{_bib_title(str(lm.get('title', '')))}}}}}",
            (
                f"  author = {{{_bib_authors(str(authors))}}}"
                if isinstance(authors, str) and authors.strip()
                else ""
            ),
            f"  year = {{{year}}}" if isinstance(year, int) else "",
            f"  eprint = {{{aid}}}",
            "  archivePrefix = {arXiv}",
            f"  howpublished = {{\\url{{https://arxiv.org/abs/{aid}}}}}",
        ]
        out.append(f"@misc{{{aid},\n" + ",\n".join(f for f in fields if f) + ",\n}")
    return "\n\n".join(out) + "\n"


def _cite_pass(body: str, landmarks: list[dict[str, object]]) -> str:
    """Rewrite `\\texttt{arXiv:<id>}` -> `\\citep{<id>}` for ids in the landmark set."""
    known = {
        str(lm.get("arxiv_id", "")).lower(): str(lm.get("arxiv_id", ""))
        for lm in landmarks
    }
    pat = re.compile(r"\\texttt\{arXiv:([^}]+)\}")
    return pat.sub(
        lambda m: (
            rf"\citep{{{known[m.group(1).lower()]}}}"
            if m.group(1).lower() in known
            else m.group(0)
        ),
        body,
    )


def to_tex(
    question: str,
    report_md: str,
    landmarks: list[dict[str, object]],
    abstract: str,
) -> tuple[str, str]:
    """Wrap the narrated markdown into a compilable LaTeX doc -> (report.tex, refs.bib).

    Landmark ids become real `\\citep` citations against the generated bibliography;
    non-landmark ids stay as monospace text."""
    preamble = (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage[numbers]{natbib}\n"
        "\\usepackage{hyperref}\n"
        "\\setlength{\\parskip}{0.5em}\n"
        "\\setlength{\\parindent}{0pt}\n"
    )
    title = _esc(question)
    body = _cite_pass(_md_to_tex(report_md), landmarks)
    abs_tex = (
        _inline(abstract)
        if abstract
        else "A grounded, chronological literature review."
    )
    tex = (
        f"{preamble}\n"
        f"\\title{{{title}}}\n"
        "\\author{GraphIV --- deep research}\n"
        "\\date{\\today}\n\n"
        "\\begin{document}\n"
        "\\maketitle\n\n"
        f"\\begin{{abstract}}\n{abs_tex}\n\\end{{abstract}}\n\n"
        f"{body}\n\n"
        "\\bibliographystyle{unsrtnat}\n"
        "\\bibliography{refs}\n\n"
        "\\end{document}\n"
    )
    return tex, refs_bib(landmarks)
