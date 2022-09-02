# Copyright (c) 2021 NASK. All rights reserved.
#
# The script should be run in the environment (virtual env or global
# environment) with installed 'intelmq' and 'intelmq-webinput-csv'
# packages. Patches applied by the script cause 'intelmq-webinput-csv'
# to work with 'intelmq' newer than version 2.3.3. They also allow
# performing SSL connection to RabbitMQ pipeline.
#
# After applying the patch, 'intelmq-webinput-csv' can work with
# version 2.3.3 of 'intelmq', as well as with versions 3.x.
# The 'pika' library can be installed in versions: 0.13.1 and >= 1.x.

import argparse
import os.path
import shutil
import sys
try:
    import intelmq_webinput_csv
except ImportError:
    package_available = False
else:
    package_available = True


TARGET_FILENAME = '__init__.py'
script_dir = os.path.dirname(os.path.realpath(__file__))
patch_file_path = os.path.join(script_dir, 'patches', 'intelmq_init_patch')
# the `__path__` attribute contains a list of paths and in some
# circumstances the same path is duplicated
package_paths = set(intelmq_webinput_csv.__path__) if package_available else None


def get_parsed_args():
    parser = argparse.ArgumentParser(description="Patch the 'intelmq-webinput-csv' library, "
                                                 "so it can be used with 'intelmq' >= 3.0.0 "
                                                 "and to connect to AMQP broker using SSL",
                                     epilog="Example locations of the library: "
                                            "'/usr/local/lib/python2.7/dist-packages/"
                                            "intelmq_webinput_csv' - if installed globally,"
                                            "'/home/user/virtual_env/lib/python3.9/site-packages/"
                                            "intelmq_webinput_csv' - if installed in virtual "
                                            "environment.")
    parser.add_argument('-p', '--path',
                        help="Manually selected path to the 'intelmq-webinput-csv' library")
    return parser.parse_args()


def is_file_empty(file_path: str) -> bool:
    if os.path.isdir(file_path):
        raise IsADirectoryError
    return not bool(os.path.getsize(file_path))


def do_patching(file_path: str) -> tuple[bool, str]:
    msg = None
    try:
        if not is_file_empty(file_path):
            return False, (f'File {file_path!a} has not been patched, it is not empty. '
                           f'Check its content')
    except FileNotFoundError:
        msg = (f'File {file_path!a} has not existed before. '
               f'Check the path to see if patching has succeeded')
    except IsADirectoryError:
        return False, (f'File {file_path!a} exists but is a directory. '
                       f'Patching could not be performed')
    try:
        shutil.copy(patch_file_path, file_path)
    except Exception as exc:
        return False, f'File {file_path!a} could not be patched: {exc}'
    return True, msg


def main() -> None:
    args = get_parsed_args()
    manual_path = args.path
    global package_paths
    if package_paths is None and manual_path is None:
        raise RuntimeError("Could not establish a path to the 'intelmq' library. If it is not "
                           "installed in current environment, choose the path manually by "
                           "passing it as a '--path' argument")
    if manual_path is not None:
        package_paths = {manual_path}
    for package_path in package_paths:
        file_path = os.path.join(package_path, TARGET_FILENAME)
        result, msg = do_patching(file_path)
        if result:
            print(msg or f'File {file_path!a} has been successfully patched')
        else:
            sys.exit(msg)


if __name__ == '__main__':
    main()
