from lib.Proxmox import ProxmoxClient
from lib.clogger import ContextLogger
import logging
from lib.tool import getParams
from lib.config import Config


def main(config):

    prox: ProxmoxClient = ProxmoxClient(config=config)
    vms = prox.findAllVM()

    for vm in vms:

        if "hv2pve" in prox.GetTagByVmId(vm["vmid"]):
            ticket = prox.stop(vm["vmid"])
            prox.wait_for_task(ticket, config.logger)
            prox.deleteVM(vm["vmid"])


if __name__ == "__main__":

    config = Config(args=getParams())

    main(config=config)
