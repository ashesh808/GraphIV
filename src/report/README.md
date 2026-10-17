# report

The document a researcher reads.
Every claim in it can be checked against a paper, and a caller can bring its own prose instead of ours.

```
fulltext.py  reads a paper's sections and result tables out of its html
table.py     the method table, one row per method, with columns the question decides
compose.py   writes an outline over the evidence, then one section per point
ground.py    the citation check every draft passes before it leaves
render.py    puts the document together
```

## The Written Part

A report is a review, not a list.
We build a digest of the papers, their lineages, the disputes and the method table, ask the model for an outline over it, then write one section per point.
Each section is told which papers it has to discuss and sees the whole digest, since one call stops at about a thousand words however much it is given.
When the caller passes its own prose, nothing here writes.

## The Method Table

Each column is `choice`, `value` or `text`, and only a `choice` column groups.
Reading a choice column top to bottom answers the question, crossing two of them maps the field, and an empty cell in that cross is a combination nobody has published.

The model designs the columns from the abstracts and fills them from each paper's method and results sections.
A column whose options missed most of the field is widened once, from what the papers said, rather than extracted again.

## The Citation Check

`ground.check` runs on every draft, including one the caller wrote.

| What it finds | What it does |
| --- | --- |
| an id the caller was given | keeps it |
| an id within two edits of one it was given | corrects it in place |
| an id the corpus holds but the caller was not given | keeps it and flags it |
| an id no paper carries | cuts the mention out of the sentence |

So every arXiv id in a finished document exists, by construction rather than by the model behaving.
