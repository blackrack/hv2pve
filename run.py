from lib.SSH import SSHClient
from lib.HyperV import HyperVVM, HyperVClient
from lib.Proxmox import ProxmoxClient
from lib.tool import getParams
from lib.clogger import ContextLogger
from lib.worker import RemoteWorker, DiskManager, MigrateVMMAnager
from lib.test import *
from lib.config import Config

from typing import List
import logging


# Use for mocking in pytest
def init_general_object(config):
    hyperV_client: HyperVClient = HyperVClient(config=config)
    proxmox_client: ProxmoxClient = ProxmoxClient(config=config)
    remoter: SSHClient = SSHClient(config=config)

    remote_worker: RemoteWorker = RemoteWorker(ssh=remoter, config=config)
    disk_manager: DiskManager = DiskManager(config=config, remote_worker=remote_worker, hyperV_client=hyperV_client)

    return (hyperV_client, proxmox_client, remoter, disk_manager,remote_worker)


def main(config):
    hyperV_client, proxmox_client, remoter, disk_manager,remote_worker = init_general_object(config=config)
    validTypeDatastore = True

    for datastore in config.getAllDatastore():
        type_datastore = remote_worker.DatastoreType(datastore)
        if type_datastore != "zfspool":
            validTypeDatastore = False
    command1 = f"df --output=avail -B1 {config.ProxmoxImportPath} | tail -n +2"

    size_import_dir = int(remoter.run(command=command1))
    runner = MigrationEligibilityChecker(
        rules=[IsNotInConfig(config=config),IsSize(size=size_import_dir,validTypeDatastore=validTypeDatastore), IsMigratedToProxmox(proxmoxClient=proxmox_client),  IsRunningRule(config=config), NoCheckpoints()], config=config
    )
    hyperV_virtual_machines_for_migrate: List[HyperVVM] = [vm for vm in hyperV_client.getVMs() if runner.is_eligible(vm)]

    config.logger.log(level=logging.INFO, message=f"VM ready to migrate: {len(hyperV_virtual_machines_for_migrate)} - {[vm.name for vm in hyperV_virtual_machines_for_migrate]}").back()

    if config.dry_run or not hyperV_virtual_machines_for_migrate:
        return 3

    migrate = MigrateVMMAnager(config=config, hyperV_virtual_machines=hyperV_virtual_machines_for_migrate, proxmox_client=proxmox_client, disk_manager=disk_manager)
    migrate.run()


if __name__ == "__main__":

    config = Config(args=getParams())

    if config.dry_run:
        config.logger.add("[ DRYRUN ]")
    else:
        config.logger.add(f"[ { config.id_migration } ]").add(f"[ SETUP ]")

    main(config=config)
