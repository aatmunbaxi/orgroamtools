from enum import Enum
import orgparse as op


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
    op.load(fname).get_body()
