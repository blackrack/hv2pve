import subprocess, random, string


def macformat(mac) -> str:
    return ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])


def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def generate_random_string(length=10):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))
