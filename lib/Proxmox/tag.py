from typing import List

from .tagtype import *


class ProxmoxTag:
    def __init__(self):
        self.tags: List[str] = [ProxmoxTagType.HV2PVE]

    def add(self, tag: str):
        self.tags.append(tag)

    def __str__(self):
        return ",".join(self.tags)
