from lib.SSH import SSHClient
from lib import MSHyperV
from lib.Proxmox import ProxmoxClient
from lib.tool import getParams
from lib.MigrateManager import MigrateManager
from lib.DiskManager import DiskManager
from lib.RemoteWorker import RemoteWorker
from lib.TestRule import *
from lib.config import Config
from typing import List
import logging


# Use for mocking in pytest
def init_general_object(config: Config):
    hyperV_client: MSHyperV.Client = MSHyperV.Client(config=config)
    proxmox_client: ProxmoxClient = ProxmoxClient(config=config)
    ssh_client: SSHClient = SSHClient(config=config)
    remote_worker: RemoteWorker = RemoteWorker(ssh=ssh_client, config=config)
    disk_manager: DiskManager = DiskManager(config=config, remote_worker=remote_worker, hyperV_client=hyperV_client)

    check_default_settings(config, proxmox_client)
    check_required(config, remote_worker)

    return (hyperV_client, proxmox_client, disk_manager, remote_worker)


def check_default_settings(config, proxmox_client):
    # Check Default Storage
    if not config.matchPath():
        avail: int = 0
        datastore_default: str = None
        for datastore in proxmox_client.getDatastores():
            if datastore.avail > avail:
                avail = datastore.avail
                datastore_default = datastore.storage
        config.SetDefaultDatastore(datastore_default)
    # DOTO check ...


def check_required(config, remote_worker):

    if config.HyperVCreateCheckPoint:

        if remote_worker.NotCheckhd2raw():
            config.logger.clean("[ REQUIRED ]").log(level=logging.INFO, message=f"AVHDX Migrate Chain requires /bin/vhdx (see Section 2 in README).")
            return

        if remote_worker.NotCheckLoadNBDModule():
            config.logger.clean("[ REQUIRED ]").log(level=logging.INFO, message=f"AVHDX Migrate Chain requires the NBD module (see Section 2 in README).")
            return


def main(config: Config):
    hyperV_client, proxmox_client, disk_manager, remote_worker = init_general_object(config=config)

    runner = MigrationEligibilityChecker(
        rules=[
            CheckImportedStatus(proxmoxClient=proxmox_client, config=config),
            CheckSnapshot(),
            CheckConfig(config=config),
            CheckStatusMigrated(proxmoxClient=proxmox_client, config=config),
            CheckVMCheckpointType(config=config),
            CheckSize(config=config, remote_worker=remote_worker, proxmox_client=proxmox_client),
            CheckVMState(config=config),
        ],
        config=config,
    )

    hyperV_virtual_machines_for_migrate: List[MSHyperV.VirtualMachine] = [vm for vm in hyperV_client.getVMs() if runner.is_eligible(vm)]

    config.logger.log(level=logging.INFO, message=f"VM ready to migrate: {len(hyperV_virtual_machines_for_migrate)} - {[vm.name for vm in hyperV_virtual_machines_for_migrate]}").back()

    if config.dry_run or not hyperV_virtual_machines_for_migrate:
        return 3

    migrate = MigrateManager(
        config=config, remote_worker=remote_worker, hyperV_virtual_machines=hyperV_virtual_machines_for_migrate, proxmox_client=proxmox_client, disk_manager=disk_manager, hyperV_client=hyperV_client
    )
    migrate.run()


if __name__ == "__main__":

    config = Config(args=getParams())

    if config.dry_run:
        config.logger.add("[ DRYRUN ]")
    else:
        config.logger.add(f"[ { config.id_migration } ]").add(f"[ SETUP ]")

    main(config=config)
