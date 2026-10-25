import re

TOKEN = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN.findall(text)]
