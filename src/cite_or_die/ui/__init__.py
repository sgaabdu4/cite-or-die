from functools import cache
from importlib.resources import files
from string import Template


@cache
def workspace_page() -> str:
    ui = files(__name__)
    components = (
        "workspace_controls",
        "workspace_dialog",
        "provider_dialog",
        "source_panel",
        "question_composer",
        "citation_viewer",
    )
    markup = {
        name: ui.joinpath("library", f"{name}.html").read_text(encoding="utf-8").rstrip("\n")
        for name in components
    }
    return Template(ui.joinpath("index.html").read_text(encoding="utf-8")).substitute(markup)
