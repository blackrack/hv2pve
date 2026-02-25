from enum import StrEnum, IntEnum


class ProxmoxTagType(StrEnum):
    IMPORTED = "imported"
    HV2PVE = "hv2pve"
    INIT = "init"


class HyperVVmState(IntEnum):
    SAVED = 1
    RUNNING = 2
    STOP = 3


class DiskType(StrEnum):
    QCOW2 = "qcow2"
    RAW = "raw"
    VHDX = "vhdx"
    VHD = "vpc"


class MountType(StrEnum):
    CIFS = "cifs"
    NFS = "nfs"


class ProxmoxDatastoreType(StrEnum):
    ZFSPOOL = "zfspool"
    DIRECTORY = "dir"
    LVM = "lvm"


class FSType(StrEnum):
    NTFS = "ntfs"
    XFS = "xfs"
    SWAP = "swap"
    EXT4 = " EXT4"
    EXT3 = " EXT3"


class HddType(StrEnum):
    IDE = "ide"
    VIRTIO = "virtio"


class ControllerType(IntEnum):
    IDE = 0
    SCSI = 1
