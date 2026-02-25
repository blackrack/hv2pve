import subprocess, random, string, argparse
from .config import Config


def getParams():
    parser = argparse.ArgumentParser(
        prog="Migrate",
        description="Migrate your VM from Hyper-V do Proxmox",
        epilog="Be happy with Prox :D",
    )

    parser.add_argument("-v", "--verbose", type=int, default=0, help="Set verbosity level")
    parser.add_argument("--dry-run", action="store_true", help="Perform a trial run without making any changes")
    parser.add_argument("--config", type=str, default="env.json", help="Config location")

    return parser.parse_args()


def humanable_size(number_input) -> str:

    size = {1: "K", 2: "M", 3: "G", 4: "T"}
    number = int(number_input)
    s: int = 0
    while True:
        tmp = int(number / 1000)

        if tmp <= 0:
            return f"{number}{size[s]}"
        s = s + 1
        number = tmp


def macformat(mac) -> str:
    return ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])


def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def generate_random_string(length=10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def prep_proxmox_storage(config: Config, Location: str) -> str:

    for map in config.HyperVShareDiskMapping:
        if map.hypervPath.lower() in Location.lower():
            return map.proxmoxStorage
    return config.ProxmoxStorage


# def prep_source_mount(config:Config, Location: str) -> str:

#     # if config.HyperVAutoShareDisk:
#     #     return f"//{config.HyperVIP}/{config.id_migration}"

#     # for map in config.HyperVShareDiskMapping:
#     #     if Location == map.hypervPath:
#     #         return f"//{config.HyperVIP}/{map.hyperVSharedDisk}"
#     return f"//{config.HyperVIP}/{Location}"
