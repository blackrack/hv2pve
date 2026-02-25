from ..tool import macformat
from .. import MSHyperV

from .tagtype import *
from .tag import ProxmoxTag
from .network import ProxmoxNetworkCart


class TemplateProxmoxVM:
    def __init__(self, hyper_vm: MSHyperV.VirtualMachine, config):
        self.hyper_vm = hyper_vm
        self.tags: ProxmoxTag = ProxmoxTag()
        self.tags.add(f"{hyper_vm.os}")
        self.tags.add(f"gen{hyper_vm.Generation}")
        self.tags.add(f"{hyper_vm.vmid}")
        self.cfg = {
            "name": hyper_vm.name,
            "memory": hyper_vm.MemoryStartup,
            "machine": "q35",
            "agent": 1,
            "cores": 1,
            "sockets": hyper_vm.ProcessorCount,
            "ostype": "l26",
            "scsihw": "virtio-scsi-pci",
            "hotplug": 1,
            "tablet": 1,
            "vga": "qxl",
            "cpu": "host",
            "start": "0",
            "tags": self.tags,
            "description": f"Import from {hyper_vm.ComputerName}, id={hyper_vm.vmid}",
        }
        if hyper_vm.Generation == 2:
            self.cfg["bios"] = "ovmf"

        self.config = config
        self._network()

    def add_Tag(self, tag):
        self.tags.add(tag)

    def _network(self):
        map_bridges = self.config.ProxmoxSwitchMapping
        bridge = self.config.ProxmoxSwitchDefault

        for network in self.hyper_vm.networks:
            if network.SwitchId in map_bridges:
                bridge = map_bridges[network.SwitchId]
            networkCart: ProxmoxNetworkCart = ProxmoxNetworkCart(typeNetCard=self.config.ProxmoxNetworkType, bridge=bridge, macaddr=macformat(network.MacAddress))

            if network.vlanid:
                networkCart.setVlan(network.vlanid)

            self.cfg[f"net{network.index}"] = networkCart

    def set(self, **kargs):
        for k, v in kargs.items():
            self.cfg[k] = v

    def network(self, slot, value):
        self.cfg[slot] = value

    def getConfig(self):
        return self.cfg
