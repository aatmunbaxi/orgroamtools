from enum import Enum
from typing import Tuple
import re
import orgparse as op

ORG_LATEX_RX = (
    r"\\\((.*?)\\\)|"  #  \(\)
    r"\\\[\n(.*?)\n\\\]|"  # \[...\]
    r"\\begin{\b(?:equation|align|equation\*|align\*|muliline\*|muliline)\b}\n(.*?)\\end{\b(?:equation|align|equation\*|align|muliline\*|muliline\*)\b}|"  # equation environment
    r"#\+begin_equation\n(.*?)#\+end_equation|"  # Org-mode equation block
    r"#\+begin_latex\n(.*?)#\+end_latex"  # Org-mode latex block
)

SRC_BLOCK_RE = re.compile(
    r"^\s*#\+BEGIN_SRC\s+([a-zA-Z0-9_-]+)(?:.*?)\n(.*?)#\+END_SRC\s*",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


class IdentifierType(Enum):
    """
    Nodes in an org-roam graph can identified uniquely by their ID, and non-uniquely
    by their title. This enum disambiguates the the type of an identifier
    for functions that take a generic identifier in as an input.
    e.g. ``RoamGraph.node(identifier)``

    Attributes
    ----------
    TITLE : 1
        Indicates identifier is a title
    ID : 2
        Indicates identifier is an ID
    NOTHING : 0
        Indicates identifier is neither a title nor an ID
    """

    TITLE = 1
    ID = 2
    NOTHING = 0


class DuplicateTitlesWarning(Warning):
    """
    Warns there are multiple nodes with the same title in the graph.

    In the case there are multiple nodes with the same title, identifying
    nodes by their title will not be a unique way of picking them out.
    The resulting behavior may not be what the user wants.

    Attributes
    ----------
    message : str
        Human readable string describing warning
    """

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


def extract_math_snippets(text: str) -> list[str]:
    """Return math snippets in text

    Parameters
    ----------
    text : ``str``
        Text to extract math snippets from

    Returns
    -------
    ``list[str]``
        List of math snippets
    """
    return [
        group
        for match in re.findall(ORG_LATEX_RX, text, re.DOTALL)
        for group in match
        if group
    ]


def extract_src_blocks(text: str) -> list[Tuple[str, str]]:
    """Return org source blocks

    Parameters
    ----------
    text : ``str``
        Text to extract source blocks from

    Returns
    -------
    ``list[Tule[str,str]]``
        List of source block environments in the form (LANGUAGE, SRC_BLOCK_BODY)
    """
    return [(match[0], match[1].strip()) for match in SRC_BLOCK_RE.findall(text)]
