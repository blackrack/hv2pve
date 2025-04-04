import urllib3, logging, time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from proxmoxer import ProxmoxAPI
from .cnxLogger import ContextLogger
from typing import List

from abc import ABC, abstractmethod


class VM(ABC):
    @abstractmethod
    def getBootDiks(self):
        pass


class Tag:
    def __init__(self):
        self.tags: List[str] = ["imported"]

    def add(self, tag: str):
        self.tags.append(tag)

    def __str__(self):
        return ",".join(self.tags)


class TemplateProxmoxVM:
    def __init__(self):
        self.cfg = {
            "name": None,
            "memory": None,
            "machine": "q35",
            "agent": 1,
            "cores": 1,
            "sockets": None,
            "ostype": "l26",
            "scsihw": "virtio-scsi-pci",
            "hotplug": 1,
            "tablet": 1,
            "vga": "qxl",
            "cpu": "host",
            "start": "0",
            "tags": None,
            "description": None,
        }

    def set(self, **kargs):
        for k, v in kargs.items():
            self.cfg[k] = v

    def network(self, slot, value):
        self.cfg[slot] = value

    def get(self):
        return self.cfg


class ProxDisk:
    def __init__(self, type, lp):
        self.type = type
        self.lp = lp

    def slot(self):
        return f"{self.type}{self.lp}"

    def __str__(self):
        return self.slot()


class ProxNetwork:
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


class ProxVM(VM):
    def __init__(self, vm):
        self.vmid = vm.get("vmid")
        self.name = vm.get("name")
        self.disk = []

    def addDisk(self, disk: ProxDisk):
        self.disk.append(disk)

    def getBootDiks(self) -> ProxDisk:
        return self.disk[0]


class Prox:
    def __init__(self, ip, user, password):
        try:
            proxmox_api = ProxmoxAPI(host=ip, user=user, password=password, verify_ssl=False)
            logging.info("Connected to Proxmox API")
            self.api = proxmox_api
        except Exception as e:
            raise (f"Failed to connect to Proxmox API: {str(e)}")

    def getNodes(self):
        return self.api.nodes.get()

    def IsExistVMByid(self, vmid):
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if vmid == vm.get("vmid", "brak nazwy"):
                    return vm
        return None

    def IsExistVM(self, name) -> ProxVM:
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if name == vm.get("name", "brak nazwy"):
                    return ProxVM(vm)
        return None

    def IsExistVMByHyperVID(self, id) -> bool:
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()

            for vm in vms:
                vv = self.api.nodes(node["node"]).qemu(vm["vmid"]).config.get()
                if id in vv.get("description", "brak nazwy"):
                    return True
        return False

    def findNodeWithVM(self, vmid):
        nodes = self.getNodes()
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if vmid == vm.get("vmid", "brak nazwy"):
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

    def setboot(self, vm: VM):
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

    def wait_for_task(self, ticket, context_logger: ContextLogger):
        context_logger.add("[Ticket]")
        while True:
            status = self.status_ticket(ticket)
            context_logger.log(level=logging.INFO, message=f"status: {status['status']}")
            if status and status["status"] != "running":
                context_logger.log(
                    level=logging.INFO,
                    message=f"exitstatus: {status['exitstatus']}",
                )
                context_logger.back()
                return
            time.sleep(1)
