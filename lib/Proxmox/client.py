from proxmoxer import ProxmoxAPI
import logging, time


from ..clogger import ContextLogger
from .tagtype import *
from .datastore import ProxmoxDatastore
from .hdd import ProxmoxHDD
from .virtual_machine import ProxmoxVM


class ProxmoxClient:
    # https://pve.proxmox.com/pve-docs/api-viewer/
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

    def changeToIDE(self, disk: ProxmoxHDD, vmid):

        node = self.getNodes()[0]

        payload = {f"delete": f"{disk}"}
        self.api.nodes(node["node"]).qemu(vmid).config.post(**payload)

        payload = {f"ide{disk.index}": disk.bind}
        self.api.nodes(node["node"]).qemu(vmid).config.post(**payload)

    def createDisk(self, payload, vmid):
        node = self.getNodes()[0]
        disk = self.api.nodes(node["node"]).qemu(vmid).config.post(**payload)
        return disk

    def getDisk(self, vmid):
        node = self.getNodes()[0]
        disk = self.api.nodes(node["node"]).qemu(vmid).config.get()
        return disk

    def getDatastores(self) -> list[ProxmoxDatastore]:
        output: list[ProxmoxDatastore] = []
        node = self.getNodes()[0]

        list_datastore = self.api.nodes(node["node"]).storage.get()
        for item in list_datastore:
            if item["enabled"] == 1:
                output.append(ProxmoxDatastore(item))
        return output

    def SetTag(self, ProxVm: ProxmoxVM, tag: ProxmoxTagType):
        nodes = self.getNodes()
        new = tag
        for node in nodes:
            vms = self.api.nodes(node["node"]).qemu.get()
            for vm in vms:
                if ProxVm.vmid == vm.get("vmid", "null"):
                    tags = vm.get("tags", "")
                    if tags:
                        new = f"{tags},{tag}"
                    self.api.nodes(node["node"]).qemu(ProxVm.vmid).config.put(tags=new)

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
                    return ProxmoxVM(vm=vm, client=self)
        return None

    def IsExistVMByHyperVID(self, id):
        nodes = self.getNodes()
        for node in nodes:
            qemu_instances = self.api.nodes(node["node"]).qemu.get()

            for qemu_instance in qemu_instances:
                vm = self.api.nodes(node["node"]).qemu(qemu_instance["vmid"]).config.get()
                if id in vm.get("description", "null") or id in vm.get("tags", "null"):
                    return vm
        return None

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
        self.logger.log(level=logging.INFO, message=f"Unused ID: {vm_cfg["vmid"]}")
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
