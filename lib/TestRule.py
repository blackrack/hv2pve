from .Proxmox import ProxmoxDatastore, ProxmoxClient

from . import MSHyperV
from abc import ABC, abstractmethod
from .RemoteWorker import RemoteWorker
from .tool import humanable_size
from .genericType import *
from .config import Config

import logging


class Rule(ABC):
    @abstractmethod
    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        pass


# return True if vm is in config or config not exist
class CheckConfig(Rule):
    def __init__(self, config: Config):
        self.config: Config = config

    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        return self.config.IsVMId(vm.vmid)


# return True if vm not exist or exist adn has
class CheckStatusMigrated(Rule):
    def __init__(self, proxmoxClient: ProxmoxClient, config: Config):
        self.config: Config = config
        self.proxmoxClient = proxmoxClient

    def is_satisfied(self, hvm: MSHyperV.VirtualMachine) -> bool:
        vm = self.proxmoxClient.IsExistVMByHyperVID(hvm.vmid)
        if not vm:
            return True
        if vm and not "imported" in vm.get("tags", "null") and not "init" in vm.get("tags", "null"):
            self.config.logger.add(f"[ {hvm.name} ]").log(level=logging.INFO, message=f"VM template corupted: required manual delete before start iport again").back()
            return False

        elif vm and not "imported" in vm.get("tags", "null") and "init" in vm.get("tags", "null"):
            if self.config.MigrateOvewrite:
                hvm.reimport = True
                self.config.logger.add(f"[ {hvm.name} ]").log(level=logging.INFO, message=f"VM will be re imported").back()

                return True

        return False


# return True if vm is stop of hv2pve use avhdx chain
class CheckVMState(Rule):
    def __init__(self, config: Config):
        self.config: Config = config

    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        return self.config.HyperVCreateCheckPoint or vm.State != HyperVVmState.RUNNING


class CheckVMCheckpointType(Rule):
    def __init__(self, config: Config):
        self.config: Config = config

    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        return vm.CheckpointType != HyperVCheckpointType.DISABLE


# return True if datastore have enougth space
class CheckSize(Rule):
    def __init__(self, config: Config, remote_worker: RemoteWorker, proxmox_client: ProxmoxClient):
        self.config: Config = config
        self.remote_worker: RemoteWorker = remote_worker
        self.proxmox_client: ProxmoxClient = proxmox_client
        self.counter: int = 0
        self.datastores: list[ProxmoxDatastore] = proxmox_client.getDatastores()

    def _get_datastore(self, datastore_name: str) -> ProxmoxDatastore:
        for item in self.datastores:
            if item.storage == datastore_name:
                return item
        return None

    def _is_zfspool(self, datastore_name: str) -> bool:
        for item in self.datastores:
            if item.storage == datastore_name and item.type != "zfspool":
                return False
        return True

    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        for disk in vm.disks:
            self.config.logger.add(f"[ {disk.Path} ]")
            datastore_name = self.config.matchPath(path=disk.Location)
            self.config.logger.log(level=logging.DEBUG, message=f"Datastore {datastore_name}Location: {disk.Location} ")

            proxmox_storage: ProxmoxDatastore = self._get_datastore(datastore_name=datastore_name)

            if proxmox_storage.avail_test - disk.Size <= 0:
                self.config.logger.log(level=logging.INFO, message=f"Datastore {datastore_name} is too small: Required more disk: {proxmox_storage.avail_test - disk.Size}")
                self.config.logger.log(
                    level=logging.DEBUG,
                    message=f"Datastore {datastore_name} have: {humanable_size(proxmox_storage.avail_test)} vm disk required: {humanable_size(disk.Size)}",
                )
                self.config.logger.back()
                return False

            proxmox_storage.avail_test = proxmox_storage.avail_test - disk.Size
            self.config.logger.log(
                level=logging.DEBUG,
                message=f"Disk has been allocated on the datastore {proxmox_storage.storage}. Free space reduced by {humanable_size(disk.Size)}, {humanable_size(proxmox_storage.avail_test) }  remaining.",
            ).back()

        return True

    # return True if vm do not have checkpoit


class CheckSnapshot(Rule):
    def is_satisfied(self, vm: MSHyperV.VirtualMachine) -> bool:
        return not vm.getCheckpoints()


class MigrationEligibilityChecker:
    def __init__(self, rules: list[Rule], config: Config):
        self.rules = rules
        self.logger = config.logger

    def is_eligible(self, vm: MSHyperV.VirtualMachine) -> bool:

        list_output_rules = []
        for rule in self.rules:
            ready = rule.is_satisfied(vm)
            list_output_rules.append(ready)
            if not ready:
                self.logger.add("[ SKIP ]")
                self.logger.log(level=logging.INFO, message=f"VM {vm.name} {rule.__class__.__name__}")
                self.logger.back()
                return False
        output = all(list_output_rules)

        return output
