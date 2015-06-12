import os
import subprocess
import sys


class UndefinedEnvironmentVariable(NameError):
    def __init__(self, var_name):
        super(NameError, self)
        self.var_name = var_name


def get_env_var(name):
    value = os.environ.get(name)

    if value is None:
        raise UndefinedEnvironmentVariable(name)

    return value


def execute_command(command):
    process = subprocess.Popen(
        command, shell=True, universal_newlines=True, stdout=subprocess.PIPE)
    process.wait()
    return process.returncode


def execute(action, success_msg, error_msg):
    try:
        action()
        print(success_msg)
    except:
        error(error_msg)


def error(msg):
    sys.stderr.write(msg + '\n')
