from .SSH import SSHClient
from .genericType import *
import logging, json


class RemoteWorker:

    def __init__(self, ssh: SSHClient, config):
        self.ssh = ssh
        self.logger = config.logger

    def NotCheckhd2raw(self):
        try:
            command = f"test -f /bin/hd2raw"
            output = self.ssh.run(command=command)
            self.logger.log(level=logging.DEBUG, message=f"COMMAND={command} | OUTPUT={output}")
        except:
            return True
        return False

    def NotCheckLoadNBDModule(self):
        try:
            command = f"lsmod | grep nbd"
            output = self.ssh.run(command=command)
            self.logger.log(level=logging.DEBUG, message=f"COMMAND={command} | OUTPUT={output}")
        except:
            return True
        return False

    def createNBD(self, path: str, index: int):
        command = f"qemu-nbd --connect=/dev/nbd{index}  {path}"
        output = self.ssh.run(command=command)
        self.logger.log(level=logging.INFO, message=f"COMMAND={command} | OUTPUT={output}")
        return f"/dev/nbd{index}"

    # def dd(self, path: str,connstr:str):
    #     return
    #     command = f"ssh {connstr} dd if=/dev/random of={path} bs=1M count=64 conv=fsync > /dev/null 2>&1 "
    #     output = self.ssh.run(command=command)
    #     self.logger.add("[ SHA ]").log(level=logging.DEBUG, message=f"COMMAND={command} | OUTPUT={output}").back()

    #     command = f"ssh {connstr} sha1sum {path} "
    #     output = self.ssh.run(command=command)
    #     self.logger.add("[ SHA ]").log(level=logging.INFO, message=f"{output}").back()

    def destroyNBD(self, index: int):
        command = f"qemu-nbd --disconnect /dev/nbd{index}"
        output = self.ssh.run(command=command)
        self.logger.log(level=logging.INFO, message=f"COMMAND={command} | OUTPUT={output}")
        return output

    def Diskfree(self, path: str) -> str:
        # check if folder exist
        command = f"df --output=avail -B1 {path} | tail -n +2"
        output = self.ssh.run(command=command)
        self.logger.log(level=logging.DEBUG, message=f"COMMAND={command} | OUTPUT={output}")
        return output

    def Copy(self, source: str, destination: str):
        self.ssh.copy(source=source, dest=destination)
        self.logger.log(level=logging.DEBUG, message=f"COPY: {destination}")

    def Mount(self, type_mount: MountType, options: str, source: str, destination: str):
        # check if folder exist
        command = f'[ -d "{destination}" ] || mkdir -p "{destination}"'
        output = self.ssh.run(command=command)
        self.logger.log(level=logging.DEBUG, message=f"{command} | {output}")
        command = f"mount -t {type_mount} -o {options} '{source}' {destination}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.DEBUG, message=f"Mount: {source} | {output}")

    def QemuConvert(self, source: str, destination: str, typeDisk: DiskType = DiskType.VHDX, TargetDiskType: DiskType = DiskType.RAW):
        command = "qemu-img"
        args = ["convert", "-f", typeDisk, "-O ", TargetDiskType, source, destination, "-p"]
        output = self.ssh.run(command=command, args=args)
        self.logger.log(level=logging.DEBUG, message=f"QEMU Convert Disk. Status: f{output}")
        self.logger.log(level=logging.INFO, message=f"QEMU Convert Disk. Status: Done")

    def Convert(self, source: str, destination: str):
        command = "/bin/hd2raw"
        args = [source, destination]
        output = self.ssh.run(command=command, args=args)
        self.logger.log(level=logging.DEBUG, message=f"Hd2Raw Convert Disk. Status: f{output}")
        self.logger.log(level=logging.INFO, message=f"Hd2Raw Convert Disk. Status: Done")

    def Import(self, vmid, destination, storage):
        awk = "awk '{print $5}'"
        command = f"qm importdisk {vmid} {destination} {storage} 2> /dev/null | grep 'successfully imported disk' | {awk} "
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.DEBUG, message=f"Import Disk Status: {output}")
        return output

    def AttachDisk(self, vmid, slot, disk):
        command = f"qm set {vmid} --{slot} {disk}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Attach Disk Status: {output}")

    def Clean(self, file):
        command = f"rm -rf {file}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.DEBUG, message=f"Delete TMP Disk. {file} Status: {output}")

    def CreateZFS(self, size, file):
        command = f" zfs create -V {size} {file}"
        output = self.ssh.run(command=command)

        self.logger.log(level=logging.INFO, message=f"Create ZFS: {file} Status: {output}")

    def Umount(self, path):
        output = self.ssh.run(command=f"umount {path}")
        self.logger.log(level=logging.DEBUG, message=f"Umount: {path} : {output}")

    def GetFsType(self, destination):
        awk = "awk '{print $2}'"
        command = f"lsblk -pf  {destination}  -o FSTYPE | grep -v ^$ | grep -i -v FSTYPE | sort | uniq -c | {awk} "
        output = self.ssh.run(command=command).replace("\n", ",")
        self.logger.log(level=logging.DEBUG, message=f"Detect FS: {destination} : {output}")
        return output

    def GetPartitionType(self, destination):

        command = f"fdisk -l {destination} |  grep ^/dev/ "
        output = self.ssh.run(command=command).replace("\n", ",")
        self.logger.log(level=logging.DEBUG, message=f"Detect FS: {destination} : {output}")
        return output

    def DatastoreType(self, datastore):
        command = f"pvesh get /storage/{datastore} -o json"
        output = self.ssh.run(command=command)
        data = json.loads(output)
        return data["type"]

    def DatastoreLocation(self, datastore):
        command = f"pvesh get /storage/{datastore} -o json"
        output = self.ssh.run(command=command)
        data = json.loads(output)
        if "path" in data:
            return data["path"]
        return None
