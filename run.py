from lib.WRM import WRM
from lib.SSHM import SSHM
from lib.HyperV import HyperVM, ControllerType
from lib.prox import Prox, ProxVM, ProxDisk, Tag, TemplateProxmoxVM, ProxNetwork
from lib.tool import macformat, generate_random_string
from lib.cnxLogger import ContextLogger
from lib.worker import ManagerWorker
import lib.EFI


from typing import List

import logging, argparse, json

LOG_LEVELS = {0: logging.NOTSET, 1: logging.INFO, 2: logging.DEBUG}

parser = argparse.ArgumentParser(
    prog="Migrate",
    description="Migrate your VM from Hyper-V to Proxmox",
    epilog="Be happy with Proxmox :D",
)

parser.add_argument("-v", "--verbose", type=int, default=0, help="Set verbosity level")
parser.add_argument("--dry-run", action="store_true", help="Perform a trial run without making any changes")

args = parser.parse_args()
DRYRUN = args.dry_run

try:
    with open("env.json", "r") as file:
        CONFIG = json.load(file)
except FileNotFoundError:
    raise ("File not exist")
except json.JSONDecodeError as e:
    raise ("Error load JSON:", e)


if args.verbose != 0:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=LOG_LEVELS[args.verbose],
        datefmt="%Y-%m-%d %H:%M:%S",
    )

context_logger = ContextLogger(logging.getLogger("migrate"))


def main():
    cache_error = None
    if DRYRUN:
        context_logger.add("[ DRYRUN ]")
    else:
        context_logger.add("[ Setup ]")

    wsman = f'http://{CONFIG["HYPERV_IP"]}:5985/wsman'
    context_logger.log(level=logging.INFO, message=f"HYPERV_IP: {CONFIG['HYPERV_IP']}")
    context_logger.log(level=logging.INFO, message=f"HYPERV_USER: {CONFIG['HYPERV_USER']}")

    cnx: WRM = WRM(
        hyperv_host=wsman,
        username=CONFIG["HYPERV_USER"],
        password=CONFIG["HYPERV_PASS"],
        logger=context_logger,
    )
    prox: Prox = Prox(
        ip=CONFIG["PROXMOX_IP"],
        user=f"{CONFIG["PROXMOX_USER"]}@pam",
        password=CONFIG["PROXMOX_PASS"],
    )
    remoter: SSHM = SSHM(
        ip=CONFIG["PROXMOX_IP"],
        username=CONFIG["PROXMOX_USER"],
        password=CONFIG["PROXMOX_PASS"],
        context_logger=context_logger,
    )

    VMS: List[HyperVM] = cnx.getVMs()
    vms_for_migrate: List[HyperVM] = []

    command = f"df --output=avail -B1 {CONFIG['PROXMOX_IMPORTPATH']} | tail -n +2"
    size_import_dir = int(remoter.run(command=command))

    context_logger.add("[ SKIP ]")
    for vm in VMS:
        if vm.State == 2:
            context_logger.log(level=logging.INFO, message=f"VM {vm.name}: state=running")
            continue
        if prox.IsExistVMByHyperVID(vm.vmid):
            context_logger.log(level=logging.INFO, message=f"VM {vm.name}: Exist on proxmox")
            continue
        if "HYPER_VM_LIST" in CONFIG and CONFIG["HYPER_VM_LIST"] and not vm.vmid in CONFIG["HYPER_VM_LIST"]:
            context_logger.log(level=logging.INFO, message=f"VM {vm.name}: ID {vm.vmid} not included in CONFIG['HYPER_VM_LIST']")
            continue
        if vm.getMaxFileSizeSingleDisk() > size_import_dir:
            context_logger.log(
                level=logging.INFO,
                message=f"VM {vm.name}: Not enough space on {CONFIG['PROXMOX_IMPORTPATH']} - {int(size_import_dir/(1_000_000_000))}G > {int(vm.getMaxFileSizeSingleDisk()/1_000_000_000)}G",
            )
            continue
        if vm.getCheckpoints():
            context_logger.log(level=logging.INFO, message=f"VM {vm.name}: Snapshot detected")
            continue
        vms_for_migrate.append(vm)
    context_logger.back()

    context_logger.log(level=logging.INFO, message=f"VM ready to migrate: {len(vms_for_migrate)}")
    context_logger.log(level=logging.INFO, message=f"VM ready to migrate: {[vm.name for vm in vms_for_migrate]}")

    if DRYRUN or not vms_for_migrate:
        return

    proxmox_default_bridge = CONFIG["PROXMOX_SWITCH_DEFAULT"]
    map_bridges = CONFIG["PROXMOX_SWITCH_MAPPING"]

    id_migration = f"MIG-{generate_random_string()}"
    context_logger.log(level=logging.INFO, message=f"ID Migracji: {id_migration}")

    migration_workdir = f"{CONFIG['PROXMOX_MOUNTPATH']}/{id_migration}"
    output = remoter.run(command=f"mkdir {migration_workdir}")
    context_logger.log(level=logging.INFO, message=f"mkdir {migration_workdir} : {output}")

    context_logger.back()

    migrate_helper: ManagerWorker = ManagerWorker(Worker=remoter, logger=context_logger)

    for vm in vms_for_migrate:
        context_logger.add(f"[{vm.name}]")

        tags: Tag = Tag()
        if "os" in vm.customAtribute:
            tags.add(vm.customAtribute["os"])
        tags.add(f"gen{vm.Generation}")

        template: TemplateProxmoxVM = TemplateProxmoxVM()

        template.set(name=vm.name, memory=vm.MemoryStartup, sockets=vm.ProcessorCount, description=f"Import from {vm.ComputerName}, id={vm.vmid} , id_migration={id_migration}")

        bridge = proxmox_default_bridge
        for lp, net in enumerate(vm.networks):
            if net.SwitchId in map_bridges:
                bridge = map_bridges[net.SwitchId]
            networkProx: ProxNetwork = ProxNetwork(typeNetCard=CONFIG["PROXMOX_NETWORK_TYPE"], bridge=bridge, macaddr=macformat(net.MacAddress))

            if net.vlanid:
                networkProx.setVlan(net.vlanid)

            template.network(slot=f"net{lp}", value=networkProx)

        if vm.Generation == 2:
            template.set(bios="ovmf")
        template.set(tags=tags)

        ticket = prox.createVM(vm_cfg=template.get())
        context_logger.log(level=logging.INFO, message=f"Wait for vm in prox")

        prox.wait_for_task(ticket, context_logger)
        proxmox_vm: ProxVM = prox.IsExistVM(vm.name)
        vmid = proxmox_vm.vmid
        context_logger.log(level=logging.INFO, message=f"VM prox ID: {vmid}")

        for lp, disk in enumerate(vm.disks):
            context_logger.add(f"[{disk.Path}]")

            proxmox_storage = CONFIG["PROXMOX_STORAGE"]
            source_mount = f"//{CONFIG['HYPERV_IP']}/{CONFIG['HYPERV_SHAREDISK']}"
            destination_mount = f"{CONFIG['PROXMOX_MOUNTPATH']}/{id_migration}"

            for map in CONFIG["HYPERV_SHAREDISK_MAPPING"]:
                if disk.Location in map:
                    source_mount = f"//{CONFIG['HYPERV_IP']}/{map[disk.Location]}"
                    proxmox_storage = map["PROXMOX_STORAGE"]

            if CONFIG["HYPERV_AUTO_SHAREDISK"]:
                share_name = id_migration
                source_mount = f"//{CONFIG['HYPERV_IP']}/{share_name}"
                cnx.NewSMB(share_name=share_name, path=disk.Location)

            try:
                options = f"username={CONFIG['HYPERV_USER']},password={CONFIG['HYPERV_PASS']},vers=3.0"

                migrate_helper.Mount(options=options, source=source_mount, destination=destination_mount, type_mount="cifs")

                source = f"{destination_mount}/{disk.FileName}"
                destination = f"{CONFIG['PROXMOX_IMPORTPATH']}/{disk.FileName}.qcow2"
                migrate_helper.Convert(source=source, destination=destination, typeDisk=disk.VhdFormat)

                disk_location = migrate_helper.Import(destination=destination, vmid=vmid, storage=proxmox_storage)

                ## Attach
                TypeDisk = "ide" if "os" in vm.customAtribute and vm.customAtribute["os"] == "windows" else "virtio"
                hdd: ProxDisk = ProxDisk(type=TypeDisk, lp=lp)
                proxmox_vm.addDisk(hdd)

                migrate_helper.AttachDisk(vmid=vmid, slot=hdd.slot(), disk=disk_location)

            except Exception as e:
                context_logger.log(level=logging.ERROR, message=e)
                cache_error = e

            finally:
                migrate_helper.Clean(file=destination)
                migrate_helper.Umount(path=destination_mount)

            if CONFIG["HYPERV_AUTO_SHAREDISK"]:
                source_mount = f"//{CONFIG['HYPERV_IP']}/{id_migration}"
                cnx.RemoveSMB(share_name=share_name)

            if cache_error:
                raise (cache_error)

            context_logger.back()

        prox.setboot(vm=proxmox_vm)

        ## EFI section:
        if vm.Generation == 2:
            lib.EFI.do(CONFIG=CONFIG, migrate_helper=migrate_helper, vmid=vmid, context_logger=context_logger)

        if CONFIG["PROXMOX_START_AFTER"]:
            prox.start(vmid)
        if CONFIG["PROXMOX_IMPORT_ONCE"]:
            return
        context_logger.back()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
