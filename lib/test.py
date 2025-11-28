from .HyperV import HyperVClient, HyperVVM
from lib.clogger import ContextLogger
from abc import ABC, abstractmethod

import logging


class Rule(ABC):
    @abstractmethod
    def is_satisfied(self, vm: HyperVVM) -> bool:
        pass


class IsNotInConfig(Rule):
    def __init__(self, config):
        self.config = config

    def is_satisfied(self, vm: HyperVVM) -> bool:
        return self.config.IsVMId(vm.vmid)


class IsMigratedToProxmox(Rule):
    def __init__(self, proxmoxClient):
        self.proxmoxClient = proxmoxClient

    def is_satisfied(self, vm: HyperVVM) -> bool:

        return not self.proxmoxClient.IsExistVMByHyperVID(vm.vmid)


class IsRunningRule(Rule):
    def __init__(self, config):
        self.config = config

    def is_satisfied(self, vm: HyperVVM) -> bool:
        return self.config.HyperVCreateCheckPoint or vm.State != 2


class IsSize(Rule):
    def __init__(self, size,validTypeDatastore):
        self.size = size
        self.validTypeDatastore = validTypeDatastore

    def is_satisfied(self, vm: HyperVVM) -> bool:
        if self.validTypeDatastore:
            return True
        test = vm.getMaxFileSizeSingleDisk() < self.size

        return test


class NoCheckpoints(Rule):
    def is_satisfied(self, vm: HyperVVM) -> bool:
        return not vm.getCheckpoints()


class MigrationEligibilityChecker:
    def __init__(self, rules: list[Rule], config):
        self.rules = rules
        self.logger = config.logger

    def is_eligible(self, vm: HyperVVM) -> bool:
        self.logger.add("[ SKIP ]")

        list_output_rules = []
        for rule in self.rules:
            ready = rule.is_satisfied(vm)
            list_output_rules.append(ready)
            if not ready:
                self.logger.log(level=logging.INFO, message=f"VM {vm.name} {rule.__class__.__name__}")
        output = all(list_output_rules)

        self.logger.back()

        return output
