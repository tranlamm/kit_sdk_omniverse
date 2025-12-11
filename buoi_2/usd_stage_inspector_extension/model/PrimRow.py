from dataclasses import dataclass, field

@dataclass
class PrimRow:
    path: str
    name: str
    type: str
    is_active: bool
    children: list = field(default_factory=list)
    expanded: bool = False  