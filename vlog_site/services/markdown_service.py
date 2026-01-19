from markupsafe import Markup, escape
import markdown


def render_markdown(md_text: str) -> Markup:
    safe_source = str(escape(md_text))
    html = markdown.markdown(safe_source, extensions=["fenced_code", "tables"])
    return Markup(html)
