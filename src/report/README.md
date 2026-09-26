# report

The document a researcher reads. Every section is evidence that can be checked against a paper,
and the prose belongs to whoever called this.

```
fulltext.py  sections and result tables out of the html on disk
table.py     a table whose rows are methods, with columns the question decides
compose.py   an outline over the evidence, then one model call per section
ground.py    the guard every draft passes through before it leaves
render.py    the document
```

## The written half

A report is a review and not a list. `compose.py` builds a digest, a node table plus the lineages,
the papers the field argues with, the disputes and the method table, then asks for an outline over
it and writes one section per point. A section is told which papers it has to discuss and is given
the whole digest to write from, since one call self-limits to about a thousand words however much
it is given. The caller can pass its own prose instead, and then nothing here writes anything.

## The method table

A column is `choice`, `value` or `text`, and only a `choice` column with options groups. That is
the point of the table: reading one closed column top to bottom answers what was asked, the cross
product of two of them is a map of the field, and an empty cell in that cross product is a
combination nobody has published.

The model designs the columns from the abstracts, fills them from each paper's own method and
results sections, and a column whose options missed most of the field is widened once from what
the papers actually said rather than by extracting again.

## The guard

`ground.check` runs on every draft, including one the caller wrote and handed back.

| what it finds | what it does |
| --- | --- |
| an id the caller was given | keeps it |
| an id within two edits of one it was given | corrects it where it stands |
| an id the corpus holds but the caller was not given | keeps it and says so |
| an id no paper carries | cuts the mention out of the sentence |

So every arXiv id in a finished document exists, by construction rather than by the model's good
behavior.
