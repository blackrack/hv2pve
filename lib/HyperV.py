from typing import List, Dict
from enum import Enum


class ControllerType(Enum):
    IDE = 0
    SCSI = 1


class CustomAtribute(Enum):
    OS = "os"


class HDD:
    def __init__(self, disk, lp: int):
        self.ControllerType: ControllerType = int(disk["ControllerType"])
        self.Path: str = disk["Path"]
        self.FileName: str = disk["Path"].split("\\")[-1]
        self.Location: str = "/".join(disk["Path"].split("\\")[:-1])
        self.lp: int = lp
        self.VhdFormat = "vpc" if disk["VhdFormat"] == 2 else "vhdx"
        self.Size = disk["Size"]
        self.FileSize = disk["FileSize"]


class Network:
    def __init__(self, network, lp: int):
        self.MacAddress = network["MacAddress"]
        self.SwitchId = network["SwitchId"]
        self.lp: int = lp
        self.vlanid = network["VLANID"]


class HyperVM:

    def getCheckpoints(self):
        return self.checkpoints

    def getTotalDiskSize(self):
        totalsize = 0
        for disk in self.disks:
            totalsize += disk.Size
        return totalsize

    def getMaxFileSizeSingleDisk(self):
        size = 0

        for disk in self.disks:
            if disk.FileSize > size:
                size = disk.FileSize
        return size

    def setBoot(self, data):
        tmp = data[0]["BootOrder"]
        for id, item in enumerate(tmp):
            if item["BootType"] == 3:
                self.efi = item["FirmwarePath"]

    def _prep_notes(self, notes):
        rows = notes.split("\n")
        if rows:
            for row in rows:
                value = row.split(":")
                if value[0] in CustomAtribute._value2member_map_:
                    self.customAtribute[value[0]] = value[1]

    def __init__(self, vm):
        self.customAtribute: Dict = {}
        self.ComputerName = vm["ComputerName"]
        self.name = vm["VMName"]
        self.Generation = vm["Generation"]
        self.MemoryMaximum = int(vm["MemoryMaximum"] / (1024 * 1024))
        self.MemoryMinimum = int(vm["MemoryMinimum"] / (1024 * 1024))
        self.MemoryStartup = int(vm["MemoryStartup"] / (1024 * 1024))
        self.ProcessorCount = vm["ProcessorCount"]
        self.vmid = vm["VMId"]
        self.State = vm["State"]
        self.checkpoints = vm["CheckPoints"]

        self.disks: List[HDD] = [HDD(disk, lp) for lp, disk in enumerate(vm["HardDrives"])]
        self.networks: List[Network] = [Network(net, lp) for lp, net in enumerate(vm["NetworkAdapters"])]
        self._prep_notes(vm["Notes"])

    def __str__(self):
        return f"[ID]: {self.vmid} | [GEN]: {self.Generation} | [HDD]:{ len(self.disks)} | [NET]:{ len(self.networks)} | [VM]: {self.name}"
