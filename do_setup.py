#!/usr/bin/env python3
# Copyright (c) 2013-2025 NASK. All rights reserved.

"""
`do_setup.py` is the *n6* installation script.

***

Below -- some usage examples... *Note*: the script always needs to be
run in a Python virtual environment.

* Show a fairly extensive description of all command-line arguments (and
  environment variables) supported by `do_setup.py`:

      ./do_setup.py --help   # or just -h

* Install all *n6* packages and their basic dependencies:

      ./do_setup.py all

  ...which is equivalent to:

      ./do_setup.py -a install all

  (`-a` is an abbreviation for `--action`; "install" is the default)

* Similarly, install all *n6* packages and their basic dependencies, but
  this time -- including also the *tests* optional dependencies:

      ./do_setup.py -x tests -- all

  (`-x` is an abbreviation for `--n6-package-extras`)

* Uninstall everything, unconditionally delete `*.egg-info` files and
  other build artifacts (if any), then update *pip* and *uv*, and then
  install all *n6* packages and their basic dependencies:

      ./do_setup.py -U -u all

  (`-U` is an abbreviation for `--first-uninstall-all-and-clean-up`;
  `-u` is an abbreviation for `--update-basic-setup-tools`)

* Just *uninstall* everything and unconditionally delete `*.egg-info`
  files and other build artifacts (if any):

      ./do_setup.py -U ''

* Just update *pip* and *uv*:

      ./do_setup.py -u ''

* Install *for development* (i.e., in the *editable* mode) all *n6*
  packages and their basic dependencies:

      ./do_setup.py -a dev all

  ...which is equivalent to:

      ./do_setup.py --action develop all

  Note, however, that the recommended way of *development installation*
  is described below (in the next bullet point).

* Install *for development* (i.e., in the *editable* mode) all *n6*
  packages and their basic dependencies, but this time -- including
  also the *dev* optional dependencies:

      ./do_setup.py -a dev -x dev -- all

  The same expressed more concisely:

      ./do_setup.py --dev all

  ...or even:

      ./do_setup.py -d all

  *Note*: it is worth noting that, among our *dev* optional dependencies,
  there is the *[Invoke](https://www.pyinvoke.org/)* tool, for which we
  have defined a handful of *tasks* that may prove necessary or just
  useful in your everyday work on development of *n6*. To familiarize
  with those tasks -- after successfully executing the above command --
  you can try:

      inv --list   # or just -l
      inv add-completion-to-venv --help   # or just -h
      inv delete-pycs --help
      inv pytest --help
      inv regen-requirements --help
      inv sync-dev --help

  See also:
    * https://docs.pyinvoke.org/en/stable/
    * the `tasks.py` and `invoke.yaml` files residing at the top of the
      *n6* source code directory.

* Install the `N6DataSources` and `N6AdminPanel` packages, with all
  basic dependencies:

      ./do_setup.py N6DataSources N6AdminPanel

  *Note*: when it comes to the *n6* packages, `N6DataSources` depends on
  `N6DataPipeline` + `N6Lib` + `N6SDK`, and `N6AdminPanel` depends on
  `N6Lib` + `N6SDK` -- so those "inner" dependencies (`N6DataPipeline`,
  `N6Lib` and `N6SDK`) are automatically installed as well (together
  with *their* external dependencies).

* The same as in the previous example, but *without* the automatic
  installation of the "inner" dependencies (`N6DataPipeline`, `N6Lib`
  and `N6SDK`), which is OK if those "inner" dependencies are already
  installed:

      ./do_setup.py -N N6DataSources N6AdminPanel

  (`-N` is an abbreviation for `--no-auto-n6-inner-dependencies`)

* Install all basic dependencies defined in the relevant
  `requirements*.txt` files, but *without* actual *n6* stuff
  (e.g., if you want to install the *n6* packages later):

      ./do_setup.py -r N6DataSources N6AdminPanel

  (`-r` is an abbreviation for `--requirements-but-no-n6-packages`)

  *Note*: here all basic *dependencies* for `N6DataSources` and
  `N6AdminPanel` as well as for `N6DataPipeline`, `N6Lib` and `N6SDK`
  are installed but the *n6* packages themselves (`N6DataSources`,
  `N6AdminPanel`, `N6DataPipeline`, `N6Lib`, `N6SDK`) are *not*.

* Install the `N6DataSources` and `N6AdminPanel` n6* packages, but
  *without* any of the dependencies defined in `requirements*.txt`
  files (e.g., if you have already installed those dependencies):

      ./do_setup.py -n N6DataSources N6AdminPanel

  (`-n` is an abbreviation for `--n6-packages-but-no-requirements`)

  *Note*: here the *n6* packages -- `N6DataSources`and `N6AdminPanel` as
  well as `N6DataPipeline`, `N6Lib` and `N6SDK` -- *are* installed (and
  *only* them).

* Install the `N6DataSources` and `N6AdminPanel` packages, with all
  basic dependencies -- with the proviso that no `*.pyc` files are
  generated during installation:

      ./do_setup.py -B N6DataSources N6AdminPanel

  (`-B` is an abbreviation for `--never-compile-bytecode`)

* Install the `N6DataSources` and `N6AdminPanel` packages, with all
  basic dependencies -- with the proviso that nothing is read or written
  from/to any *uv*'s or *pip*'s cache files:

      ./do_setup.py --no-cache N6DataSources N6AdminPanel
"""

from __future__ import annotations

import ast
import argparse
import collections
import contextlib
import json
import logging
import logging.config
import os
import re
import shlex
import subprocess
import sys
import tempfile
try:
    import tomllib
except ImportError:
    tomllib = None  # XXX... Py3.9 :-/
import traceback
from collections.abc import (
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Set,
)
from functools import cached_property
from pathlib import (
    PosixPath,
    PurePosixPath,
)
from typing import (
    Any,
    TYPE_CHECKING,
    Protocol,
    Union,
    cast,
    final,
)

if TYPE_CHECKING:
    from n6lib.typing_helpers import SupportsWrite, T

assert sys.version_info[:2] >= (3, 9)  # XXX... Py3.9 :-/


#
# Constants
#


ENV_VAR_NAME_DRY_RUN = 'N6_DO_SETUP_DRY_RUN'
ENV_VAR_NAME_COMMANDS_DUMP = 'N6_DO_SETUP_COMMANDS_DUMP'

DEFAULT_LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'brief': {'format': '\n%(asctime)s [%(levelname)s] %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'brief',
            'stream': 'ext://sys.stdout',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}

ACTION_INSTALL = 'install'
ACTION_DEV = 'dev'
ACTION_DEV_ALT_SPELLING = 'develop'

EXTRA_DEV = 'dev'

SPEC_N6_ALL = 'all'

PYPROJECT_FILENAME = 'pyproject.toml'

N6_BONUS_COMPANION_PACKAGE_DIRNAME_REGEX = re.compile(
    r'''
        (N6[A-Z]\w*)  # <- core n6 package dirname
        -\w+          # <- this bc-package's suffix
    ''',
    re.ASCII | re.VERBOSE,
)

PER_PACKAGE_BASIC_REQUIREMENTS_FILENAME = 'requirements.txt'
PER_PACKAGE_EXTRA_REQUIREMENTS_FILENAME_FMT = 'requirements-{extra}.txt'

ALL_CORE_REQUIREMENTS_DIRNAME = 'requirements'
ALL_BONUS_COMPANIONS_REQUIREMENTS_DIRNAME_GLOB_PATTERN = 'requirements-*'
ALL_REQUIREMENTS_FILENAME = "requirements-ALL.txt"
MANUAL_CONSTRAINTS_FILENAME = "manual-constraints.txt"

EGG_INFO_SUFFIX = '.egg-info'
PER_PACKAGE_BUILD_ARTIFACT_GLOB_PATTERNS = [
    'build',
    'dist',
    f'n6*{EGG_INFO_SUFFIX}'
]

PIP_CONSTANT_OPTIONS = [
    '--isolated',
    '--no-input',
    '--require-virtualenv',
]
UV_PIP_CONSTANT_OPTIONS = [
    '--no-config',
    '--no-python-downloads',
    '--no-progress',
]
RM_COMMAND = '/bin/rm'


#
# Script-arguments-related classes
#


class ScriptArgumentParser(argparse.ArgumentParser):

    def __init__(self):
        super().__init__(
            description=(
                "use this script to install some (or all) components "
                "of n6, always in a Python virtual environment (the "
                "script refuses to work without that); for usage "
                "examples, see the script's docstring..."
            ),
            epilog=(
                f"note: you can also modify the behavior of this script "
                f"by setting the following environment variables to a "
                f"non-empty value: {ENV_VAR_NAME_DRY_RUN} - has the "
                f"same effect as specifying the `--dry-run` option; "
                f"{ENV_VAR_NAME_COMMANDS_DUMP} - causes that first a "
                f"*command dump* file is created, then all external "
                f"commands run by this script are dumped to that file, "
                f"each as a one-line JSON array of strings representing "
                f"the spawned subprocess's name and arguments, and "
                f"finally (when the script is about to exit) a log "
                f"INFO message containing the *command dump* file's "
                f"path is emitted (the *commands dump* feature is "
                f"intended to facilitate testing and debugging of "
                f"this script)"
            ),
        )
        self.add_argument(
            'n6_packages',
            nargs='+',
            metavar='N6-PACKAGE-DIRECTORY',
            help=(
                f"one or more `N6*` directory names identifying the n6 "
                f"packages to be installed (note that, for convenience, "
                f"trailing slashes and lowercase-vs-uppercase variances "
                f"are treated as insignificant), or one of the special "
                f"values: {SPEC_N6_ALL!a} - install all available n6 "
                f"packages, '' (explicit empty string) - do not install "
                f"any n6 packages or their dependencies (yet still do "
                f"other operations, should any be performed); note: "
                f"value duplicates (repeated occurrences of a value) "
                f"as well as redundant '' values (empty strings) are "
                f"ignored (which may occasionally prove useful when "
                f"scripting using custom environment variables...)"
            ),
        )
        self.add_argument(
            '-a', '--action',
            default=ACTION_INSTALL,
            choices=[ACTION_INSTALL, ACTION_DEV, ACTION_DEV_ALT_SPELLING],
            metavar='ACTION',
            help=(
                f"either {ACTION_INSTALL!a} or {ACTION_DEV!a} (legacy "
                f"spelling {ACTION_DEV_ALT_SPELLING!a} is also accepted); "
                f"{ACTION_INSTALL!a} - normal installation, {ACTION_DEV!a} "
                f"- \"editable\" installation (i.e., with the `uv pip`'s "
                f"option `-e`, when it comes to n6 packages); default: "
                f"{ACTION_INSTALL!a}"
            ),
        )
        legal_extras = sorted(sf.all_n6_package_extras)
        legal_extras_listing = ', '.join(map(ascii, legal_extras))
        self.add_argument(
            '-x', '--n6-package-extras',
            nargs='+',
            default=[],
            choices=legal_extras,
            metavar='EXTRA',
            help=(
                f"one or more identifiers of the n6 packages' *extras* "
                f"(aka *optional dependencies*) to be included during "
                f"installation (if applicable for an n6 package being "
                f"installed); each EXTRA value must exist as a key in "
                f"the \"project.optional-dependencies\" table in any "
                f"n6 package's `pyproject.toml`, that is, must be one "
                f"of: {legal_extras_listing}; note: value duplicates "
                f"(repeated occurrences of a value) and any '' values "
                f"(empty strings) are ignored (which may occasionally "
                f"prove useful when scripting using custom environment "
                f"variables...); by default, no *extras* are included"
            ),
        )
        self.add_argument(
            '-d', '--dev',
            action='store_true',
            help=(
                f"set ACTION to {ACTION_DEV!a} (overriding the option "
                f"`-a`/`--action`) and force the n6 packages' *extras* "
                f"list (see the option `-x`/`--n6-package-extras`) to "
                f"include {EXTRA_DEV!a} (you can think of this option "
                f"as a shortcut for `-x {EXTRA_DEV} -a {ACTION_DEV}`)"
            ),
        )
        self.add_argument(
            '-r', '--requirements-but-no-n6-packages',
            action='store_true',
            help=(
                "after installing external requirements, skip the "
                "actual installation of n6 packages (e.g., if you "
                "want to install them later)"
            ),
        )
        self.add_argument(
            '-n', '--n6-packages-but-no-requirements',
            action='store_true',
            help=(
                "before installing n6 packages, skip the actual "
                "installation of external requirements (e.g., if "
                "you installed them earlier)"
            ),
        )
        self.add_argument(
            '-N', '--no-auto-n6-inner-dependencies',
            action='store_true',
            help=(
                "disable the default mechanism of resolving "
                "dependencies between n6 packages themselves (i.e., "
                "of automatic installation of those n6 packages which "
                "are directly or indirectly required by n6 packages "
                "already selected to be installed)"
            ),
        )
        self.add_argument(
            '-b', '--auto-bonus-companions',
            action='store_true',
            help=(
                "enable automatic installation of those custom "
                "\"bonus\" n6 packages (aka *bonus companions* "
                "or *bc* packages) whose directory names (e.g., "
                "'N6DataSources-any_alnum_chars') correspond to "
                "those *core* n6 packages which are explicitly "
                "listed as to be installed (e.g., 'N6DataSources')"
            ),
        )
        self.add_argument(
            '-B', '--never-compile-bytecode',
            action='store_true',
            help=(
                "disable the mechanism of bytecode compilation (that "
                "is, creating `*.pyc` files) during installation; "
                "normally, it is active for all packages (n6 ones and "
                "external ones) which are being installed in the non-"
                "\"editable\" mode (without the `uv pip`'s option `-e`)"
            ),
        )
        self.add_argument(
            '-p', '--additional-packages',
            nargs='+',
            default=[],
            metavar='PACKAGE',
            help=(
                "one or more names (or whole requirement specifiers) "
                "of additional external packages to be installed; "
                "note: value duplicates (repeated occurrences of a "
                "value) and any '' values (empty strings) are ignored "
                "(which may occasionally prove useful when scripting "
                "using custom environment variables...); by default, "
                "no additional packages are installed"
            ),
        )
        self.add_argument(
            '-k', '--keep-build-artifacts',
            action='store_true',
            help=(
                f"after successful installation, keep any newly created "
                f"build artifacts (`build`, `dist`, `n6*.egg-info`) if "
                f"they remained in the source code directories of the "
                f"installed n6 packages, i.e., disable the default "
                f"mechanism of auto-removal of `build`, `dist` and "
                f"`n6*.egg-info` when ACTION is {ACTION_INSTALL!a}, or "
                f"just `build` and `dist` when ACTION is {ACTION_DEV!a} "
                f"(note that, anyway, that auto-removal mechanism is "
                f"not applied to any paths that existed before the "
                f"script execution; this contrasts with the thorough "
                f"and ruthless style of operations triggered by the "
                f"options `-C`/`--first-clean-up` and "
                f"`-U`/`--first-uninstall-all-and-clean-up`)"
            ),
        )
        self.add_argument(
            '-C', '--first-clean-up',
            action='store_true',
            help=(
                "before installation of n6 packages/their dependencies, "
                "for each n6 package whose source directory exists (not "
                "only for those selected to be installed!), ruthlessly "
                "remove any existing build artifacts, i.e., `dist`, "
                "`build` and `n6*.egg-info` subpaths (regardless of "
                "what ACTION is); *WARNING*: removals are performed "
                "without any interactive prompts or runtime warnings"
            ),
        )
        self.add_argument(
            '-U', '--first-uninstall-all-and-clean-up',
            action='store_true',
            help=(
                "before installation of n6 packages/their dependencies, "
                "execute `uv pip uninstall` regarding all packages "
                "already installed in the current Python virtual "
                "environment (i.e., both n6 ones and external ones, "
                "except the 'uv' and 'pip' packages), then remove "
                "any existing build artifacts, as if the option "
                "`-C`/`--first-clean-up` was specified (see the "
                "*WARNING* its description includes)"
            ),
        )
        self.add_argument(
            '-u', '--update-basic-setup-tools',
            action='store_true',
            help=(
                "before any other `uv pip` operations, execute "
                "`uv pip install --upgrade` regarding just the "
                "'uv' and 'pip' packages themselves"
            ),
        )
        self.add_argument(
            '-E', '--no-ensure-uv',
            action='store_true',
            help=(
                "disable the default mechanism of automatic "
                "installation of 'uv' before any other operations "
                "if 'uv' is not already installed"
            ),
        )
        self.add_argument(
            '--dry-run',
            action='store_true',
            help=(
                "do not install/uninstall/update/remove/clean "
                "anything (actually, no external commands are "
                "run, so no destructive operations are performed)"
            ),
        )
        self.add_argument(
            '--no-cache',
            action='store_true',
            help=(
                "always run 'uv' with the `--no-cache` option "
                "and 'pip' with the `--no-cache-dir` option"
            ),
        )
        self.add_argument(
            '--log-config',
            default=ascii(DEFAULT_LOG_CONFIG),
            metavar='DICT',
            help=(
                f"a Python dict literal specifying the logging configuration "
                f"for this script, in the logging.config.dictConfig format; "
                f"default: {ascii(DEFAULT_LOG_CONFIG).replace('%', '%%')!a}"
            ),
        )

    def parse_args(self, /, *args, **kwargs) -> ParsedScriptArguments:
        arguments = super().parse_args(*args, **kwargs)

        if arguments.dev:
            arguments.action = ACTION_DEV
            arguments.n6_package_extras.append(EXTRA_DEV)
        elif arguments.action == ACTION_DEV_ALT_SPELLING:
            arguments.action = ACTION_DEV

        arguments.n6_package_extras = (
            self.__sorted_nonfalse_unique(arguments.n6_package_extras)
        )
        arguments.n6_packages = (
            self.__get_adjusted_n6_packages(arguments)
        )
        arguments.additional_packages = (
            self.__sorted_nonfalse_unique(arguments.additional_packages)
        )
        arguments.log_config = self.__parse_log_config_dict(cast(str, arguments.log_config))

        return arguments


    def __sorted_nonfalse_unique(self, iterable: Iterable[T]) -> list[T]:
        return sorted(filter(None, set(iterable)))


    def __get_adjusted_n6_packages(self, arguments: ParsedScriptArguments) -> list[str]:
        n6_packages = self.__sorted_nonfalse_unique(arguments.n6_packages)

        if n6_packages == [SPEC_N6_ALL]:
            n6_packages = list(sf.all_n6_packages)
        else:
            try:
                n6_packages = list(map(sf.normalize_n6_pkg_dirname, n6_packages))
            except ValueError as exc:
                self.error(str(exc))

        if arguments.auto_bonus_companions:
            n6_packages.extend(self.__iter_bc_corresponding_to_selected_core(n6_packages))

        if not arguments.no_auto_n6_inner_dependencies:
            n6_packages = self.__get_n6_packages_including_all_relevant_inner_dependencies(
                n6_packages,
                # Note: taking `arguments.n6_package_extras` into consideration.
                relevant_extras=set(arguments.n6_package_extras),
            )

        return self.__sorted_nonfalse_unique(n6_packages)


    def __iter_bc_corresponding_to_selected_core(
        self,
        n6_packages: Sequence[str],
    ) -> Iterator[str]:
        # If the `-b`/`--auto-bonus-companions` flag is set then, for
        # each core n6 package which is explicitly listed (by the user)
        # as to be installed *and* for which the corresponding *bonus
        # companion* exists, we select also that bonus companion (e.g.,
        # if `N6DataSources` is explicitly listed to be installed *and*
        # `N6DataSources-my_custom_stuff` also exists, we install also
        # the latter, even if it is not explicitly listed).
        for n6_pkg_dirname in n6_packages:
            if corresponding_bc := sf.core_to_bc.get(n6_pkg_dirname):
                yield corresponding_bc


    def __get_n6_packages_including_all_relevant_inner_dependencies(
        self,
        n6_packages: Sequence[str],
        relevant_extras: Set[str],
    ) -> list[str]:

        n6_pkg_dirname_to_relevant_direct_inner_deps = (
            self.__get_n6_pkg_dirname_to_relevant_direct_inner_deps(relevant_extras)
        )
        resolved = set()
        pending = collections.deque(n6_packages)
        while pending:
            n6_pkg_dirname = pending.popleft()
            if n6_pkg_dirname not in resolved:
                pending.extend(n6_pkg_dirname_to_relevant_direct_inner_deps[n6_pkg_dirname])
                resolved.add(n6_pkg_dirname)
        assert resolved.issuperset(n6_packages)
        return sorted(resolved)


    def __get_n6_pkg_dirname_to_relevant_direct_inner_deps(
        self,
        relevant_extras: Set[str],
    ) -> Mapping[str, Sequence[str]]:

        n6_pkg_actual_name_to_dirname = {
            self.__extract_canonical_name(pyproject['project']['name']): n6_pkg_dirname
            for n6_pkg_dirname, pyproject in sf.n6_pkg_to_pyproject.items()
        }

        def iter_n6_pkg_dirnames_from_pkg_specs(pkg_specs: Iterable[str]) -> Iterator[str]:
            for spec in pkg_specs:
                n6_pkg_actual_name = self.__extract_canonical_name(spec)
                if n6_pkg_actual_name.startswith('n6'):
                    try:
                        yield n6_pkg_actual_name_to_dirname[n6_pkg_actual_name]
                    except KeyError:
                        sys.exit(f'fatal error: unknown n6 package {n6_pkg_actual_name}')

        def get_relevant_direct_dependencies(project: Mapping[str, Any]) -> Set[str]:
            return set().union(
                iter_n6_pkg_dirnames_from_pkg_specs(project.get('dependencies', ())),
                *(
                    iter_n6_pkg_dirnames_from_pkg_specs(pkg_specs)
                    for extra, pkg_specs in project.get('optional-dependencies', {}).items()
                    if extra in relevant_extras
                ),
            )

        return {
            n6_pkg_dirname: sorted(get_relevant_direct_dependencies(pyproject['project']))
            for n6_pkg_dirname, pyproject in sf.n6_pkg_to_pyproject.items()
        }


    def __extract_canonical_name(self, spec: str) -> str:
        # This stuff mimics helpers from `packaging` (which cannot be imported here).
        name = self.__REQ_NAME_FROM_REQ_SPEC_REGEX.search(spec).group('name')
        return self.__REQ_NAME_SEP_REGEX.sub('-', name).lower()

    __REQ_NAME_FROM_REQ_SPEC_REGEX = re.compile(r'\A\s*(?P<name>[a-zA-Z0-9][a-zA-Z0-9._-]*\b)')
    __REQ_NAME_SEP_REGEX = re.compile(r'[._-]+')


    def __parse_log_config_dict(self, raw_opt_value: str) -> dict:
        try:
            parsed = ast.literal_eval(raw_opt_value)
            if not isinstance(parsed, dict):
                raise ValueError
        except (ValueError, SyntaxError):
            self.error(f'{raw_opt_value!a} is not a literal-evaluable Python dict')
        return parsed


class ParsedScriptArguments(Protocol):

    n6_packages: Sequence[str]

    action: str
    n6_package_extras: Sequence[str]
    requirements_but_no_n6_packages: bool
    n6_packages_but_no_requirements: bool
    no_auto_n6_inner_dependencies: bool
    auto_bonus_companions: bool
    never_compile_bytecode: bool
    additional_packages: Sequence[str]

    keep_build_artifacts: bool
    first_clean_up: bool
    first_uninstall_all_and_clean_up: bool
    update_basic_setup_tools: bool
    no_ensure_uv: bool

    dry_run: bool
    no_cache: bool
    log_config: dict


#
# OS+filesystem operations helper class and its global instance
#


@final
class SystemFacade:

    #
    # Instance's public interface

    # * Method to load deferred properties (call it before any use of instance!):

    def load(self) -> None:
        # (see also: `__init__()` and `__getattribute__()` definitions below)
        deferred_property_names = self._deferred_property_names
        if deferred_property_names is not None:
            self._deferred_property_names = None
            try:
                for name in deferred_property_names:
                    super().__getattribute__(name)
            except:  # noqa
                self._deferred_property_names = deferred_property_names
                raise

        assert list(self.all_n6_packages) == list(
            map(self.normalize_n6_pkg_dirname, self.all_n6_packages),
        )

    # * System data properties (constant throughout script execution):

    @cached_property
    def virtual_environment_path(self) -> PosixPath:
        if sys.prefix == sys.base_prefix:
            sys.exit('fatal error: no Python virtual environment is in use')
        sys_prefix_path = PosixPath(sys.prefix)
        assert sys_prefix_path.is_absolute()
        return sys_prefix_path

    @cached_property
    def python_exe_path(self) -> PosixPath:
        python_exe_path = PosixPath(sys.executable)
        assert python_exe_path.is_absolute()
        assert python_exe_path.is_relative_to(self.virtual_environment_path)
        return python_exe_path

    @cached_property
    def top_dir_path(self) -> PosixPath:
        top_dir_path = PosixPath(__file__).parent.resolve(strict=True)
        assert top_dir_path.is_absolute()
        return top_dir_path

    @cached_property
    def all_core_constraints_paths(self) -> Sequence[PosixPath]:
        all_core_constraints_paths = self._find_constraints_paths(
            dirname_glob_pattern=ALL_CORE_REQUIREMENTS_DIRNAME,
        )
        assert all(path.is_absolute() for path in all_core_constraints_paths)
        return all_core_constraints_paths

    @cached_property
    def all_bc_constraints_paths(self) -> Sequence[PosixPath]:
        all_bc_constraints_paths = self._find_constraints_paths(
            dirname_glob_pattern=ALL_BONUS_COMPANIONS_REQUIREMENTS_DIRNAME_GLOB_PATTERN,
        )
        assert all(path.is_absolute() for path in all_bc_constraints_paths)
        return all_bc_constraints_paths

    @cached_property
    def all_n6_packages(self) -> Sequence[str]:
        try:
            all_n6_packages = sorted(
                p.name
                for p in self.top_dir_path.iterdir()
                if self._looks_like_n6_pkg_dir(p)
            )
        except OSError as exc:
            sys.exit(
                f'fatal error while trying to list the directory '
                f'{str(self.top_dir_path)!a} ({exc})',
            )
        assert len(all_n6_packages) == len(set(all_n6_packages))
        return all_n6_packages

    @cached_property
    def bc_to_core(self) -> Mapping[str, str]:
        bc_to_core = {
            match[0]: match[1]
            for match in map(
                N6_BONUS_COMPANION_PACKAGE_DIRNAME_REGEX.search,
                self.all_n6_packages,
            )
            if match
        }
        assert set(bc_to_core.keys()).issubset(self.all_n6_packages)
        assert None not in bc_to_core
        return bc_to_core

    @cached_property
    def core_to_bc(self) -> Mapping[str, str]:
        core_to_bc = {
            c: bc
            for bc, c in self.bc_to_core.items()
        }
        assert len(core_to_bc) == len(self.bc_to_core)
        assert set(core_to_bc.keys()).issubset(self.all_n6_packages)
        assert None not in core_to_bc
        return core_to_bc

    @cached_property
    def n6_pkg_to_pyproject(self) -> Mapping[str, Mapping[str, Any]]:
        return {
            n6_pkg_dirname: self._load_pyproject_file(n6_pkg_dirname)
            for n6_pkg_dirname in self.all_n6_packages
        }

    @cached_property
    def n6_pkg_to_extras(self) -> Mapping[str, Set[str]]:
        return {
            n6_pkg_dirname: frozenset(pyproject['project']['optional-dependencies'])
            for n6_pkg_dirname, pyproject in self.n6_pkg_to_pyproject.items()
        }

    @cached_property
    def all_n6_package_extras(self) -> Set[str]:
        all_n6_package_extras = frozenset().union(*self.n6_pkg_to_extras.values())
        assert EXTRA_DEV in all_n6_package_extras
        assert all(
            isinstance(extra, str) and extra.isascii() and extra.isalnum()
            for extra in all_n6_package_extras
        )
        return all_n6_package_extras

    # * Logging-related stuff:

    @property
    def logger(self) -> logging.Logger:
        try:
            return self._logger
        except AttributeError as exc:
            raise AssertionError(
                'the configure_logging() method should be invoked '
                'before an attempt to get the logger',
            ) from exc

    def configure_logging(self, arguments: ParsedScriptArguments) -> None:
        try:
            logging.config.dictConfig(arguments.log_config)
        except Exception:  # noqa
            sys.exit(
                f'fatal error: could not configure logging according '
                f'to the specified config: {arguments.log_config!a}\n'
                f'cause: {traceback.format_exc()}',
            )
        self._logger = logging.getLogger('n6_do_setup')  # noqa
        self._logger.debug('logging configured')
        self._emit_deferred_warnings()

    def log_done_op(self, msg, /, *args, **kwargs) -> None:
        assert self._dry_run is not None  # (already set to True or False)
        if self._dry_run:
            msg = f'{msg} [`--dry-run`, so no real op!]'
        self.logger.info(msg, *args, **kwargs)

    # * Command running stuff:

    @contextlib.contextmanager
    def ready_to_run_commands(self, arguments: ParsedScriptArguments) -> Generator[None]:
        self._dry_run = arguments.dry_run or self._dry_run_according_to_env_var  # noqa
        self._found_artifact_paths = self._find_in_n6_package_dirs(  # noqa
            arguments.n6_packages,
            glob_patterns=PER_PACKAGE_BUILD_ARTIFACT_GLOB_PATTERNS,
        )

        original_wd = os.getcwd()
        try:
            os.chdir(self.top_dir_path)
            with self._open_commands_dump_file_if_enabled():
                yield
                self._on_success()
        finally:
            os.chdir(original_wd)

    def run_command(
        self,
        *args: Union[str, PurePosixPath],
        never_raise_for_exit_status: bool = False,
    ) -> int:
        assert self._dry_run is not None  # (already set to True or False)
        assert args

        args = [str(a) if isinstance(a, PurePosixPath) else a for a in args]
        assert all(isinstance(a, str) for a in args)

        cur_dir = os.getcwd()
        command_repr = ascii(shlex.join(args))
        if self._dry_run:
            command_repr = f'{command_repr} [`--dry-run`, so no real op!]'

        self.logger.info('executing (in %a): %s...', cur_dir, command_repr)

        if self._commands_dump_enabled:
            assert self._commands_dump_file is not None
            print(json.dumps(args), file=self._commands_dump_file)

        if not self._dry_run:
            exit_status = subprocess.run(args, cwd=cur_dir).returncode
            if exit_status != 0:
                if never_raise_for_exit_status:
                    return exit_status
                sys.exit(
                    f'exiting after an error from the '
                    f'external command {command_repr}',
                )

        self._successful_command_memos.append(f'(in {cur_dir!a}) {command_repr}')
        return 0

    # * Other public methods:

    @staticmethod
    def are_we_in_virtual_environment() -> bool:
        return sys.prefix != sys.base_prefix

    def normalize_n6_pkg_dirname(self, given_dirname: str) -> str:
        lowercased_dirname = given_dirname.rstrip('/').lower()
        try:
            return self._lowercased_to_actual_dirname[lowercased_dirname]
        except KeyError as exc:
            raise ValueError(
                f'{given_dirname.rstrip("/")!a} does not '
                f'specify an n6 package directory',
            ) from exc

    def remove_all_build_artifacts(self) -> None:
        assert self._found_artifact_paths is not None

        for path in sorted(
            self._find_in_n6_package_dirs(  # noqa
                self.all_n6_packages,
                glob_patterns=PER_PACKAGE_BUILD_ARTIFACT_GLOB_PATTERNS,
            ),
        ):
            self.run_command(RM_COMMAND, '-rf', path)
            self._found_artifact_paths.discard(path)

    def remove_new_obviously_junk_build_artifacts(self, arguments: ParsedScriptArguments) -> None:
        assert self._found_artifact_paths is not None

        for path in sorted(
            self._find_in_n6_package_dirs(  # noqa
                arguments.n6_packages,
                glob_patterns=PER_PACKAGE_BUILD_ARTIFACT_GLOB_PATTERNS,
            ),
        ):
            is_protected = (
                path in self._found_artifact_paths
                or (arguments.action == ACTION_DEV and path.suffix == EGG_INFO_SUFFIX)
            )
            if not is_protected:
                self.run_command(RM_COMMAND, '-rf', path)

    #
    # Non-public internals

    # * Deferred property loading mechanism:

    def __init__(self):
        self._deferred_property_names = [
            name
            for name, obj in vars(type(self)).items()
            if isinstance(obj, cached_property)
        ]
        assert self._deferred_property_names == [
            'virtual_environment_path',
            'python_exe_path',
            'top_dir_path',
            'all_core_constraints_paths',
            'all_bc_constraints_paths',
            'all_n6_packages',
            'bc_to_core',
            'core_to_bc',
            'n6_pkg_to_pyproject',
            'n6_pkg_to_extras',
            'all_n6_package_extras',
            '_lowercased_to_actual_dirname',
            '_dry_run_according_to_env_var',
            '_commands_dump_enabled',
            '_deferred_warnings',
            '_successful_command_memos',
            '_dry_run',
            '_found_artifact_paths',
            '_commands_dump_file',
        ]

    def __getattribute__(self, name: str) -> Any:
        if (name in {'load', '_deferred_property_names'}
              or self._deferred_property_names is None):
            return super().__getattribute__(name)
        raise AssertionError(
            'the load() method should be invoked before '
            'attempting to access any method/attribute',
        )

    # * System data properties (constant throughout script execution):

    @cached_property
    def _lowercased_to_actual_dirname(self) -> Mapping[str, str]:
        lowercased_to_actual_dirname = {
            n6_pkg_dirname.lower(): n6_pkg_dirname
            for n6_pkg_dirname in self.all_n6_packages
        }
        assert len(lowercased_to_actual_dirname) == len(self.all_n6_packages)
        return lowercased_to_actual_dirname

    @cached_property
    def _dry_run_according_to_env_var(self) -> bool:
        return bool(os.environ.get(ENV_VAR_NAME_DRY_RUN))

    @cached_property
    def _commands_dump_enabled(self) -> bool:
        return bool(os.environ.get(ENV_VAR_NAME_COMMANDS_DUMP))

    # * Variable/mutable properties:

    @cached_property
    def _deferred_warnings(self) -> Union[list[str], None]:
        # (mutable... + to be set to None in `_emit_deferred_warnings()`)
        return []

    @cached_property
    def _successful_command_memos(self) -> list[str]:
        # (mutable...)
        return []

    @cached_property
    def _dry_run(self) -> Union[bool, None]:
        # (to be set to True or False in `ready_to_run_commands()`)
        return None

    @cached_property
    def _found_artifact_paths(self) -> Union[set[PosixPath], None]:
        # (to be set to a mutable set in `ready_to_run_commands()`...)
        return None

    @cached_property
    def _commands_dump_file(self) -> Union[SupportsWrite, None]:
        # (to be conditionally set to a file-like object
        # in `_open_commands_dump_file_if_enabled()`)
        return None

    # * Helper methods:

    def _find_constraints_paths(self, dirname_glob_pattern) -> list[PosixPath]:
        glob_patterns = [
            f'{dirname_glob_pattern}/{filename}'
            for filename in [
                ALL_REQUIREMENTS_FILENAME,
                MANUAL_CONSTRAINTS_FILENAME,
            ]
        ]
        try:
            return sorted(
                path
                for pattern in glob_patterns
                for path in self.top_dir_path.glob(pattern)
            )
        except OSError as exc:
            pattern_listing = ', '.join(map(ascii, glob_patterns))
            sys.exit(
                f'fatal error while trying to expand a glob pattern '
                f'in the directory {str(self.top_dir_path)!a} ({exc}; '
                f'the concerned pattern is one of: {pattern_listing})',
            )

    def _looks_like_n6_pkg_dir(self, path) -> bool:
        assert self._deferred_warnings is not None

        if path.name.startswith('N6') and path.is_dir():
            expected_file = PYPROJECT_FILENAME
            if (path / expected_file).exists():
                return True
            self._deferred_warnings.append(
                f'omitting the directory {str(path)!a} because it '
                f'does not contain {expected_file!a}',
            )
        return False

    def _load_pyproject_file(self, n6_pkg_dirname: str) -> Mapping[str, Any]:
        pyproject_path = self.top_dir_path / n6_pkg_dirname / PYPROJECT_FILENAME
        try:
            if tomllib is None:
                # XXX: Py3.9... Temporary ugly hack:
                content = pyproject_path.read_text()

                project_section_re = r'(?ams)^\[project](.*?)^\[\w+'
                project_section = re.search(project_section_re, content)[1]

                name_setting_re = r'(?am)^name\s*=\s*\"([nN]6[-\w]+)"'
                name = re.search(name_setting_re, project_section)[1]

                deps_setting_re = r'(?ams)^dependencies\s*=\s*\[(.*?)^]'
                deps_setting = re.search(deps_setting_re, project_section)[1]
                deps = re.findall(r'(?am)^\s*"([-\w]+)"', deps_setting)

                extras_section_re = r'(?ams)^\[project\.optional-dependencies](.*?)^\[\w+'
                extras_section = re.search(extras_section_re, content)[1]
                extras = re.findall(r'(?am)^([-\w]+)', extras_section)

                if 'n6' in extras_section.lower():
                    raise AssertionError(  # (XXX: yes, it's very ugly) :-|
                        'n6 stuff in optional-dependencies is unsupported for < Py3.11',
                    )

                return {
                    'project': {
                        'name': name,
                        'dependencies': deps,
                        'optional-dependencies': dict.fromkeys(extras, ()),
                    },
                }

            with pyproject_path.open('rb') as f:
                return tomllib.load(f)
        except Exception as exc:
            sys.exit(
                f'fatal error: a problem with loading the '
                f'{str(pyproject_path)!a} file ({exc})',
            )

    def _emit_deferred_warnings(self) -> None:
        # (called immediately after logging is configured)
        while self._deferred_warnings:
            warning_text = self._deferred_warnings.pop(0)
            self.logger.warning(warning_text)
        self._deferred_warnings = None  # noqa

    def _find_in_n6_package_dirs(
        self,
        n6_packages: Sequence[str],
        glob_patterns: Sequence[str],
    ) -> set[PosixPath]:
        found = set()
        for n6_pkg_dirname in n6_packages:
            dir_path = self.top_dir_path / n6_pkg_dirname
            try:
                found.update(
                    path
                    for pattern in glob_patterns
                    for path in dir_path.glob(pattern)
                )
            except OSError as exc:
                pattern_listing = ', '.join(map(ascii, glob_patterns))
                sys.exit(
                    f'fatal error while trying to expand a glob pattern '
                    f'in the directory {str(dir_path)!a} ({exc}; the '
                    f'concerned pattern is one of: {pattern_listing})',
                )
        return found

    @contextlib.contextmanager
    def _open_commands_dump_file_if_enabled(self) -> Generator[None]:
        if self._commands_dump_enabled:
            file_path = '<undetermined>'
            try:
                with tempfile.NamedTemporaryFile(
                    'w+t',
                    prefix='do_setup_commands_dump.',
                    suffix='.jsonl',
                    encoding='ascii',
                    errors='strict',
                    delete=False,
                ) as file:
                    self._commands_dump_file = file  # noqa
                    file_path = file.name
                    yield
            finally:
                self.logger.info('commands dump: %a', file_path)
        else:
            yield

    def _on_success(self) -> None:
        if self._successful_command_memos:
            self.logger.info(
                'successfully executed %d external commands',
                len(self._successful_command_memos),
            )
            self.logger.debug(
                'the %d external commands were:\n* ' +
                '\n* '.join(self._successful_command_memos),
                len(self._successful_command_memos),
            )


sf = SystemFacade()


#
# Actual script logic
#


def main() -> None:
    if not __debug__:
        # (let all `assert`s be 100% reliable
        # when this module is used as a script)
        sys.exit(
            "fatal error: this script requires that "
            "Python's `__debug__` constant is true "
            "(Python's `-O` flag must not be set)",
        )

    sf.load()
    arguments = ScriptArgumentParser().parse_args()
    sf.configure_logging(arguments)

    try:
        with sf.ready_to_run_commands(arguments):
            if not arguments.no_ensure_uv:
                ensure_uv(arguments)

            if arguments.update_basic_setup_tools:
                update_basic_setup_tools(arguments)

            if arguments.first_uninstall_all_and_clean_up:
                uninstall_all(arguments)
                sf.remove_all_build_artifacts()
            elif arguments.first_clean_up:
                sf.remove_all_build_artifacts()

            install_packages(arguments, just_dry_check=True)
            install_packages(arguments)
            check_packages(arguments)

            if not arguments.keep_build_artifacts:
                sf.remove_new_obviously_junk_build_artifacts(arguments)

    except SystemExit as exc:
        if exc.code:
            msg = (exc.code if isinstance(exc.code, str)
                   else f'exiting with the status: {exc.code!a}')
            sf.logger.error(msg)
            raise
        else:
            msg = f'unexpected fatal error: premature exit'
            sf.logger.critical(msg, exc_info=True)
            raise SystemExit(msg) from exc

    except:  # noqa
        sf.logger.critical('unexpected fatal error', exc_info=True)
        raise

    sf.logger.debug('exiting gracefully...')


def ensure_uv(
    arguments: ParsedScriptArguments,
) -> None:
    exit_status = sf.run_command(
        sf.python_exe_path,
        '-m',
        'uv',
        '--version',
        *UV_PIP_CONSTANT_OPTIONS,
        never_raise_for_exit_status=True,
    )
    if exit_status != 0:
        options = list(PIP_CONSTANT_OPTIONS)
        if arguments.no_cache:
            options.append('--no-cache-dir')
        sf.run_command(
            sf.python_exe_path,
            '-m',
            'pip',
            'install',
            '-qq',  # <- To silence warning about outdated *pip*.
            *options,
            'uv',
        )
        sf.log_done_op("OK, installed 'uv'")


def uninstall_all(
    arguments: ParsedScriptArguments,
) -> None:
    uv_pip_options = list(UV_PIP_CONSTANT_OPTIONS)
    if arguments.no_cache:
        uv_pip_options.append('--no-cache')

    format_uv_pip = (
        (
            shlex.quote(str(sf.python_exe_path))
            .replace('{', '{{')
            .replace('}', '}}')
        )
        + ' -m uv pip {} '
        + ' '.join(uv_pip_options)
    ).format

    uv_pip_list_options = (
        ' --format freeze'
        ' --exclude uv'
        ' --exclude pip'
        ' --no-index'
        ' --no-color'
    )

    with tempfile.TemporaryDirectory(prefix='n6_do_setup_') as tmp_dir:
        tmp_file = shlex.quote(f'{tmp_dir}/uv-pip-list.txt')
        sf.run_command(
            '/bin/bash',
            '-c',
            (
                f'{format_uv_pip("list")} {uv_pip_list_options} > {tmp_file} '
                f'&& '
                f'if [[ -s {tmp_file} ]]; then '
                f'{format_uv_pip("uninstall")} -r {tmp_file}; '
                f'fi'
            ),
        )
        sf.log_done_op('OK, uninstalled (almost) everything')


def update_basic_setup_tools(
    arguments: ParsedScriptArguments,
) -> None:
    maybe_no_cache_opt = ['--no-cache'] if arguments.no_cache else []
    install('--upgrade', *maybe_no_cache_opt, 'uv')
    install('--upgrade', *maybe_no_cache_opt, 'pip')
    sf.log_done_op(
        "OK, updated 'uv' and 'pip' (unless already up to date)",
    )


def install_packages(
    arguments: ParsedScriptArguments,
    *,
    just_dry_check: bool = False,
) -> None:
    maybe_dry_run_opt = ['--dry-run'] if just_dry_check else []
    maybe_no_cache_opt = ['--no-cache'] if arguments.no_cache else []
    maybe_compile_bytecode_opt = [] if arguments.never_compile_bytecode else ['--compile-bytecode']

    if requirements_install_args := list(generate_requirements_install_args(arguments)):
        install(
            *maybe_dry_run_opt,
            *(['--no-deps'] if sys.version_info[:2] >= (3, 11) else []),  # XXX: hack for Py3.9...
            *maybe_no_cache_opt,
            *maybe_compile_bytecode_opt,
            *generate_constraints_install_args(),
            *requirements_install_args,
        )
        if not just_dry_check:
            sf.log_done_op('OK, installed dependencies')

    if n6_packages_install_args := list(generate_n6_packages_install_args(arguments)):
        install(
            *maybe_dry_run_opt,
            '--no-deps',
            '--reinstall',
            *maybe_no_cache_opt,
            *([] if arguments.action == ACTION_DEV else maybe_compile_bytecode_opt),
            *n6_packages_install_args,
        )
        if not just_dry_check:
            sf.log_done_op(
                'OK, installed n6 stuff: %s (%s)',
                format_installed_n6_packages_listing(arguments),
                format_installed_n6_packages_endnote(arguments),
            )

    if arguments.additional_packages:
        install(
            *maybe_dry_run_opt,
            *maybe_no_cache_opt,
            *maybe_compile_bytecode_opt,
            *generate_constraints_install_args(),
            *arguments.additional_packages,
        )
        if not just_dry_check:
            sf.log_done_op(
                'OK, installed additional packages: %s',
                ', '.join(map(ascii, arguments.additional_packages)),
            )


def generate_requirements_install_args(
    arguments: ParsedScriptArguments,
) -> Iterator[str]:
    if arguments.n6_packages_but_no_requirements:
        return
    for n6_pkg_dirname in arguments.n6_packages:
        yield from generate_install_args_for_requirements_of_n6_pkg(
            arguments,
            n6_pkg_dirname,
        )


def generate_n6_packages_install_args(
    arguments: ParsedScriptArguments,
) -> Iterator[str]:
    if arguments.requirements_but_no_n6_packages:
        return
    for n6_pkg_dirname in arguments.n6_packages:
        yield from generate_install_args_for_n6_pkg(
            arguments,
            n6_pkg_dirname,
        )


def generate_constraints_install_args() -> Iterator[str]:
    for path in sf.all_core_constraints_paths:
        yield '-c'
        yield str(path)
    for path in sf.all_bc_constraints_paths:
        yield '-c'
        yield str(path)


def format_installed_n6_packages_listing(arguments):
    relative_specs = [
        '.' + (
            format_n6_pkg_spec(arguments, n6_pkg_dirname)
            .removeprefix(str(sf.top_dir_path))
        )
        for n6_pkg_dirname in arguments.n6_packages
    ]
    return ', '.join(map(ascii, relative_specs))


def format_installed_n6_packages_endnote(arguments):
    details = f"from {os.getcwd()!a}"
    if arguments.action == ACTION_DEV:
        details += ', in "editable" mode'
    return details


def generate_install_args_for_requirements_of_n6_pkg(
    arguments: ParsedScriptArguments,
    n6_pkg_dirname: str,
) -> Iterator[str]:
    yield '-r'
    yield format_basic_requirements_path(n6_pkg_dirname)
    for extra in get_extras_for_n6_pkg(arguments, n6_pkg_dirname):
        yield '-r'
        yield format_extra_requirements_path(n6_pkg_dirname, extra)


def format_basic_requirements_path(
    n6_pkg_dirname: str,
) -> str:
    return str(
        sf.top_dir_path /
        n6_pkg_dirname /
        PER_PACKAGE_BASIC_REQUIREMENTS_FILENAME
    )


def format_extra_requirements_path(
    n6_pkg_dirname: str,
    extra: str,
) -> str:
    return str(
        sf.top_dir_path /
        n6_pkg_dirname /
        PER_PACKAGE_EXTRA_REQUIREMENTS_FILENAME_FMT.format(extra=extra)
    )


def generate_install_args_for_n6_pkg(
    arguments: ParsedScriptArguments,
    n6_pkg_dirname: str,
) -> Iterator[str]:
    if arguments.action == ACTION_DEV:
        yield '-e'
    yield format_n6_pkg_spec(arguments, n6_pkg_dirname)


def format_n6_pkg_spec(
    arguments: ParsedScriptArguments,
    n6_pkg_dirname: str,
) -> str:
    pkg_spec = str(sf.top_dir_path / n6_pkg_dirname)
    if extras := get_extras_for_n6_pkg(arguments, n6_pkg_dirname):
        pkg_spec = f"{pkg_spec}[{','.join(extras)}]"
    return pkg_spec


def get_extras_for_n6_pkg(
    arguments: ParsedScriptArguments,
    n6_pkg_dirname: str,
) -> Sequence[str]:
    return sorted(
        sf.n6_pkg_to_extras[n6_pkg_dirname] & set(arguments.n6_package_extras),
    )


def install(*install_args: Union[str, PurePosixPath]) -> None:
    sf.run_command(
        sf.python_exe_path,
        '-m',
        'uv',
        'pip',
        'install',
        '--strict',
        *UV_PIP_CONSTANT_OPTIONS,
        *install_args,
    )


def check_packages(arguments: ParsedScriptArguments) -> None:
    options = list(UV_PIP_CONSTANT_OPTIONS)
    if arguments.no_cache:
        options.append('--no-cache')

    sf.run_command(
        sf.python_exe_path,
        '-m',
        'uv',
        'pip',
        'check',
        *options,
    )


if __name__ == '__main__':
    main()
