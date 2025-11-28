import json, logging, os
from .clogger import ContextLogger
from .tool import generate_random_string


class HyperVDiskMapping:
    def __init__(self, args):
        self.hypervPath = args["HYPERV_PATH"]
        self.hyperVSharedDisk = args["HYPERV_SHAREDISK"]
        self.proxmoxStorage = args["PROXMOX_STORAGE"]


class Config:
    def __init__(self, args):
        self.file = args.config
        self.verbose = args.verbose
        self.dry_run = args.dry_run

        self._raw_dict_data = self._read()
        self._prep()

    def _prep(self):
        # read HYPER-V
        self.HyperVIP: str = os.environ["HYPERV_IP"] if "HYPERV_IP" in os.environ else self._raw_dict_data.get("HYPERV_IP", None)
        self.HyperVUser = os.environ["HYPERV_USER"] if "HYPERV_USER" in os.environ else self._raw_dict_data.get("HYPERV_USER", "administrator")
        self.HyperVPass = os.environ["HYPERV_PASS"] if "HYPERV_PASS" in os.environ else self._raw_dict_data.get("HYPERV_PASS", None)
        self.HyperVAutoShareDisk = os.environ["HYPERV_AUTO_SHAREDISK"] if "HYPERV_AUTO_SHAREDISK" in os.environ else self._raw_dict_data.get("HYPERV_AUTO_SHAREDISK", False)
        self.HyperVSHAREDISK = os.environ["HYPERV_SHAREDISK"] if "HYPERV_SHAREDISK" in os.environ else self._raw_dict_data.get("HYPERV_SHAREDISK", "")
        self.HyperVCreateCheckPoint = os.environ["HYPERV_CREATE_CHECKPOINT"] if "HYPERV_CREATE_CHECKPOINT" in os.environ else self._raw_dict_data.get("HYPERV_CREATE_CHECKPOINT", False)

        self.HuperVVMLIST = self._raw_dict_data.get("HYPER_VM_LIST", [])
        self.HyperVShareDiskMapping = [HyperVDiskMapping(item) for item in self._raw_dict_data.get("HYPERV_SHAREDISK_MAPPING", [])]

        # read Proxmox
        self.ProxmoxIP = os.environ["PROXMOX_IP"] if "PROXMOX_IP" in os.environ else self._raw_dict_data.get("PROXMOX_IP", None)
        self.ProxmoxUser = os.environ["PROXMOX_USER"] if "PROXMOX_USER" in os.environ else self._raw_dict_data.get("PROXMOX_USER", "root")
        self.ProxmoxPass = os.environ["PROXMOX_PASS"] if "PROXMOX_PASS" in os.environ else self._raw_dict_data.get("PROXMOX_PASS", None)
        self.ProxmoxMountPath = os.environ["PROXMOX_MOUNTPATH"] if "PROXMOX_MOUNTPATH" in os.environ else self._raw_dict_data.get("PROXMOX_MOUNTPATH", "/tmp")
        self.ProxmoxImportPath = os.environ["PROXMOX_IMPORTPATH"] if "PROXMOX_IMPORTPATH" in os.environ else self._raw_dict_data.get("PROXMOX_IMPORTPATH", "/tmp")
        self.ProxmoxStorage = os.environ["PROXMOX_STORAGE"] if "PROXMOX_STORAGE" in os.environ else self._raw_dict_data.get("PROXMOX_STORAGE", None)
        self.ProxmoxSwitchDefault = os.environ["PROXMOX_SWITCH_DEFAULT"] if "PROXMOX_SWITCH_DEFAULT" in os.environ else self._raw_dict_data.get("PROXMOX_SWITCH_DEFAULT", "vmbr0")
        self.ProxmoxSwitchMapping = self._raw_dict_data.get("PROXMOX_SWITCH_MAPPING", {})
        self.ProxmoxNetworkType = os.environ["PROXMOX_NETWORK_TYPE"] if "PROXMOX_NETWORK_TYPE" in os.environ else self._raw_dict_data.get("PROXMOX_NETWORK_TYPE", "e1000")
        self.ProxmoxStartAfter = os.environ["PROXMOX_START_AFTER"] if "PROXMOX_START_AFTER" in os.environ else self._raw_dict_data.get("PROXMOX_START_AFTER", True)
        self.ProxmoxImportOnce = os.environ["PROXMOX_IMPORT_ONCE"] if "PROXMOX_IMPORT_ONCE" in os.environ else self._raw_dict_data.get("PROXMOX_IMPORT_ONCE", True)
        #

        self.logger = ContextLogger(logging.getLogger("migrate"), self.verbose)
        self.id_migration = f"MIG-{generate_random_string()}"

        pass

    def _read(self):
        try:
            with open(self.file, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            raise ("File not Exist")
        except json.JSONDecodeError as e:
            raise ("Error read file:", e)

    def GetVMOSConfig(self, vmid: str) -> str:
        for item in self.HuperVVMLIST:
            if isinstance(item, dict) and "VMID" in item and item["VMID"] == vmid and "OS" in item:
                return item["OS"]
        return "Generic"

    def IsVMId(self, vmid: str) -> bool:
        if self.HuperVVMLIST == []:
            return True
        for item in self.HuperVVMLIST:
            if item == vmid or (isinstance(item, dict) and "VMID" in item and item["VMID"] == vmid):
                return True
        return False
    
    def getAllDatastore(self) ->list[str]:
        output=[]
        if self.ProxmoxStorage:
            output.append(self.ProxmoxStorage)

        for item in self.HyperVShareDiskMapping:
            output.append(item.proxmoxStorage)

        return output


class Context:
    def __init__(self, config: Config, logger: ContextLogger):
        self.config: Config = config
        self.logger: ContextLogger = logger
