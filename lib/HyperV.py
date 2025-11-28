from typing import List, Dict
from enum import Enum
from typing import List, TypedDict
from .clogger import ContextLogger

import json, winrm, logging


class Config(TypedDict):
    Name: str
    Id: str


class ControllerType(Enum):
    IDE = 0
    SCSI = 1


class HyperVHDD:
    def __init__(self, disk, index: int, type_disk: str):
        self.ControllerType: ControllerType = int(disk["ControllerType"])
        self.Path: str = disk["Path"]
        self.FileName: str = disk["Path"].split("\\")[-1]
        self.Location: str = "/".join(disk["Path"].split("\\")[:-1])
        self.index: int = index
        self.VhdFormat = "vpc" if disk["VhdFormat"] == 2 else "vhdx"
        self.Size = disk["Size"]
        self.FileSize = disk["FileSize"]
        self.type_disk = type_disk


class HyperVNetwork:
    def __init__(self, network, index: int):
        self.MacAddress = network["MacAddress"]
        self.SwitchId = network["SwitchId"]
        self.index: int = index
        self.vlanid = network["VLANID"]


class HyperVVM:

    def IsRunning(self):
        return self.State

    def getCheckpoints(self):
        return self.checkpoints

    def getTotalDiskSize(self):
        totalsize = 0
        for disk in self.disks:
            totalsize += disk.Size
        return totalsize

    def getMaxFileSizeSingleDisk(self):
        size = 0

        for disk in self.disks:
            if disk.FileSize > size:
                size = disk.FileSize
        return size

    def setBoot(self, data):
        tmp = data[0]["BootOrder"]
        for id, item in enumerate(tmp):
            if item["BootType"] == 3:
                self.efi = item["FirmwarePath"]

    def __init__(self, vm, os: str = "Unknown"):
        self.os = os
        self.ComputerName = vm["ComputerName"]
        self.name = vm["VMName"]
        self.Generation = vm["Generation"]
        self.MemoryMaximum = int(vm["MemoryMaximum"] / (1024 * 1024))
        self.MemoryMinimum = int(vm["MemoryMinimum"] / (1024 * 1024))
        self.MemoryStartup = int(vm["MemoryStartup"] / (1024 * 1024))
        self.ProcessorCount = vm["ProcessorCount"]
        self.vmid = vm["VMId"]
        self.State = vm["State"]
        self.checkpoints = vm["CheckPoints"]
        _typeDisk = "ide" if os == "windows" else "virtio"

        self.disks: List[HyperVHDD] = [HyperVHDD(disk=disk, index=index, type_disk=_typeDisk) for index, disk in enumerate(vm["HardDrives"])]
        self.networks: List[HyperVNetwork] = [HyperVNetwork(network=network, index=index) for index, network in enumerate(vm["NetworkAdapters"])]

    def __str__(self):
        return f"[ID]: {self.vmid} | [GEN]: {self.Generation} | [HDD]:{ len(self.disks)} | [NET]:{ len(self.networks)} | [VM]: {self.name}"


class HyperVClient:
    def __init__(self, config):
        self.config = config
        self.logger = config.logger

        self._connect()

    def _connect(self) -> None:
        self.logger.log(level=logging.INFO, message=f"HyperVIP: {self.config.HyperVIP}")
        self.logger.log(level=logging.INFO, message=f"HyperVUser: {self.config.HyperVUser}")
        try:
            self.session = winrm.Session(f"http://{self.config.HyperVIP}:5985/wsman", auth=(self.config.HyperVUser, self.config.HyperVPass), server_cert_validation="ignore")
        except Exception as e:
            print(e)

    def NewCheckPoint(self, vmid, name):
        script = f"""Checkpoint-VM -Name {vmid} -SnapshotName {name} | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"NewCheckPoint: NAME:{vmid} ")
        return self._run(script=script)

    def RemoveCheckPoint(self, vmid, name):
        script = f"""Remove-VMCheckpoint -VMName {vmid} -Name {name} | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"RemoveCheckPoint: NAME:{vmid} ")
        return self._run(script=script)

    def NewSMB(self, share_name, path):
        script = f"""New-SmbShare -Name "{share_name}" -Path "{path}" -FullAccess "Administrators" | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"NEWSMB: NAME:{share_name} PATH:{path}")
        return self._run(script=script)

    def RemoveSMB(self, share_name):
        script = f"""Remove-SmbShare -Name "{share_name}" -Force | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"Remove SMB {share_name}")
        return self._run(script=script)

    def _run(self, script):
        result = self.session.run_ps(script)
        self.logger.log(level=logging.DEBUG, message=f"Powershell: script: {script}")
        output = result.std_out.decode()
        self.logger.log(level=logging.DEBUG, message=f"Powershell: output: {output}")
        return output

    def runJson(self, script) -> List:
        json_raw = self._run(script=script)
        if not json_raw:
            return []
        output = json.loads(json_raw)
        if isinstance(output, list):
            return output
        return [output]

    def getVMs(self) -> List[HyperVVM]:
        self.logger.log(level=logging.INFO, message="Start inventory Hyper-V ...")
        script = """Get-VM | select name,id | ConvertTo-Json"""
        wms_raw_json: List[Config] = self.runJson(script)
        self.logger.log(level=logging.INFO, message=f"Detect: {len(wms_raw_json)} vm`s")
        virtual_machines_list: List[HyperVVM] = list()

        for vm_raw_json in wms_raw_json:
            vm_json_data = self.getVMByName(vm_raw_json["Name"])

            vm = HyperVVM(vm=vm_json_data[0], os=self.config.GetVMOSConfig(vm_json_data[0]["VMId"]))

            virtual_machines_list.append(vm)
        return virtual_machines_list

    def getBootOrderInfo(self, name):
        script = f"""Get-VMFirmware {name} | ConvertTo-Json"""

        return self.runJson(script)

    def getVMByName(self, name):
        pre = f"$vm = Get-VM -Name {name}"
        script = (
            pre
            + """ | Select-Object *
            $disks = @($vm.HardDrives | ForEach-Object {
                $vhd = Get-VHD -Path $_.Path
                [PSCustomObject]@{
                    Path          = $_.Path
                    VhdFormat        = $vhd.VhdFormat
                    Size             = $vhd.Size
                    FileSize             = $vhd.FileSize
                    IsFixed          = $vhd.IsFixed
                    Attached         = $vhd.Attached
                    ParentPath       = $vhd.ParentPath
                    ControllerType   = $_.ControllerType
                    ControllerNumber = $_.ControllerNumber
                    ControllerLocation = $_.ControllerLocation
                }
            })

            $checkPoints =@(Get-VMSnapshot -VMName $vm.Name )

            $networks = @(Get-VMNetworkAdapter -VMName $vm.Name | ForEach-Object {
                [PSCustomObject]@{
                    AdapterName  = $_.Name
                    SwitchName   = $_.SwitchName
                    SwitchId     = $_.SwitchId
                    MacAddress   = $_.MacAddress
                    VLANID       = $_.VlanSetting.AccessVlanId

                }
            })

            $vm | Add-Member -MemberType NoteProperty -Name "HardDrives" -Value $disks -Force
            $vm | Add-Member -MemberType NoteProperty -Name "NetworkAdapters" -Value $networks -Force
            $vm | Add-Member -MemberType NoteProperty -Name "CheckPoints" -Value $checkPoints -Force

            # Konwersja do JSON
            $vm | ConvertTo-Json 

        """
        )
        return self.runJson(script)
