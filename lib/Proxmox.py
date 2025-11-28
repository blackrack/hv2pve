import urllib3, logging, time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from proxmoxer import ProxmoxAPI
from .clogger import ContextLogger
from typing import List
from .tool import macformat
from .HyperV import HyperVVM, HyperVHDD


class ProxmoxTag:
    def __init__(self):
        self.tags: List[str] = ["imported"]

    def add(self, tag: str):
        self.tags.append(tag)

    def __str__(self):
        return ",".join(self.tags)


class TemplateProxmoxVM:
    def __init__(self, hyper_vm: HyperVVM, config):
        self.hyper_vm = hyper_vm
        self.tags: ProxmoxTag = ProxmoxTag()
        self.tags.add(f"{hyper_vm.os}")
        self.tags.add(f"gen{hyper_vm.Generation}")
        self.tags.add(f"{hyper_vm.vmid}")
        self.tags.add(f"hv2pve")
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
            networkProx: ProxmoxNetwork = ProxmoxNetwork(typeNetCard=self.config.ProxmoxNetworkType, bridge=bridge, macaddr=macformat(network.MacAddress))

            if network.vlanid:
                networkProx.setVlan(network.vlanid)

            self.cfg[f"net{network.index}"] = networkProx

    def set(self, **kargs):
        for k, v in kargs.items():
            self.cfg[k] = v

    def network(self, slot, value):
        self.cfg[slot] = value

    def get(self):
        return self.cfg


class ProxmoxHDD:
    def __init__(self, disk: HyperVHDD):
        self.type = disk.type_disk
        self.index = disk.index

    def slot(self):
        return f"{self.type}{self.index}"

    def __str__(self):
        return self.slot()


class ProxmoxNetwork:
    def __init__(self, typeNetCard, bridge, macaddr):
        self.typeNetCard = typeNetCard
        self.bridge = bridge
        self.macaddr = macaddr
        self.vlandid = 0

    def setVlan(self, id):
        self.vlandid = id

    def __str__(self):
        output = f"{self.typeNetCard},bridge={self.bridge},macaddr={self.macaddr}"
        if self.vlandid:
            output += f",tag={self.vlandid}"
        return output


class ProxmoxVM:
    def __init__(self, vm):
        self.vmid = vm.get("vmid")
        self.name = vm.get("name")
        self.disk = []

    def addDisk(self, disk: ProxmoxHDD):
        self.disk.append(disk)

    def getBootDiks(self) -> ProxmoxHDD:
        return self.disk[0]


class ProxmoxClient:
    def __init__(self, config):
        self.config = config
        self.verify_ssl = False
        self.logger = config.logger

        self._connect()

    def _connect(self):
        try:
            self.api = ProxmoxAPI(host=self.config.ProxmoxIP, user=f"{self.config.ProxmoxUser}@pam", password=self.config.ProxmoxPass, verify_ssl=self.verify_ssl)
            self.logger.log(level=logging.INFO, message=f"Connected to Proxmox API")
        except Exception as e:
            raise (f"Failed to connect to Proxmox API: {str(e)}")

    def getNodes(self):
        return self.api.nodes.get()

    def IsExistVMByid(self, vmid):
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if vmid == vm.get("vmid", "null"):
                    return vm
        return None

    def IsExistVM(self, name) -> ProxmoxVM:
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if name == vm.get("name", "null"):
                    return ProxmoxVM(vm)
        return None

    def IsExistVMByHyperVID(self, id) -> bool:
        nodes = self.getNodes()
        for node in nodes:
            qemu_instances = self.api.nodes(node["node"]).qemu.get()

            for qemu_instance in qemu_instances:
                vm = self.api.nodes(node["node"]).qemu(qemu_instance["vmid"]).config.get()
                if id in vm.get("description", "null") or id in vm.get("tags", "null"):
                    return True
        return False

    def findAllVM(self):
        nodes = self.getNodes()
        vms = []
        for node in nodes:
            vms = vms + self.api.nodes(node["node"]).qemu.get()
        return vms

    def GetTagByVmId(self, vmid):
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if vmid == vm.get("vmid", "null"):
                    return vm.get("tags", "null")
        return False

    def findNodeWithVM(self, vmid):
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if vmid == vm.get("vmid", "null"):
                    return node["node"]
        return False

    def start(self, vmid):
        node = self.findNodeWithVM(vmid)
        self.api.nodes(node).qemu(vmid).status.start.post()

    def stop(self, vmid):
        node = self.findNodeWithVM(vmid)
        return self.api.nodes(node).qemu(vmid).status.stop.post()

    def status(self, vmid):
        node = self.findNodeWithVM(vmid)
        return self.api.nodes(node).qemu(vmid).status.current.get()

    def setboot(self, vm: ProxmoxVM):
        node = self.findNodeWithVM(vm.vmid)
        boot_order = f"order={vm.getBootDiks()}"
        self.api.nodes(node).qemu(vm.vmid).config.set(boot=boot_order)

    def createVM(self, vm_cfg):
        vm_cfg["vmid"] = self.api.cluster.nextid.get()
        nodes = self.getNodes()
        for node in nodes:
            node_object = self.api.nodes(node["node"])
            task_id = getattr(node_object, "qemu").create(**vm_cfg)
            return task_id
        raise Exception("Node PVE not Found")

    def deleteVM(self, vmid):
        node = self.findNodeWithVM(vmid)
        self.api.nodes(node).qemu(vmid).delete()

    def status_ticket(self, task_id):
        nodes = self.getNodes()
        node = self.api.nodes(nodes[0]["node"])
        return node.tasks(task_id).status.get()

    def wait_for_task(self, ticket, logger: ContextLogger):
        logger.add("[Ticket]")
        while True:
            status = self.status_ticket(ticket)
            logger.log(level=logging.INFO, message=f"status: {status['status']}")
            if status and status["status"] != "running":
                logger.log(
                    level=logging.INFO,
                    message=f"exitstatus: {status['exitstatus']}",
                )
                logger.back()
                return
            time.sleep(1)
