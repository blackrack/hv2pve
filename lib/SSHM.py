import paramiko, logging
from scp import SCPClient
from abc import ABC, abstractmethod
from .cnxLogger import ContextLogger


class Worker(ABC):
    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def copy(self):
        pass


class SSHM(Worker):
    def __init__(self, ip, username, password, context_logger: ContextLogger, port=22, log=logging.CRITICAL):
        paramiko_logger = logging.getLogger("paramiko")
        paramiko_logger.setLevel(log)

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(ip, port=port, username=username, password=password)
        self.logger = context_logger

    def run(self, command: str, args: str = "") -> str:
        self.logger.log(level=logging.DEBUG, message=f"[COMMAND] {command} {args}")
        cmd: str = f"{command} {args}"
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
        self.ssh.close()


class LocalWorker(Worker):
    def __init__(self):
        pass
