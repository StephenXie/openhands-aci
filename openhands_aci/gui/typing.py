from enum import StrEnum
from typing import TypedDict


class Resolution(TypedDict):
    width: int
    height: int


class ScalingSource(StrEnum):
    COMPUTER = 'computer'
    API = 'api'
