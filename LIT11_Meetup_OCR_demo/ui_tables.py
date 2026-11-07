"""Escaped static tables with predictable wrapping for long extracted text."""
from html import escape

TABLE_CSS = """
.poster-table-wrap {width:100%;max-width:100%;margin:12px 0 20px;}
.poster-table {width:100%;max-width:100%;table-layout:fixed;border-collapse:collapse;font-size:1rem;}
.poster-table th,.poster-table td {
  text-align:left!important;vertical-align:top;padding:12px;
  border:1px solid #cbd5e1;white-space:pre-wrap!important;
  overflow-wrap:anywhere!important;word-break:normal;
  text-overflow:clip!important;overflow:visible!important;line-height:1.65;
}
.poster-table th {background:#f1f5f9;color:#0f172a;font-weight:600;}
.poster-table td {background:#fff;color:#0f172a;}
@media(max-width:640px){
  .poster-table {font-size:0.9rem;}
  .poster-table th,.poster-table td {padding:8px 6px;}
}
"""

def table_html(rows):
    if not rows:
        return ""
    columns = list(dict.fromkeys(key for row in rows for key in row))
    widths = {2: [26, 74], 3: [16, 42, 42], 4: [16, 34, 34, 16]}.get(len(columns))
    colgroup = "<colgroup>" + "".join(
        f'<col style="width:{width}%">' for width in widths
    ) + "</colgroup>" if widths else ""
    headers = "".join(f'<th scope="col">{escape(str(key))}</th>' for key in columns)
    body = "".join("<tr>" + "".join(
        f"<td>{escape(str(row.get(key, '') if row.get(key) is not None else ''))}</td>"
        for key in columns
    ) + "</tr>" for row in rows)
    return f'<div class="poster-table-wrap"><table class="poster-table">{colgroup}<thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table></div>'
