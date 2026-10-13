import re
from enum import Enum

MATH_ENVIRONMENTS = (
    "equation",
    "align",
    "gather",
    "multline",
    "flalign",
    "eqnarray",
    "math",
    "displaymath",
)

# Alternatives are tried in order; the first matching named group is the snippet.
ORG_LATEX_RE = re.compile(
    r"""
      (?i:\#\+begin_equation)[^\n]*\n (?P<equation_block>.*?) (?i:\#\+end_equation)
    | (?i:\#\+begin_latex)[^\n]*\n (?P<latex_block>.*?) (?i:\#\+end_latex)
    | \\begin\{(?P<env>(?:"""
    + "|".join(MATH_ENVIRONMENTS)
    + r""")\*?)\} (?P<environment>.*?) \\end\{(?P=env)\}
    | (?<!\\)\$\$ (?P<display_dollars>.+?) \$\$
    | (?<!\\)\\\[ (?P<display>.+?) \\\]
    | (?<!\\)\\\( (?P<inline>.+?) \\\)
    # Org's rule for single $: no space just inside either $, at most two
    # line breaks, and the closing $ followed by space, punctuation or the end
    | (?<![\\$])\$
      (?P<dollars>[^\s,;.$](?:[^$\n]*?(?:\n[^$\n]*?){0,2}[^\s,.$])?)
      \$(?=[\s\-.,?;:'")]|\Z)
    """,
    re.VERBOSE | re.DOTALL,
)

SRC_BLOCK_RE = re.compile(
    r"^[ \t]*\#\+BEGIN_SRC(?:[ \t]+(\S+))?[^\n]*\n(.*?)^[ \t]*\#\+END_SRC",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

LISP_ESCAPE_RE = re.compile(r"\\(.)", re.DOTALL)


class IdentifierType(Enum):
    """
    .. deprecated:: 0.2.0
      No longer used by orgroamtools. Kept for compatibility.
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


class BodyNotFoundWarning(Warning):
    """
    Warns that a node's body could not be read.

    The node's file no longer exists, or no longer contains a heading (or file
    property drawer) with the node's ID. This usually means the org-roam
    database is out of date; run ``(org-roam-db-sync)`` in Emacs. The body is
    returned as an empty string.
    """


class NodeNotFoundError(KeyError, AttributeError):
    """
    Raised when no node in the collection matches an identifier.

    Subclasses ``KeyError``. It also subclasses ``AttributeError``, which was
    raised in this situation before, so existing ``except AttributeError``
    handlers keep working.
    """


def decode_lisp_string(value):
    """Decode a string value as stored by org-roam

    org-roam stores strings in its database as printed Emacs Lisp strings:
    wrapped in double quotes, with ``"`` and ``\\`` backslash-escaped.
    Values that are not quoted strings are returned unchanged.

    Parameters
    ----------
    value : ``str | None``
        Raw value from the org-roam database

    Returns
    -------
    ``str | None``
        Decoded string
    """
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] == '"':
        return LISP_ESCAPE_RE.sub(r"\1", value[1:-1])
    return value


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
    # Code isn't math, even when it contains $ or \( ... \)
    text = SRC_BLOCK_RE.sub("", text)
    snippets = []
    for match in ORG_LATEX_RE.finditer(text):
        groups = match.groupdict()
        del groups["env"]
        snippets.append(next(g for g in groups.values() if g is not None).strip())
    return snippets


def extract_src_blocks(text: str) -> list[tuple[str | None, str]]:
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
    return [
        (match.group(1), match.group(2).strip())
        for match in SRC_BLOCK_RE.finditer(text)
    ]
