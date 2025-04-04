from .SSHM import Worker
from .cnxLogger import ContextLogger
import logging


class ManagerWorker:
    def __init__(self, Worker: Worker, logger: ContextLogger):
        self.worker = Worker
        self.logger = logger

    def Copy(self, source: str, destination: str):
        self.worker.copy(source=source, dest=destination)
        self.logger.log(level=logging.INFO, message=f"COPY: {destination}")

    def Mount(self, type_mount: str, options: str, source: str, destination: str):
        command = f"mount -t {type_mount} -o {options} '{source}' {destination}"
        output = self.worker.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Mount: {source} | {output}")

    def Convert(self, source: str, destination: str, typeDisk: str = "vhdx"):
        command = f"qemu-img convert -f {typeDisk} -O qcow2 {source} {destination}"
        output = self.worker.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Convert Disk. Status: : {output}")

    def Import(self, vmid, destination, storage):
        awk = "awk '{print $5}'"
        command = f"qm importdisk {vmid} {destination} {storage} 2> /dev/null | grep 'successfully imported disk' | {awk} "
        output = self.worker.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Import Disk Status: {output}")
        return output

    def AttachDisk(self, vmid, slot, disk):
        command = f"qm set {vmid} --{slot} {disk}"
        output = self.worker.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Attach Disk Status: {output}")

    def Clean(self, file):
        command = f"rm -rf {file}"
        output = self.worker.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Delete TMP Disk. {file} Status: {output}")

    def Umount(self, path):
        output = self.worker.run(command=f"umount {path}")
        self.logger.log(level=logging.INFO, message=f"Umount: {path} : {output}")
