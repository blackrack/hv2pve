import logging, time
from typing import List

from ..genericType import *
from .hdd import ProxmoxHDD


class ProxmoxVM:
    def __init__(self, vm, client):
        self.client = client
        self.vmid = vm.get("vmid")
        self.name = vm.get("name")
        self.disks: List[ProxmoxHDD] = []

    def addDisk(self, disk: ProxmoxHDD):
        self.disks.append(disk)

    def AddTag(self, tag: ProxmoxTagType):
        self.client.SetTag(self, tag)

    def changeToIDE(self, disk: ProxmoxHDD):
        self.client.changeToIDE(disk=disk, vmid=self.vmid)
        disk.type = HddType.IDE

    def getBootDiks(self) -> ProxmoxHDD:
        output = [disk.slot() for disk in self.disks]
        return ";".join(output)

    def getDisk(self, disk_index):

        for item in self.disks:
            if item.index == disk_index:
                return item
        return False

    def createDisk(self, proxmox_storage, disk, proxmox_storage_type, proxmox_storage_location):
        self.client.logger.log(level=logging.INFO, message=f"Disk Size: {disk.Size}")

        pdisk = ProxmoxHDD(disk=disk)
        self.disks.append(pdisk)

        payload = {f"{disk.type_disk}{disk.index}": f"{proxmox_storage}:{disk.Size/(1024*1024*1024)}"}
        if proxmox_storage_type == ProxmoxDatastoreType.DIRECTORY:
            pdisk._Type = DiskType.QCOW2
            payload[f"{disk.type_disk}{disk.index}"] = payload[f"{disk.type_disk}{disk.index}"] + ",format=qcow2"

        self.client.logger.log(level=logging.DEBUG, message=f"Prep payload for proxmox Api: {payload}")

        # sprawdzmy czy dysk istnieje
        tmp = self.client.getDisk(vmid=self.vmid)
        if not f"{disk.type_disk}{disk.index}" in tmp:
            output = self.client.createDisk(payload=payload, vmid=self.vmid)
            self.client.logger.log(level=logging.DEBUG, message=f"create: {output}")

            time.sleep(5)
            tmp = self.client.getDisk(vmid=self.vmid)
        else:
            self.client.logger.log(level=logging.INFO, message=f"Disc Exist")

        path = ""
        if not f"{disk.type_disk}{disk.index}" in tmp:
            raise f"fuck"

        path = tmp[f"{disk.type_disk}{disk.index}"].split(",")[0].split(":")
        self.client.logger.log(level=logging.DEBUG, message=f"BIND: {disk.type_disk}{disk.index} {path}")
        pdisk.bind = tmp[f"{disk.type_disk}{disk.index}"].split(",")[0]

        if proxmox_storage_type == ProxmoxDatastoreType.ZFSPOOL:
            pdisk.Location = f"/dev/zvol/{proxmox_storage}/{path[1]}"
        elif proxmox_storage_type == ProxmoxDatastoreType.DIRECTORY:
            pdisk.Location = f"{proxmox_storage_location}/images/{path[1]}"
        elif proxmox_storage_type == ProxmoxDatastoreType.LVM:
            pdisk.Location = f"/dev/{proxmox_storage}/{path[1]}"

        self.client.logger.log(level=logging.DEBUG, message=f"Path: {pdisk.Location}")
        # return output
