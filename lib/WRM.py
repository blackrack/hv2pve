import json, winrm, logging
from typing import List, TypedDict

from .HyperV import HyperVM
from .cnxLogger import ContextLogger


class Config(TypedDict):
    Name: str
    Id: str


class WRM:
    def __init__(self, username, password, hyperv_host, logger: ContextLogger):
        self.session = winrm.Session(hyperv_host, auth=(username, password), server_cert_validation="ignore")
        self.logger = logger

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

    def getVMs(self) -> List[HyperVM]:
        self.logger.log(level=logging.INFO, message="Start inventory Hyper-V ...")
        script = """Get-VM | select name,id | ConvertTo-Json"""
        wms_raw_json: List[Config] = self.runJson(script)
        self.logger.log(level=logging.INFO, message=f"Detect: {len(wms_raw_json)} vm`s")
        virtual_machines_list: List[HyperVM] = list()

        for vm_raw_json in wms_raw_json:
            vm_json_data = self.getVMByName(vm_raw_json["Name"])
            vm = HyperVM(vm_json_data[0])

            if vm.Generation == 2:
                vm.setBoot(self.getBootOrderInfo(vm_raw_json["Name"]))

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
