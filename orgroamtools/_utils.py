import re
from enum import Enum

ORG_ID_FORMAT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class IdentifierType(Enum):
    """
    Nodes in an org-roam graph can identified uniquely by their ID, and non-uniquely
    by their title. This enum helps disambiguate the the type of an identifier
    for functions that take a generic identifier in as an input. e.g. RoamGraph.node
    """

    TITLE = 1
    ID = 2
    NOTHING = 0


class DuplicateTitlesWarning(Warning):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)
