import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

ORG_ID_FORMAT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# TODO Maybe consolidate all links to this class for richer representation of links?
@dataclass
class OrgLink:
    """
    Miscellaneous link type for other org-mode type links

    Attributes
    ----------
    type : str
        the type of linke (e.g. https, fil)
    content : str
        content of the link
    desc : Optional[str]
        description of the link
    """
    type : str
    content : str
    desc : Optional[str]




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
