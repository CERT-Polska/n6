# Copyright (c) 2022 NASK. All rights reserved.

# Run the `intelmqsetup` command with the `INTELMQ_ROOT_DIR`
# environment variable set to the custom value from n6 configuration.
# Add the '--skip-ownership' command-line argument to
# the `intelmqsetup` command, so it skips the process of changing
# the ownership of installed files.

# If the `INTELMQ_ROOT_DIR` is a path to a directory, to which
# the user has permissions and '--skip-ownership' argument is added,
# running of the `intelmqsetup` does not need root permissions.

import os
import sys

from n6lib.config import Config


SKIP_OWNERSHIP_ARG = '--skip-ownership'
ENV_VAR_NAME = 'INTELMQ_ROOT_DIR'
CONFIG_SPEC = '''
    [intelmq]
    intelmq_root_dir =
'''


def main():
    if SKIP_OWNERSHIP_ARG not in sys.argv:
        # add the command-line argument causing the 'intelmq'
        # setup to skip the changing of installed files ownership,
        # which requires root privileges
        sys.argv.append(SKIP_OWNERSHIP_ARG)
    config_section = Config(CONFIG_SPEC)['intelmq']
    intelmq_root_dir = config_section['intelmq_root_dir']
    if intelmq_root_dir:
        os.environ[ENV_VAR_NAME] = intelmq_root_dir
    from intelmq.bin import intelmqsetup
    intelmqsetup.main()


if __name__ == '__main__':
    main()
