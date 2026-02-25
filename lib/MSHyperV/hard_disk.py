from typing import List, TypedDict
from lib.genericType import *


class HardDisk:
    def __init__(self, disk, type_disk: HddType):
        self.ControllerType: ControllerType = int(disk["ControllerType"])
        self.ControllerNumber: int = int(disk["ControllerNumber"])
        self.ControllerLocation: int = int(disk["ControllerLocation"])

        self.avhdx = False
        self.Path: str = disk["Path"]
        self.Parent: str = disk["ParentPath"]
        self.index: int = self.ControllerLocation
        self.VhdFormat: DiskType = DiskType.VHD if disk["VhdFormat"] == 2 else DiskType.VHDX
        self.Size = disk["Size"]
        self.FileSize = disk["FileSize"]
        self.type_disk: HddType = type_disk

        self.compute()

    def compute(self):
        self.FileName: str = self.Path.split("\\")[-1]
        self.Location: str = "/".join(self.Path.split("\\")[:-1])

        self.Letter: str = self.Location.split(":")[0].lower()
        self.smb: str = f"{self.Letter}{self.Location.split(':')[1].replace(' ' , '\\ ')}/{self.FileName}"

    def __repr__(self) -> str:
        return (
            f"HardDisk(index={self.index}, file_name='{self.FileName}', "
            f"location='{self.Location}', controller_type={self.ControllerType}, "
            f"vhd_format={self.VhdFormat.name}, size={self.Size}, file_size={self.FileSize}, "
            f"type_disk={self.type_disk.name})"
        )


class HardDisks:
    def __init__(self):
        self.index: int = 0
        self.harddisks: List[HardDisk] = []

    def add(self, harddisk: HardDisk):
        self.harddisks.append(harddisk)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index < len(self.harddisks):
            harddisk: HardDisk = self.harddisks[self.index]
            self.index += 1
            return harddisk
        else:
            raise StopIteration
