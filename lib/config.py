import json, logging, os
from .clogger import ContextLogger
import random, string


class HyperVDiskMapping:
    def __init__(self, args):
        self.hypervPath: str = args["HYPERV_PATH"]
        self.proxmoxStorage: str = args["PROXMOX_STORAGE"]

    def __str__(self):
        return f"<HyperVDiskMapping hypervPath={self.hypervPath};proxmoxStorage={self.proxmoxStorage} >"


class Config:
    def __init__(self, args):
        self.file = args.config
        self.verbose = args.verbose
        self.dry_run = args.dry_run

        self._raw_dict_data = self._read()
        self._prep()

    def _generate_random_string(self, length=10) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def _prep(self):
        # read HYPER-V
        self.HyperVPORT: int = os.environ["HYPERV_PORT"] if "HYPERV_PORT" in os.environ else self._raw_dict_data.get("HYPERV_PORT", 5985)
        self.HyperVSSL: bool = os.environ["HYPERV_SSL"] if "HYPERV_SSL" in os.environ else self._raw_dict_data.get("HYPERV_SSL", False)
        self.HyperVIP: str = os.environ["HYPERV_IP"] if "HYPERV_IP" in os.environ else self._raw_dict_data.get("HYPERV_IP", None)
        self.HyperVSMBVersion: str = os.environ["HYPERV_SMB_VERSION"] if "HYPERV_SMB_VERSION" in os.environ else self._raw_dict_data.get("HYPERV_SMB_VERSION", "3.0")
        self.HyperVUser: str = os.environ["HYPERV_USER"] if "HYPERV_USER" in os.environ else self._raw_dict_data.get("HYPERV_USER", "administrator")
        self.HyperVPass: str = os.environ["HYPERV_PASS"] if "HYPERV_PASS" in os.environ else self._raw_dict_data.get("HYPERV_PASS", None)
        self.HyperVCreateCheckPoint: bool = os.environ["HYPERV_CREATE_CHECKPOINT"] if "HYPERV_CREATE_CHECKPOINT" in os.environ else self._raw_dict_data.get("HYPERV_CREATE_CHECKPOINT", False)
        self.HuperVVMLIST = self._raw_dict_data.get("HYPER_VM_LIST", [])
        self.HyperVShareDiskMapping = [HyperVDiskMapping(item) for item in self._raw_dict_data.get("HYPERV_SHAREDISK_MAPPING", [])]
        
        self.HyperVPowerOffForce: bool = os.environ["HyperVPowerOffForce"] if "HyperVPowerOffForce" in os.environ else self._raw_dict_data.get("HyperVPowerOffForce", False)
        self.HyperVTurnOff: bool = os.environ["HyperVTurnOff"] if "HyperVTurnOff" in os.environ else self._raw_dict_data.get("HyperVTurnOff", True)
        self.HyperVNoConfirm: bool = os.environ["HyperVNoConfirm"] if "HyperVNoConfirm" in os.environ else self._raw_dict_data.get("HyperVNoConfirm", True)

        self.MigrateOvewrite: str = os.environ["MIGRATE_OVERWRITE"] if "MIGRATE_OVERWRITE" in os.environ else self._raw_dict_data.get("MIGRATE_OVERWRITE", False)

        # read Proxmox
        self.ProxmoxIP: str = os.environ["PROXMOX_IP"] if "PROXMOX_IP" in os.environ else self._raw_dict_data.get("PROXMOX_IP", None)
        self.ProxmoxUser: str = os.environ["PROXMOX_USER"] if "PROXMOX_USER" in os.environ else self._raw_dict_data.get("PROXMOX_USER", "root")
        self.ProxmoxPass: str = os.environ["PROXMOX_PASS"] if "PROXMOX_PASS" in os.environ else self._raw_dict_data.get("PROXMOX_PASS", None)
        self.ProxmoxMountPath: str = os.environ["PROXMOX_MOUNTPATH"] if "PROXMOX_MOUNTPATH" in os.environ else self._raw_dict_data.get("PROXMOX_MOUNTPATH", "/tmp")
        self.ProxmoxImportPath: str = os.environ["PROXMOX_IMPORTPATH"] if "PROXMOX_IMPORTPATH" in os.environ else self._raw_dict_data.get("PROXMOX_IMPORTPATH", "/tmp")
        self.ProxmoxStorage: str = os.environ["PROXMOX_STORAGE"] if "PROXMOX_STORAGE" in os.environ else self._raw_dict_data.get("PROXMOX_STORAGE", None)
        self.ProxmoxSwitchDefault: str = os.environ["PROXMOX_SWITCH_DEFAULT"] if "PROXMOX_SWITCH_DEFAULT" in os.environ else self._raw_dict_data.get("PROXMOX_SWITCH_DEFAULT", "vmbr0")
        self.ProxmoxSwitchMapping = self._raw_dict_data.get("PROXMOX_SWITCH_MAPPING", {})
        self.ProxmoxNetworkType: str = os.environ["PROXMOX_NETWORK_TYPE"] if "PROXMOX_NETWORK_TYPE" in os.environ else self._raw_dict_data.get("PROXMOX_NETWORK_TYPE", "e1000")
        self.ProxmoxStartAfter: bool = os.environ["PROXMOX_START_AFTER"] if "PROXMOX_START_AFTER" in os.environ else self._raw_dict_data.get("PROXMOX_START_AFTER", False)
        self.ProxmoxImportOnce: bool = os.environ["PROXMOX_IMPORT_ONCE"] if "PROXMOX_IMPORT_ONCE" in os.environ else self._raw_dict_data.get("PROXMOX_IMPORT_ONCE", False)
        #

        self.logger = ContextLogger(logging.getLogger("migrate"), self.verbose)
        self.id_migration = f"MIG-{ self._generate_random_string() }"
        self.MigrateMaxAvhdxChain: int = os.environ["Migrate_Max_Avhdx_Chain"] if "Migrate_Max_Avhdx_Chain" in os.environ else self._raw_dict_data.get("Migrate_Max_Avhdx_Chain", 2)

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

    def SetDefaultDatastore(self, datastore_name: str):
        self.ProxmoxStorage = datastore_name

    def matchPath(self, path=None) -> HyperVDiskMapping:
        if path is None:
            return self.ProxmoxStorage
        for item in self.HyperVShareDiskMapping:
            if item.hypervPath in path:
                return item.proxmoxStorage
        return self.ProxmoxStorage

    def getAllDatastore(self) -> list[str]:
        output = []
        if self.ProxmoxStorage:
            output.append(self.ProxmoxStorage)

        for item in self.HyperVShareDiskMapping:
            output.append(item.proxmoxStorage)

        return output


class Context:
    def __init__(self, config: Config, logger: ContextLogger):
        self.config: Config = config
        self.logger: ContextLogger = logger
