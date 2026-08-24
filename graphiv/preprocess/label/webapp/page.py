"""
The one page the labeling app serves: PDF on the left, the citation and both papers on the right

Assembled from the same shell idiom as the dashboard, minus anything that assumes a phone
"""

from __future__ import annotations

from .script import _APP_JS
from .theme import _CSS, _FONTS

_BODY: str = """
<nav class="navbar">
 <span class="brand"><b>GraphIV</b><span>Citation Labeling</span></span>
 <span class="right">
  <span class="counts"><b id="n-done">0</b> / <span id="n-total">0</span> labeled</span>
  <button class="pill sm" id="hint-btn">hint</button>
  <button class="pill sm" id="mode">theme</button>
 </span>
</nav>
<div id="bar"><div id="barfill" style="width:0"></div></div>
<div class="split" id="split">
 <div class="pane pdf">
  <div class="pdfhead">
   <button class="pill sm" onclick="showPage(page-1)">&larr;</button>
   <span>page <span id="pageno">-</span> &middot; <kbd>h</kbd> jumps back to the citation</span>
   <button class="pill sm" onclick="showPage(page+1)">&rarr;</button>
  </div>
  <img id="page" alt="page">
 </div>
 <div class="pane">
  <div class="card">
   <h3>The citation</h3>
   <div class="sentence" id="sentence"></div>
   <div class="meta">section <b id="section"></b> &middot; occurrence <b id="ordinal"></b></div>
  </div>
  <div class="card">
   <h3>Citing paper</h3>
   <div class="ptitle" id="citing-title"></div>
   <div class="authors" id="citing-authors"></div>
   <div class="meta"><a id="citing-id" target="_blank"></a> &middot;
    <span id="citing-facts"></span></div>
   <div class="abs" id="citing-abs"></div>
  </div>
  <div class="card">
   <h3>Cited paper</h3>
   <div class="ptitle" id="cited-title"></div>
   <div class="authors" id="cited-authors"></div>
   <div class="meta"><a id="cited-id" target="_blank"></a> &middot;
    <span id="cited-facts"></span></div>
  </div>
  <div class="axes">
   <div id="axes"></div>
   <div id="guess"></div>
   <div class="hint"><kbd>1</kbd>-<kbd>6</kbd> intent &middot; <kbd>u</kbd> undo &middot;
    <kbd>x</kbd> skip &middot; <kbd>t</kbd> hint &middot;
    <kbd>&larr;</kbd><kbd>&rarr;</kbd> pages</div>
  </div>
 </div>
</div>
<div id="fin" style="display:none">nothing left to label</div>
"""


def html() -> str:
    """
    The whole single-page app
    """
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        "<title>GraphIV citation labeling</title>"
        f"{_FONTS}<style>{_CSS}</style></head><body>"
        f"{_BODY}<script>{_APP_JS}</script></body></html>"
    )
