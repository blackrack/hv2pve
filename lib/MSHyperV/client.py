from typing import List
import json, winrm, logging
from lib.genericType import *
from lib.config import Config

from .virtual_machine import VirtualMachine, VirtualMachines


class Client:
    def __init__(self, config):
        self.config = config
        self.logger = config.logger

        self._connect()

    def _connect(self) -> None:
        self.logger.log(level=logging.DEBUG, message=f"HyperVIP: {self.config.HyperVIP}")
        self.logger.log(level=logging.DEBUG, message=f"HyperVUser: {self.config.HyperVUser}")
        protocol: str = "https" if self.config.HyperVSSL else "http"
        port: int = 5985
        try:
            self.session = winrm.Session(f"{protocol}://{self.config.HyperVIP}:{port}/wsman", auth=(self.config.HyperVUser, self.config.HyperVPass), server_cert_validation="ignore")
        except Exception as e:
            print(e)

    def getStatusVM(self, name):
        script = f"""get-VM -Name {name} |select Name , State , Status | ConvertTo-Json """
        self.logger.log(level=logging.DEBUG, message=f"getStatusVM: NAME:{name}  ")
        return self.runJson(script=script)[0]

    def GetSharedDisk(self):
        script = f"Get-SmbShare | ConvertTo-Json "
        share = self.runJson(script=script)
        list_letter = set()

        for item in share:
            if item["Path"] != "":
                list_letter.add(item["Path"].split(":")[0].lower())
        return list_letter

    def NewCheckPoint(self, vmid, name):
        script = f"""Checkpoint-VM -Name {vmid} -SnapshotName {name} | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"NewCheckPoint: {name}")
        return self._run(script=script)

    def RemoveCheckPoint(self, vmid, name):
        script = f"""Remove-VMCheckpoint -VMName {vmid} -Name {name} | ConvertTo-Json """
        self.logger.log(level=logging.INFO, message=f"RemoveCheckPoint: {name}")
        return self._run(script=script)

    def PowerOn(self, name):
        self.logger.log(level=logging.INFO, message=f"Start-VM")
        script = f"""Start-VM -VMName {name}"""

        return self._run(script=script)

    def PowerOffVM(self, vmid, force=True, turnoff=True, noconfirm=True):
        self.logger.log(level=logging.INFO, message=f"Stop-VM")
        script = f"""Stop-VM -VMName {vmid}"""

        if force:
            script = f"{script} -Force"

        if turnoff:
            script = f"{script} -TurnOff"

        if noconfirm:
            script = f"{script} -confirm:$false"

        return self._run(script=script)

    def WaitForPoweroff(self, vmid):
        script = f"""Get-VM -VMName {vmid} | select state | ConvertTo-Json"""
        self.logger.log(level=logging.INFO, message=f"WaitForPoweroff ...")
        return self.runJson(script=script)[0]

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

    def getVMs(self) -> List[VirtualMachine]:
        self.logger.log(level=logging.INFO, message="Start inventory Hyper-V ...")
        script = """Get-VM | select name,id | ConvertTo-Json"""
        wms_raw_json: List[Config] = self.runJson(script)
        self.logger.log(level=logging.INFO, message=f"Detect: {len(wms_raw_json)} vm`s")
        virtual_machines_list: List[VirtualMachine] = list()

        for vm_raw_json in wms_raw_json:
            vm_json_data = self.getVMByName(vm_raw_json["Name"])

            vm = VirtualMachine(raw_hyper_vm=vm_json_data[0], os=self.config.GetVMOSConfig(vm_json_data[0]["VMId"]), client=self)

            virtual_machines_list.append(vm)
        return virtual_machines_list

    def getBootOrderInfo(self, name):
        script = f"""Get-VMFirmware {name} | ConvertTo-Json"""
        return self.runJson(script)

    def getCheckPointByVmName(self, name):
        script = f"""Get-VMSnapshot -VMName {name} | ConvertTo-Json"""
        return self.runJson(script)

    def getDiskByVmName(self, name):
        pre = f"""
        
        $vm = Get-VM -Name {name} | Select-Object *
        
        """
        script = (
            pre
            + """
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
            $disks | ConvertTo-Json 
        """
        )
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
