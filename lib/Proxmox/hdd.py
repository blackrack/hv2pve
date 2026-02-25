from .. import MSHyperV

from .tagtype import *


class ProxmoxHDD:
    def __init__(self, disk: MSHyperV.HardDisk):
        self.type: HddType = disk.type_disk
        self.index: int = disk.index
        self.Location = ""
        self._Type = DiskType.RAW
        self.bind = None

    def slot(self):
        return f"{self.type}{self.index}"

    def __str__(self):
        return self.slot()
