import warnings
from enum import Enum

class IdentifierType(Enum):
    """
    Nodes in an org-roam graph can identified uniquely by their ID, and non-uniquely
    by their title. This enum helps disambiguate the the type of an identifier
    for functions that take a generic identifier in as an input. e.g. RoamGraph.node
    """
    TITLE = None
    ID = None
    NOTHING = None


class DuplicateTitlesWarning(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)