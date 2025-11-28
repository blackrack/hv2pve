from .SSH import SSHClient
from .clogger import ContextLogger
from .Proxmox import ProxmoxHDD, TemplateProxmoxVM, ProxmoxVM, ProxmoxClient
from .HyperV import HyperVVM, HyperVClient
from .tool import prep_proxmox_storage, prep_source_mount

from typing import List
import logging
import json


class RemoteWorker:

    def __init__(self, ssh: SSHClient, config):
        self.ssh = ssh
        self.logger = config.logger

    def Copy(self, source: str, destination: str):
        self.ssh.copy(source=source, dest=destination)
        self.logger.log(level=logging.INFO, message=f"COPY: {destination}")

    def Mount(self, type_mount: str, options: str, source: str, destination: str):
        # check if folder exist
        command = f'[ -d "{destination}" ] || mkdir -p "{destination}"'
        output = self.ssh.run(command=command)
        self.logger.log(level=logging.INFO, message=f"{command} | {output}")
        command = f"mount -t {type_mount} -o {options} '{source}' {destination}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Mount: {source} | {output}")

    def Convert(self, source: str, destination: str, typeDisk: str = "vhdx", outputTypeDisk: str = "qcow2"):
        command = "qemu-img"
        args = ["convert", "-f", typeDisk, "-O ", outputTypeDisk, source, destination, "-p"]
        output = self.ssh.run(command=command, args=args)

        self.logger.log(level=logging.INFO, message=f"Convert Disk. Status: : {output}")

    def Import(self, vmid, destination, storage):
        awk = "awk '{print $5}'"
        command = f"qm importdisk {vmid} {destination} {storage} 2> /dev/null | grep 'successfully imported disk' | {awk} "
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Import Disk Status: {output}")
        return output

    def AttachDisk(self, vmid, slot, disk):
        command = f"qm set {vmid} --{slot} {disk}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Attach Disk Status: {output}")

    def Clean(self, file):
        command = f"rm -rf {file}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Delete TMP Disk. {file} Status: {output}")

    def CreateZFS(self,size, file):
        command = f" zfs create -V {size} {file}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Create ZFS: {file} Status: {output}")

    def Umount(self, path):
        output = self.ssh.run(command=f"umount {path}")
        self.logger.log(level=logging.INFO, message=f"Umount: {path} : {output}")

    def DatastoreType(self,datastore):
        command = f"pvesh get /storage/{datastore} -o json"
        output = self.ssh.run(command=command)
        data = json.loads(output)
        return data["type"]

class DiskManager:
    def __init__(self, config, remote_worker: RemoteWorker, hyperV_client):
        self.config = config
        self.remote_worker = remote_worker
        self.logger = config.logger
        self.hyperV_client = hyperV_client

    def _prep_variable_path(self):
        self.proxmox_storage = prep_proxmox_storage(self.config, self.disk.Location)
        self.proxmox_storage_type = self.remote_worker.DatastoreType(self.proxmox_storage)
        self.source_mount = prep_source_mount(self.config, self.disk.Location)
        self.destination_mount = f"{self.config.ProxmoxMountPath}/{self.config.id_migration}"
        self.options = f"username={self.config.HyperVUser},password={self.config.HyperVPass},vers=3.0"

    def migrate(self, proxmox_vm: ProxmoxVM, hyperV_vm: HyperVVM) -> bool:
        with CheckPointManager(vmid=hyperV_vm.name, hyperV_client=self.hyperV_client, id_migration=self.config.id_migration):
            for disk in hyperV_vm.disks:
                self.logger.add(f"[{disk.Path}]")

                with ShareSMBManager(hyperV_client=self.hyperV_client, name=self.config.id_migration, Path=disk.Location, create_temporary_sharedisk=self.config.HyperVAutoShareDisk):

                    self.disk = disk

                    self._prep_variable_path()

                    self.remote_worker.Mount(options=self.options, source=self.source_mount, destination=self.destination_mount, type_mount="cifs")
                    source = f"{self.destination_mount}/{disk.FileName}"
                    destination = f"{self.config.ProxmoxImportPath}/{disk.FileName}.qcow2"
                    outputTypeDisk="qcow2"
                    # FOR ZFS

                    disk_location=""
                    if self.proxmox_storage_type == "zfspool":
                        create_dataset = f"{self.proxmox_storage}/vm-{proxmox_vm.vmid}-{disk.index}"
                        size=(disk.Size/(1024*1024*1024))+1
                        self.remote_worker.CreateZFS(size=f"{size}G",file=create_dataset)
                        disk_location = f"{self.proxmox_storage}:vm-{proxmox_vm.vmid}-{disk.index}"
                        destination =f"/dev/zvol/{create_dataset}"
                        outputTypeDisk="raw"

                    self.remote_worker.Convert(source=source, destination=destination, typeDisk=disk.VhdFormat,outputTypeDisk=outputTypeDisk)

                    # Not ZFS
                    if self.proxmox_storage_type != "zfspool":
                        disk_location = self.remote_worker.Import(destination=destination, vmid=proxmox_vm.vmid, storage=self.proxmox_storage)
                        self.remote_worker.Clean(file=destination)

                    hdd: ProxmoxHDD = ProxmoxHDD(disk=disk)
                    proxmox_vm.addDisk(hdd)

                    self.remote_worker.AttachDisk(vmid=proxmox_vm.vmid, slot=hdd.slot(), disk=disk_location)

                    self.remote_worker.Umount(path=self.destination_mount)

                    self.logger.back()

        # EFI if gen2
        ## EFI section:
        if hyperV_vm.Generation == 2:
            self.logger.add("[EFI]")

            efi_template = "efi-blank.qcow2"
            build_efi_for_vm = f"{proxmox_vm.vmid}-EFI.qcow2"

            ## EFI SCP
            efi_disk_location = f"{self.config.ProxmoxImportPath}/{build_efi_for_vm}"

            self.remote_worker.Copy(source=efi_template, destination=efi_disk_location)

            output_disk = self.remote_worker.Import(vmid=proxmox_vm.vmid, destination=efi_disk_location, storage=self.config.ProxmoxStorage)

            disk = f"{output_disk},efitype=4m,pre-enrolled-keys=1,size=528K"
            self.remote_worker.AttachDisk(vmid=proxmox_vm.vmid, slot="efidisk0", disk=disk)

            self.remote_worker.Clean(file=efi_disk_location)

            self.logger.back()


class MigrateVMMAnager:
    def __init__(self, hyperV_virtual_machines: List[HyperVVM], config, proxmox_client: ProxmoxClient, disk_manager: DiskManager):
        self.hyperV_virtual_machines = hyperV_virtual_machines
        self.logger = config.logger
        self.config = config
        self.proxmox_client = proxmox_client
        self.disk_manager = disk_manager

    def run(self):
        for hyperV_vm in self.hyperV_virtual_machines:
            self._run(hyperV_vm=hyperV_vm)

    def _run(self, hyperV_vm: HyperVVM):
        self.logger.add(f"[ {hyperV_vm.name} ]")

        template: TemplateProxmoxVM = TemplateProxmoxVM(hyper_vm=hyperV_vm, config=self.config)
        template.add_Tag(self.config.id_migration)

        ticket = self.proxmox_client.createVM(vm_cfg=template.get())
        self.proxmox_client.wait_for_task(ticket=ticket, logger=self.logger)
        proxmox_vm: ProxmoxVM = self.proxmox_client.IsExistVM(name=hyperV_vm.name)

        self.logger.log(level=logging.INFO, message=f"VM prox ID: {proxmox_vm.vmid}")
        # with DiskManager() as manager:
        #     manager.Mount()
        #     manager.Convert()
        #     manager.Import()

        self.disk_manager.migrate(proxmox_vm=proxmox_vm, hyperV_vm=hyperV_vm)

        self.proxmox_client.setboot(vm=proxmox_vm)

        if self.config.ProxmoxStartAfter:
            self.proxmox_client.start(proxmox_vm.vmid)
        if self.config.ProxmoxImportOnce:
            return 4

        self.logger.back()


class CheckPointManager:
    def __init__(self, hyperV_client: HyperVClient, vmid: str, id_migration: str):
        self.hyperV_client = hyperV_client
        self.vmid = vmid
        self.id_migration = id_migration

    def __enter__(self):
        self.hyperV_client.NewCheckPoint(vmid=self.vmid, name=self.id_migration)

    def __exit__(self, type, value, traceback):
        self.hyperV_client.RemoveCheckPoint(vmid=self.vmid, name=self.id_migration)


class ShareSMBManager:
    def __init__(self, hyperV_client: HyperVClient, name: str, Path: str, create_temporary_sharedisk: bool):
        self.hyperV_client = hyperV_client
        self.name = name
        self.path = Path
        self.create_temporary_sharedisk = create_temporary_sharedisk

    def __enter__(self):
        if self.create_temporary_sharedisk:
            self.hyperV_client.NewSMB(share_name=self.name, path=self.path)

    def __exit__(self, type, value, traceback):
        if self.create_temporary_sharedisk:
            self.hyperV_client.RemoveSMB(share_name=self.name)
