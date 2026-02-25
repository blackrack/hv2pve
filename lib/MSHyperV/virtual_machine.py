from typing import List, Dict
from .hard_disk import HardDisk, HardDisks

from .network import Network, Networks
from lib.genericType import *
import time, logging


class BootItem:
    def __init__(self, item):
        self.BootType = item["BootType"]
        self.Description = item["Description"]
        self.FirmwarePath = item["FirmwarePath"]
        self.FirmwarePath = item["FirmwarePath"]
        self.Device = item["Device"]


class BootOrder:
    def __init__(self, raw):
        self.index: int = 0
        self.boots: List[BootItem] = []
        for raw_boot in raw:
            self.add(BootItem(raw_boot))

    def add(self, boot: BootItem):
        self.boots.append(boot)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index < len(self.boots):
            boot: BootItem = self.boots[self.index]
            self.index += 1
            return boot
        else:
            raise StopIteration


class Firmware:
    def __init__(self, date):
        self.BootOrder = BootOrder(date["BootOrder"])

    def isWindows(self):
        for item in self.BootOrder:
            if item.BootType == 3 and "bootmgfw.efi" in item.FirmwarePath:
                return True

        return False


class CheckPoint:
    def __init__(self, checkpoint):
        # self.index=index
        self.checkpoint = checkpoint
        self.id = checkpoint["Id"]
        self.SnapshotType = checkpoint["SnapshotType"]
        self.ParentCheckpointId = checkpoint["ParentCheckpointId"]
        self.ParentCheckpointName = checkpoint["ParentCheckpointName"]
        self.CheckpointType = checkpoint["CheckpointType"]
        self.CreationTime = checkpoint["CreationTime"]
        self.Name = checkpoint["Name"]


class VirtualMachine:
    def __init__(self, raw_hyper_vm: Dict, os: str, client):
        self.os = os
        self._client = client
        self.reimport: bool = False
        self._update(raw_hyper_vm=raw_hyper_vm)

    def IsRunning(self):
        return self.State

    def PowerOn(self):
        self._client.PowerOn(name=self.name)

    def getCheckpoints(self):
        return self.checkpoints

    def _update(self, raw_hyper_vm: Dict):
        self.ComputerName = raw_hyper_vm["ComputerName"]
        self.name = raw_hyper_vm["VMName"]
        self.CheckpointType: HyperVCheckpointType = raw_hyper_vm["CheckpointType"]
        self.Generation = raw_hyper_vm["Generation"]
        self.MemoryMaximum = int(raw_hyper_vm["MemoryMaximum"] / (1024 * 1024))
        self.MemoryMinimum = int(raw_hyper_vm["MemoryMinimum"] / (1024 * 1024))
        self.MemoryStartup = int(raw_hyper_vm["MemoryStartup"] / (1024 * 1024))
        self.ProcessorCount = raw_hyper_vm["ProcessorCount"]
        self.vmid = raw_hyper_vm["VMId"]
        self.State = raw_hyper_vm["State"]

        self.checkpoints: List[CheckPoint] = [CheckPoint(checkpoint=checkpoint) for checkpoint in raw_hyper_vm["CheckPoints"]]
        _typeDisk: HddType = HddType.IDE if self.os == "windows" else HddType.VIRTIO

        if self.Generation == 2:
            paylaod = self._client.getBootOrderInfo(name=self.name)[0]
            self.firmware = Firmware(paylaod)
            # if self.firmware.isWindows():
            #     _typeDisk: HddType = HddType.IDE

        self.disks: List[HardDisk] = [HardDisk(disk=disk, type_disk=_typeDisk) for disk in raw_hyper_vm["HardDrives"]]
        self.networks: List[Network] = [Network(network=network, index=index) for index, network in enumerate(raw_hyper_vm["NetworkAdapters"])]

    def refresh(self):
        tmp = self._client.getCheckPointByVmName(name=self.name)
        tmps = self._client.getDiskByVmName(name=self.name)
        for disk in tmps:
            curentdisk = self.findDisk(ControllerLocation=disk["ControllerLocation"], ControllerNumber=disk["ControllerNumber"])
            curentdisk.Path = disk["Path"]
            curentdisk.compute()
            time.sleep(2)

        self.checkpoints: List[CheckPoint] = [CheckPoint(checkpoint=checkpoint) for checkpoint in tmp]

    def findDisk(self, ControllerNumber, ControllerLocation):
        for disk in self.disks:
            if disk.ControllerLocation == ControllerLocation and disk.ControllerNumber == ControllerNumber:
                return disk
        return False

    def getTotalDisksSize(self):
        totalsize = 0
        for disk in self.disks:
            totalsize += disk.Size
        return totalsize

    def CreateCheckpoint(self, name):
        output = self._client.NewCheckPoint(vmid=self.name, name=name)
        self._client.logger.log(level=logging.DEBUG, message=f"NewCheckPoint: output:{output} ")
        self._waitForCheckpoint(name=name)

    def _waitForStatus(self, status):
        a = 0
        while True:
            a += 1
            if a > 10:
                raise Exception("Problem with status VM")
            time.sleep(10)
            status_json = self._client.getStatusVM(name=self.name)
            self._client.logger.log(level=logging.INFO, message=f"status: { status_json } ")
            if status_json["Status"] == status:
                return

    def _waitForCheckpoint(self, name):
        a = 0
        while True:
            a += 1
            if a > 10:
                raise Exception("Problem with create Checkpoint")
            time.sleep(10)
            self._waitForStatus(status="Operating normally")
            # Merging disks
            # Creating checkpoint
            # Operating normally

            snaps = self._client.getCheckPointByVmName(name=self.name)

            for snap in snaps:
                if snap["Name"] == name:
                    self._client.logger.log(level=logging.DEBUG, message=f"Detect Snap: { snap['Name'] } ")
                    time.sleep(10)
                    return

    def RemoveCheckpoint(self, name):
        self._client.RemoveCheckPoint(vmid=self.name, name=name)
        self._waitForStatus(status="Operating normally")

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

    def __str__(self):
        return f"[ID]: {self.vmid} | [CP] {len(self.checkpoints)} | [GEN]: {self.Generation} | [HDD]:{ len(self.disks)} | [NET]:{ len(self.networks)} | [VM]: {self.name}"


class VirtualMachines:
    def __init__(self):
        self.index: int = 0
        self.vms: List[VirtualMachine] = []

    def add(self, vm: VirtualMachine):
        self.vms.append(vm)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self._position < len(self.vms):
            vm: VirtualMachine = self.vms[self.index]
            self.index += 1
            return vm
        else:
            raise StopIteration
