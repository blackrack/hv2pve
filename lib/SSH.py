import paramiko, logging
from scp import SCPClient

from .clogger import ContextLogger
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

    def _connect(self) -> None:

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.config.ProxmoxIP, port=self.port, username=self.config.ProxmoxUser, password=self.config.ProxmoxPass)

    def run(self, command: str, args: List[str] = []) -> str:
        self.logger.log(level=logging.DEBUG, message=f"[COMMAND] {command} {args}")
        cmd: str = f"{command} {' '.join(args)}"
        _, stdout, stderr = self.ssh.exec_command(cmd)
        output = stdout.read().decode()
        error = stderr.read().decode()
        exit_code = stdout.channel.recv_exit_status()
        self.logger.log(level=logging.DEBUG, message=output)

        if error:
            logging.error(error)
        if exit_code > 0:
            raise Exception(f"Detect problem with command: '{command}', program return exit code: {exit_code}")

        return output.rstrip("\n")

    def copy(self, source, dest):
        with SCPClient(self.ssh.get_transport()) as scp:
            scp.put(source, dest)

    def __del__(self):
        if self.ssh:
            self.ssh.close()
