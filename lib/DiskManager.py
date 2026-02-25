from .Proxmox import ProxmoxVM
from lib import MSHyperV
from .RemoteWorker import RemoteWorker
from .genericType import *
from .config import Config
import logging, time


class DiskManager:
    def __init__(self, config: Config, remote_worker: RemoteWorker, hyperV_client: MSHyperV.Client):
        self.config: Config = config
        self.remote_worker = remote_worker
        self.logger = config.logger
        self.hyperV_client = hyperV_client

    def migrate_disk(self, proxmox_vm: ProxmoxVM, disk: MSHyperV.HardDisk, avhdx=False):

        self.logger.add(f"[ migrate ]").add(f"[ {disk.Path} ]")
        destination_disk = proxmox_vm.getDisk(disk_index=disk.index)
        destination = destination_disk.Location

        if destination_disk._Type == DiskType.QCOW2:
            destination = self.remote_worker.createNBD(path=destination, index=disk.index)

        try:
            self.logger.log(level=logging.INFO, message=f"Start Converting")
            source = f"{self.config.ProxmoxMountPath}/{self.config.id_migration}/{disk.smb}"
            if avhdx:
                self.remote_worker.Convert(source=source, destination=destination)
            else:
                self.remote_worker.QemuConvert(source=source, destination=destination, typeDisk=disk.VhdFormat)

            if destination_disk.type != HddType.IDE:
                fstype = ""
                a = 0
                while True:
                    time.sleep(1)
                    fstype: str = self.remote_worker.GetFsType(destination=destination)
                    partition: str = self.remote_worker.GetPartitionType(destination=destination)
                    a = a + 1
                    if fstype or a > 2:
                        break
                if FSType.NTFS in fstype or "microsoft" in partition.lower():
                    self.logger.log(level=logging.DEBUG, message=f"Windows Disk Detected - use IDE")
                    proxmox_vm.changeToIDE(destination_disk)

        finally:
            if destination_disk._Type == DiskType.QCOW2:
                self.remote_worker.destroyNBD(index=disk.index)

        self.logger.back().back()

    def migrate_disks(self, proxmox_vm: ProxmoxVM, hyperV_vm: MSHyperV.VirtualMachine, avhdx=False) -> bool:

        for disk in hyperV_vm.disks:
            self.migrate_disk(proxmox_vm=proxmox_vm, disk=disk, avhdx=avhdx)

    def prep_eif(self, proxmox_vm: ProxmoxVM):

        ## EFI section:
        self.logger.add("[EFI]")

        efi_template = "efi-blank.qcow2"
        build_efi_for_vm = f"{proxmox_vm.vmid}-EFI.qcow2"

        ## EFI SCP
        efi_disk_location = f"{self.config.ProxmoxImportPath}/{build_efi_for_vm}"

        self.remote_worker.Copy(source=efi_template, destination=efi_disk_location)

        output_disk = self.remote_worker.Import(vmid=proxmox_vm.vmid, destination=efi_disk_location, storage=self.config.ProxmoxStorage)

        disk = f"{output_disk},efitype=4m,pre-enrolled-keys=1,size=528K"
        self.remote_worker.AttachDisk(vmid=proxmox_vm.vmid, slot="efidisk0", disk=disk)

        self.remote_worker.Clean(file=efi_disk_location)

        self.logger.back()
