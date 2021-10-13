# Copyright (c) 2020 NASK. All rights reserved.

import argparse
import sys

import os.path as osp

from n6lib.data_spec.fields import (
    FieldValueError,
    SourceField,
)

CONF_PATTERN = """
[program:{prog}]
command={command}              ;  the program (relative uses PATH, can take args)
process_name=%(program_name)s  ;  process_name expr (default %(program_name)s)
numprocs=1                     ;  number of processes copies to start (def 1)

autorestart=unexpected         ;  whether/when to restart (default: unexpected)
startsecs=1                    ;  number of secs prog must stay running (def. 1)
startretries=3                 ;  max # of serial start failures (default 3)
exitcodes=0                    ;  'expected' exit codes for process (default 0)
stopsignal=INT                 ;  signal used to kill process (default TERM)
stopwaitsecs=10                ;  max num secs to wait b4 SIGKILL (default 10)
stopasgroup=false              ;  send stop signal to the UNIX process group (default false)
killasgroup=false              ;  SIGKILL the UNIX process group (def false)

environment=HOME="/home/dataman" 
"""


def _print(msg, file=None):
    if file is None:
        file = sys.stdout
    file.write(msg+"\n")


def print_err(msg, *args, **kwargs):
    file = kwargs.pop('file', sys.stderr)
    formatted = "[{}] ERROR: {}".format(
        sys.argv[0], msg.format(*args, **kwargs))
    _print(formatted, file)


def print_msg(msg, *args, **kwargs):
    _print("[{}] {}".format(
        sys.argv[0], msg.format(*args, **kwargs)))


class RecorderConfigGenerationError(Exception):
    """
    General purpose exception to signal error
    during recorder supervisors' config generation.

    If the `RecorderConfigGenerator` would be called
    from other code raising this exception instead
    of quitting on error allows caller to recover.
    """
    def __init__(self, msg):
        super(RecorderConfigGenerationError, self).__init__()
        self.exit_msg = msg


class RecorderConfigGenerator(object):
    """
    Generates supervisor configuration files
    for the recorders run with flag `--n6recorder-blacklist`
    or `--n6recorder-non-blacklist`.

    Sources to generate the configuration for will
    be read from the path passed under the `source_file_path`.
    File under this path should contain each source in a separate
    line in format `source_label.source_channel`.
    Sources file can contain blank lines and/or comments
    starting with a '#' character.
    Example:

        # important sources
        source_l1.channel1
        important.important_channel

        # rest of the sources
        some_s.rest_channel

    Most of the implementation is transactional.
    What it means is that if an error occurs then no change
    is made to the outside environment. Exception to that
    is writing configuration to files.
    If some error occurs during this phase then the already
    written files will not be reverted to the state before.

    To generate configuration files call mwthod `gen_and_write_source_conf()`.
    To generate non-blacklist configuration file call method `gen_and_write_non_bl_conf()`.
    """

    N6RECORDER_BL_CONF_NAME_PATT = "n6recorder_bl_{}"
    N6RECORDER_NON_BL_CONF_BAME = "n6recorder_non_blacklist"

    def __init__(self, source_file_path, dest_path, overwrite=False, skip_errors=True):
        """
        Initializes `RecorderConfigGenerator` instance.

        Args/kwargs:
            `source_file_path`:
                *Path to the file* containing sources to generate
                the configurations for.
            `dest_path`:
                *Path to the directory* where the
                configuration files will be generated to.
            `overwrite`:
                Should the content of the configuration files
                be overwritten if the files already exists.
                If this flag is not set and any of the files exist
                then exception will be risen without any changes
                being made to the outside environment.
                Defaults to `False`.
            `skip_errors`:
                By default `RecorderConfigGenerator` halts on every
                error. This flag changes this behavior so that
                not all errors result in exception being thrown.
                Instead the execution proceeds as if the error never
                occured and a cause of the error is ignored.
                If this flag is set then the following
                errors will be skipped:
                    - wrong source format in the sources file,
                    - configuration file already exists and overwriting flag is not set.

        Raises:
            `RecorderConfigGenerationError`:
                If `source_file_path` is not an existing file or
                `dest_path` is not an existing directory.
        """
        super(RecorderConfigGenerator, self).__init__()
        self.source_file_path = source_file_path
        self.dest_path = dest_path
        self.overwrite = overwrite
        self.skip_errors = skip_errors
        self._check_source_path()
        self._check_dest_path()

    def _check_source_path(self):
        if not osp.isfile(self.source_file_path):
            raise RecorderConfigGenerationError(
                "source file '{}' does not exist or is not a file".format(
                    self.source_file_path))

    def _check_dest_path(self):
        if not osp.isdir(self.dest_path):
            raise RecorderConfigGenerationError(
                "destination path '{}' does not exist or is not a directory".format(
                    self.dest_path))

    # static helper functions

    @staticmethod
    def generate_bl_recorder_conf(source):
        """
        Creates a configuration for the blacklist recorder
        for the passed source.

        Returns:
            Created configuration as `str`.
        """
        prog_fmt = RecorderConfigGenerator.N6RECORDER_BL_CONF_NAME_PATT
        return CONF_PATTERN.format(
            prog=prog_fmt.format(source.replace(".", "_")),
            command="n6recorder --n6recorder-blacklist {}".format(source))

    @staticmethod
    def generate_non_bl_recorder_conf():
        """
        Creates a configuration for the non-blacklist
        recorder.

        Returns:
            Created configuration as `str`.
        """
        return CONF_PATTERN.format(
            prog=RecorderConfigGenerator.N6RECORDER_NON_BL_CONF_BAME,
            command="n6recorder --n6recorder-non-blacklist")

    @staticmethod
    def file_name_from_source(source):
        """
        Creates a filename for the configuration file
        from the given source.

        Returns:
            Created filename as `str`.
        """
        name_patt = RecorderConfigGenerator.N6RECORDER_BL_CONF_NAME_PATT
        name_patt += ".conf"
        return name_patt.format(source.replace(".", "_"))

    # logic implementation

    def get_source_configurations(self):
        """
        Create a dictionary mapping source from the
        sources file to the configuration generated for
        this source.

        Returns:
            Created dictionary.

        Raises:
            `RecorderConfigGenerationError`:
                If the `skip_errors` flag is set to `False`
                and some source in the file has a wrong format.
        """
        configs = {}
        errors = []
        with open(self.source_file_path) as src:
            for line, source in enumerate(src.readlines(), start=1):
                source = source.rstrip()
                if not source or self._is_comment(source):
                    continue
                try:
                    source = SourceField().clean_result_value(source)
                except FieldValueError as e:
                    err_msg = "({}:{}) {}".format(self.source_file_path, line, e)
                    if self.skip_errors:
                        print_msg("skipping error: {}".format(err_msg))
                        continue
                    errors.append(err_msg)
                    continue
                configs[source] = self.generate_bl_recorder_conf(source)
        if errors:
            for err in errors:
                print_err(err)
            raise RecorderConfigGenerationError(
                "there were errors during config generation")
        return configs

    def _is_comment(self, source):
        return source.startswith('#')

    def _check_config_files(self, configs):
        """
        This method checks if the path in the `configs`
        dictionary exists. If so 3 things can be done:
            - if `skip_errors` and `overwrite` flags are `False`
              then an exception will be raised.
            - if `skip_errors` is `True` and `overwrite` is `False`
              then the path will be removed from the dictionary.
              So that later no writes to it happen.
            - if `overwrite` is `True` then nothing is done
              and later the content of the file will be overwritten
              with newly generated configuration.

        Args:
            `configs`:
                A dictionary mapping paths to the sources'
                configuration files with configurations generated
                for the sources.

        Raises:
            `RecorderConfigGenerationError`:
                If the `skip_errors` and `overwrite` flags are set to `False`
                and one of the paths already exists.
        """
        confs_to_del = []
        errors = []
        for conf_name in configs:
            conf_path = osp.join(self.dest_path, conf_name)
            if osp.exists(conf_path):
                if not self.overwrite:
                    err_msg = (
                        "config file '{}' already exists "
                        "and overwritting was not allowed "
                        "(use --overwrite if you want it "
                        "to be overwritten)").format(conf_path)
                    if self.skip_errors:
                        print_msg("skipping error: {}".format(err_msg))
                        confs_to_del.append(conf_name)
                        continue
                    errors.append(err_msg)
                else:
                    print_msg("config file '{}' will be overwritten", conf_path)
        if errors:
            for err in errors:
                print_err(err)
            raise RecorderConfigGenerationError(
                "there were errors during files checking")
        for conf in confs_to_del:
            del configs[conf]

    def _write_configurations(self, configs):
        """
        Writes configurations to their designated files
        overwriting whatever content there was before.

        Args:
            `configs`:
                Dictionary mapping file paths to their
                new content.
        """
        for conf, content in configs.items():
            wrt_path = osp.join(self.dest_path, conf)
            with open(wrt_path, 'w') as f:
                f.write(content)

    def gen_and_write_non_bl_conf(self):
        """
        Works like `gen_and_write_source_conf()` method but instead of
        creating configuration for sources listed in the file
        creates a single configuration file for the
        non-blacklist recorder.

        Raises:
            `RecorderConfigGenerationError`:
                If the configuration file alredy exists and
                the flags `skip_errors` and `overwrite` are
                set to `False`.
        """
        path = osp.join(
            self.dest_path,
            self.N6RECORDER_NON_BL_CONF_BAME + ".conf")
        if osp.exists(path):
            if not self.overwrite:
                err_msg = (
                    "config file '{}' already exists "
                    "and overwritting wasn't allowed "
                    "(use --overwrite if you want it "
                    " to be overwritten)").format(path)
                if self.skip_errors:
                    print_msg("skipping error: {}".format(err_msg))
                    return
                raise RecorderConfigGenerationError(err_msg)
            print_msg("config file '{}' will be overwritten", path)
        with open(path, 'w') as f:
            f.write(self.generate_non_bl_recorder_conf())

    def gen_and_write_source_conf(self):
        """
        Creates and writes the configuration files for the
        sources in the source file to the destination path.

        Raises:
            `RecorderConfigGenerationError`:
                If there were errors in the called methods.
                See other methods documentation for more details.
        """
        configs = self.get_source_configurations()
        configs = {self.file_name_from_source(k): v for k, v in configs.items()}
        self._check_config_files(configs)
        self._write_configurations(configs)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="Generate supervisor configuration in the given destination"
                    " directory for the sources given in the source file.")
    parser.add_argument("source",
                        help="Path to the source file containing one source per line."
                             " Source is a string in format 'source_label.source_channel'")
    parser.add_argument("dest",
                        help="Path to a directory to generate the config files to.")
    parser.add_argument("-n", "--non-blacklist", action='store_true',
                        help="Additionaly to the bl recorders creates "
                             "configuration for the non blacklist recorder.")
    parser.add_argument("-o", "--overwrite", action='store_true',
                        help="Should the configuration files be overwritten if already present")
    parser.add_argument("-s", "--skip-errors", action='store_true',
                        help="If set then if possible script will try to skip on errors instead"
                             " of stopping execution"
                             "(for example: illegal value in the source file")
    return parser


def main():
    args = get_argparser().parse_args()
    try:
        conf_generator = RecorderConfigGenerator(
            args.source, args.dest, args.overwrite, args.skip_errors)
        conf_generator.gen_and_write_source_conf()
        if args.non_blacklist:
            conf_generator.gen_and_write_non_bl_conf()
    except RecorderConfigGenerationError as e:
        print_err(e.exit_msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
