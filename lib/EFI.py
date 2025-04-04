from .worker import ManagerWorker
from .cnxLogger import ContextLogger


def do(context_logger: ContextLogger, migrate_helper: ManagerWorker, vmid, CONFIG):
    context_logger.add("[EFI]")

    efi_template = "efi-blank.qcow2"
    build_efi_for_vm = f"{vmid}-EFI.qcow2"

    ## EFI SCP
    efi_disk_location = f"{CONFIG['PROXMOX_IMPORTPATH']}/{build_efi_for_vm}"

    migrate_helper.Copy(source=efi_template, destination=efi_disk_location)

    output_disk = migrate_helper.Import(vmid=vmid, destination=efi_disk_location, storage=CONFIG["PROXMOX_STORAGE"])

    disk = f"{output_disk},efitype=4m,pre-enrolled-keys=1,size=528K"
    migrate_helper.AttachDisk(vmid=vmid, slot="efidisk0", disk=disk)

    migrate_helper.Clean(file=efi_disk_location)

    context_logger.back()
