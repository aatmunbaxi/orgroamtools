from enum import Enum
import re
import orgparse as op

ORG_LATEX_RX = (
    r"\\\((.*?)\\\)|"  #  \(\)
    r"\\\[\n(.*?)\n\\\]|"  # \[...\]
    r"\\begin{\b(?:equation|align|equation\*|align\*|muliline\*|muliline)\b}\n(.*?)\\end{\b(?:equation|align|equation\*|align|muliline\*|muliline\*)\b}|"  # equation environment
    r"#\+begin_equation\n(.*?)#\+end_equation|"  # Org-mode equation block
    r"#\+begin_latex\n(.*?)#\+end_latex"  # Org-mode latex block
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


def get_file_body_text(fname: str) -> str:
    """Return full body text of file

    Parameters
    ----------
    fname : ``str``
        Filename

    Returns
    -------
    ``str``
        Body text of file
    """
    body = ""
    root = op.load(fname)
    for node in root:
        body += node.get_body()
    return body


def extract_math_snippets(fname: str) -> list[str]:
    return [
        s
        for tup in re.findall(ORG_LATEX_RX, get_file_body_text(fname), re.DOTALL)
        for s in tup
        if s
    ]
