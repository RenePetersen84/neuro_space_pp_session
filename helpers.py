import subprocess

class CommandError(Exception):
    """
    This is the exception class used to indicate that there was an error while running a fixture.
    """
    def __init__(self, error_msg = "", returncode = None, stdout = ""):
        self.error_msg = error_msg
        self.stdout = stdout
        self.returncode = returncode
        super().__init__(self.error_msg)

def run_git_cmd(command):
    completed_process = subprocess.run("git {}".format(command), shell=True, capture_output=True, text=True)
    if (completed_process.returncode != 0):
        raise CommandError("Git failed while running '{}'".format(command))
    return completed_process.stdout

def run_sys_cmd(command):
    completed_process = subprocess.run(command, shell=True, capture_output=True, text=True)
    if (completed_process.returncode != 0):
        raise CommandError("Cmd failed while running '{}'.".format(command), completed_process.returncode, completed_process.stdout)
    return completed_process.stdout