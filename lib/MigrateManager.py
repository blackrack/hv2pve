from .Proxmox import TemplateProxmoxVM, ProxmoxVM, ProxmoxClient
from lib import MSHyperV
from .RemoteWorker import RemoteWorker
from .DiskManager import DiskManager
from .tool import prep_proxmox_storage
from typing import List
from .genericType import *
from .config import Config
import logging
import time


class MigrateManager:
    def __init__(
        self,
        remote_worker: RemoteWorker,
        hyperV_virtual_machines: List[MSHyperV.VirtualMachine],
        config: Config,
        proxmox_client: ProxmoxClient,
        disk_manager: DiskManager,
        hyperV_client: MSHyperV.Client,
    ):
        self.hyperV_virtual_machines = hyperV_virtual_machines
        self.logger = config.logger
        self.config = config
        self.proxmox_client = proxmox_client
        self.disk_manager = disk_manager
        self.hyperV_client = hyperV_client
        self.remote_worker = remote_worker

    def _prep_variable_path(self, disk):
        proxmox_storage = prep_proxmox_storage(self.config, disk.Location)
        proxmox_storage_type = self.remote_worker.DatastoreType(proxmox_storage)
        proxmox_storage_location = self.remote_worker.DatastoreLocation(proxmox_storage)
        return proxmox_storage, proxmox_storage_type, proxmox_storage_location

    def run(self):
        list_letter = self.hyperV_client.GetSharedDisk()

        try:
            for item in list_letter:
                self.source_mount = f"//{self.config.HyperVIP}/{item}$"
                self.options = f"username={self.config.HyperVUser},password={self.config.HyperVPass},vers={self.config.HyperVSMBVersion}"
                self.destination_mount = f"{self.config.ProxmoxMountPath}/{self.config.id_migration}/{item}"
                self.remote_worker.Mount(options=self.options, source=self.source_mount, destination=self.destination_mount, type_mount=MountType.CIFS)

            for hyperV_vm in self.hyperV_virtual_machines:

                self._run(hyperV_vm=hyperV_vm)

                if self.config.ProxmoxImportOnce:
                    break
        finally:
            # clean all important thinks
            for item in list_letter:
                self.destination_mount = f"{self.config.ProxmoxMountPath}/{self.config.id_migration}/{item}"
                self.remote_worker.Umount(path=self.destination_mount)

    def prep_disk(self, disks, proxmox_vm):
        for disk in disks:
            self.logger.add(f"[ {disk.Path} ]")
            proxmox_storage, proxmox_storage_type, proxmox_storage_location = self._prep_variable_path(disk=disk)
            proxmox_vm.createDisk(proxmox_storage=proxmox_storage, disk=disk, proxmox_storage_type=proxmox_storage_type, proxmox_storage_location=proxmox_storage_location)
            self.logger.back()

    def _run(self, hyperV_vm: MSHyperV.VirtualMachine):
        self.logger.add(f"[ {hyperV_vm.name} ]")
        self.logger.add(f"[ Creating ... ]")

        if hyperV_vm.reimport:
            self.logger.log(level=logging.INFO, message=f"Proxmox Exist but failed fast import: reimported")
        else:
            template: TemplateProxmoxVM = TemplateProxmoxVM(hyper_vm=hyperV_vm, config=self.config)
            ticket = self.proxmox_client.createVM(vm_cfg=template.getConfig())
            self.proxmox_client.wait_for_task(ticket=ticket, logger=self.logger)

        proxmox_vm: ProxmoxVM = self.proxmox_client.IsExistVM(name=hyperV_vm.name)
        proxmox_vm.AddTag(self.config.id_migration)

        self.logger.back().add(f"[ Created ]")
        self.logger.log(level=logging.INFO, message=f"Proxmox VM ID: {proxmox_vm.vmid}")
        self.logger.back()

        self.prep_disk(disks=hyperV_vm.disks, proxmox_vm=proxmox_vm)

        if not hyperV_vm.reimport and hyperV_vm.Generation == 2:
            self.disk_manager.prep_eif(proxmox_vm=proxmox_vm)

        # set init
        proxmox_vm.AddTag(ProxmoxTagType.INIT)

        self.proxmox_client.setboot(vm=proxmox_vm)
        if self.config.HyperVCreateCheckPoint:
            # snap
            a = 0
            loop = True
            collect_snapshot = []

            self.logger.add(f"[ Checkpoint{a} ]")

            hyperV_vm.CreateCheckpoint(name=f"{self.config.id_migration}-Checkpoint{a}")

            collect_snapshot.append(f"Checkpoint{a}")

            self.disk_manager.migrate_disks(proxmox_vm=proxmox_vm, hyperV_vm=hyperV_vm, avhdx=True)

            while loop:
                hyperV_vm.refresh()
                b = a
                a = a + 1

                self.logger.add(f"[ Checkpoint{a} ]")

                hyperV_vm.CreateCheckpoint(name=f"{self.config.id_migration}-Checkpoint{a}")

                self.disk_manager.migrate_disks(proxmox_vm=proxmox_vm, hyperV_vm=hyperV_vm, avhdx=True)

                hyperV_vm.refresh()
                hyperV_vm.RemoveCheckpoint(name=f"{self.config.id_migration}-Checkpoint{b}")
                self.logger.back().back().add(f"[ Checkpoint{a} ]")

                if a == self.config.MigrateMaxAvhdxChain:
                    self.logger.log(level=logging.INFO, message=f"Poweroff")
                    loop = False
                    self.PowerOffVmOnHyperV(hyperV_vm=hyperV_vm)

            # last checkpoint after poweroff
            self.disk_manager.migrate_disks(proxmox_vm=proxmox_vm, hyperV_vm=hyperV_vm, avhdx=True)

            # run after last sync
            if self.config.ProxmoxStartAfter:
                self.proxmox_client.start(proxmox_vm.vmid)

            hyperV_vm.RemoveCheckpoint(name=f"{self.config.id_migration}-Checkpoint{a}")
            self.logger.back()

        else:
            self.disk_manager.migrate_disks(proxmox_vm=proxmox_vm, hyperV_vm=hyperV_vm)

            if self.config.ProxmoxStartAfter:
                self.proxmox_client.start(proxmox_vm.vmid)

        self.proxmox_client.SetTag(proxmox_vm, ProxmoxTagType.IMPORTED)

        self.logger.back()

    def PowerOffVmOnHyperV(self, hyperV_vm):
        self.hyperV_client.PowerOffVM(vmid=hyperV_vm.name, force=self.config.HyperVPowerOffForce, turnoff=self.config.HyperVTurnOff, noconfirm=self.config.HyperVNoConfirm)
        while True:
            state = self.hyperV_client.WaitForPoweroff(vmid=hyperV_vm.name)["State"]
            self.logger.log(level=logging.INFO, message=f"VM state: { state }")
            if int(state) == HyperVVmState.STOP:
                break
            time.sleep(10)
