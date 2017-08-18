#!/usr/bin/env python3
from __future__ import print_function
import datetime
import errno
import logging
import os
import pwd
import re
import shutil
import subprocess
import sys
import time

if False:
    from typing import Sequence, Text, Any

DEPLOYMENTS_DIR = "/home/zulip/deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = '%Y-%m-%d-%H-%M-%S'

# Color codes
OKBLUE = '\033[94m'
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BLACKONYELLOW = '\x1b[0;30;43m'
WHITEONRED = '\x1b[0;37;41m'
BOLDRED = '\x1B[1;31m'

GREEN = '\x1b[32m'
YELLOW = '\x1b[33m'
BLUE = '\x1b[34m'
MAGENTA = '\x1b[35m'
CYAN = '\x1b[36m'

def get_deployment_version(extract_path):
    # type: (str) -> str
    version = '0.0.0'
    for item in os.listdir(extract_path):
        item_path = os.path.join(extract_path, item)
        if item.startswith('zulip-server') and os.path.isdir(item_path):
            with open(os.path.join(item_path, 'version.py')) as f:
                result = re.search('ZULIP_VERSION = "(.*)"', f.read())
                if result:
                    version = result.groups()[0]
            break
    return version

def is_invalid_upgrade(current_version, new_version):
    # type: (str, str) -> bool
    if new_version > '1.4.3' and current_version <= '1.3.10':
        return True
    return False

def subprocess_text_output(args):
    # type: (Sequence[str]) -> str
    return subprocess.check_output(args, universal_newlines=True).strip()

def su_to_zulip():
    # type: () -> None
    pwent = pwd.getpwnam("zulip")
    os.setgid(pwent.pw_gid)
    os.setuid(pwent.pw_uid)
    os.environ['HOME'] = os.path.abspath(os.path.join(DEPLOYMENTS_DIR, '..'))

def make_deploy_path():
    # type: () -> str
    timestamp = datetime.datetime.now().strftime(TIMESTAMP_FORMAT)
    return os.path.join(DEPLOYMENTS_DIR, timestamp)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make_deploy_path':
        print(make_deploy_path())

def mkdir_p(path):
    # type: (str) -> None
    # Python doesn't have an analog to `mkdir -p` < Python 3.2.
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_deployment_lock(error_rerun_script):
    # type: (str) -> None
    start_time = time.time()
    got_lock = False
    while time.time() - start_time < 300:
        try:
            os.mkdir(LOCK_DIR)
            got_lock = True
            break
        except OSError:
            print(WARNING + "Another deployment in progress; waiting for lock... " +
                  "(If no deployment is running, rmdir %s)" % (LOCK_DIR,) + ENDC)
            sys.stdout.flush()
            time.sleep(3)

    if not got_lock:
        print(FAIL + "Deployment already in progress.  Please run\n" +
              "  %s\n" % (error_rerun_script,) +
              "manually when the previous deployment finishes, or run\n" +
              "  rmdir %s\n"  % (LOCK_DIR,) +
              "if the previous deployment crashed." +
              ENDC)
        sys.exit(1)

def release_deployment_lock():
    # type: () -> None
    shutil.rmtree(LOCK_DIR)

def run(args, **kwargs):
    # type: (Sequence[str], **Any) -> None
    # Output what we're doing in the `set -x` style
    print("+ %s" % (" ".join(args)))

    if kwargs.get('shell'):
        # With shell=True we can only pass string to Popen
        args = " ".join(args)

    try:
        subprocess.check_call(args, **kwargs)
    except subprocess.CalledProcessError:
        print()
        print(WHITEONRED + "Error running a subcommand of %s: %s" % (sys.argv[0], " ".join(args)) +
              ENDC)
        print(WHITEONRED + "Actual error output for the subcommand is just above this." +
              ENDC)
        print()
        raise

def log_management_command(cmd, log_path):
    # type: (Text, Text) -> None
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter("%(asctime)s: %(message)s")
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger = logging.getLogger("zulip.management")
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

    logger.info("Ran '%s'" % (cmd,))
