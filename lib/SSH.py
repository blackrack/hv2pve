import paramiko, logging
from scp import SCPClient
from typing import List


class SSHClient:
    def __init__(self, config, port=22, log=logging.CRITICAL):
        paramiko_logger = logging.getLogger("paramiko")
        paramiko_logger.setLevel(log)

        self.config = config
        self.logger = config.logger
        self.port = port
        self.log = log
        self.ssh = None

        self._connect()
        self.counter: int = 0

    def _connect(self) -> None:

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.config.ProxmoxIP, port=self.port, username=self.config.ProxmoxUser, password=self.config.ProxmoxPass)

    def run(self, command: str, args: List[str] = []) -> str:
        self.counter = self.counter + 1
        self.logger.add(f"[ { self.counter } ]")

        self.logger.log(level=logging.DEBUG, message=f"[COMMAND] {command} {args}")

        cmd: str = f"{command} {' '.join(args)}"
        _, stdout, stderr = self.ssh.exec_command(cmd)
        output = stdout.read().decode().rstrip("\n")
        error = stderr.read().decode()
        exit_code = stdout.channel.recv_exit_status()
        self.logger.log(level=logging.DEBUG, message=f"[OUTPUT] {output}")
        self.logger.log(level=logging.DEBUG, message=f"[EXIT CODE] {exit_code}")
        self.logger.back()

        if error:
            logging.error(error)
        if exit_code > 0:
            raise Exception(f"Detect problem with command: '{command}', program return exit code: {exit_code}")

        return output

    def copy(self, source, dest):
        with SCPClient(self.ssh.get_transport()) as scp:
            scp.put(source, dest)

    def __del__(self):
        if self.ssh:
            self.ssh.close()
