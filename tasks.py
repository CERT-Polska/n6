# Copyright (c) 2025 NASK. All rights reserved.

"""
This is the *n6*'s *[Invoke](https://www.pyinvoke.org/) tasks* file.
It defines a handful of *n6*-development-related *tasks*.

To make use of it, you need to install *n6* in the development mode,
e.g., by executing:

    cd n6  # <- your local *n6* source code directory
    python3.11 -m venv my-n6-venv
    source my-n6-venv/bin/activate
    ./do_setup.py -U -u --dev all

Then you can list the available tasks by executing the command:

    inv --list

You can also learn more about particular tasks by executing:

    inv <task name> --help

See also:
  * https://docs.pyinvoke.org/en/stable/
  * the `invoke.yaml` file in the root *n6* source code directory.
"""

from __future__ import annotations

import contextlib
import functools
import importlib.metadata
import shlex
import string
import sys
import tempfile
from collections.abc import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Set,
)
from pathlib import (
    PosixPath,
    PurePosixPath,
)
from types import SimpleNamespace
from typing import (
    Any,
    LiteralString,
    NoReturn,
    TypeAlias,
    assert_never,
)

from invoke import (
    Context,
    Exit,
    UnexpectedExit,
    task,
)
from packaging.requirements import Requirement
from packaging.utils import (
    NormalizedName,
    canonicalize_name,
)

import do_setup


#
# Auxiliary typing stuff
#


InstallKind: TypeAlias = (
    str |  # Either an *extra* str, as from _get_all_n6_package_extras(),
    None   # or None denoting the *production* kind of installation.
)


#
# Auxiliary constants
#


EXTRA_DEV = do_setup.EXTRA_DEV

class StaticallyKnownInstallKind:
    PROD: InstallKind = None
    DEV: InstallKind = EXTRA_DEV

ALL_CORE_REQUIREMENTS_DIRNAME = (
    do_setup.ALL_CORE_REQUIREMENTS_DIRNAME
)
ALL_BONUS_COMPANIONS_REQUIREMENTS_DIRNAME_GLOB_PATTERN = (
    do_setup.ALL_BONUS_COMPANIONS_REQUIREMENTS_DIRNAME_GLOB_PATTERN
)
ALL_REQUIREMENTS_FILENAME = do_setup.ALL_REQUIREMENTS_FILENAME
MANUAL_CONSTRAINTS_FILENAME = do_setup.MANUAL_CONSTRAINTS_FILENAME
PYPROJECT_FILENAME = do_setup.PYPROJECT_FILENAME

N6_PKG_REQUIREMENTS_FILENAME_FMT = 'requirements{}.txt'
N6_PKG_INPUT_DEPS_FILENAME_FMT = 'pyproject-derived{}.in'

N6_PKG_REQUIREMENTS_FILENAME_GLOB_PATTERN = N6_PKG_REQUIREMENTS_FILENAME_FMT.format('*')

VENV_ACTIVATE_SCRIPT_COMPLETION_PART_START_MARKER = (
    b"# Added by *n6*'s task 'add-completion-to-venv':"
)

UV_PIP_CONSTANT_OPTIONS = [
    '--no-config',
    '--no-python-downloads',
]

PYTEST_DOCTEST_OPT = '--doctest-modules'


#
# Actual task definitions
#


@task(
    help={
        "shell": "The shell name: 'bash' (default) or any other supported by *Invoke*.",
    },
)
def add_completion_to_venv(
    c: Context,
    shell: str = 'bash',
) -> None:
    """
    Enrich venv's 'activate' with shell completion for our *Invoke* tasks

    (for the 'bash' shell, or another shell specified with `--shell`,
    provided that the *Invoke*'s completion mechanism supports it). If
    the venv's 'activate' script (or, e.g., 'activate.fish', depending
    on the specified shell...) has already been enriched, the relevant
    fragment of it is overwritten.

    The enrichment is applied to the currently used venv. Note: you will
    *not* be able to make use of the completion mechanism immediately,
    but only *from the next activation* of the venv.
    """
    _info_on_venv_detection(c)

    with _top_dir_as_cwd(c):
        _intent("enrich the current venv's activation script")

        shell_name = PurePosixPath(shell).name  # (e.g. '/bin/bash' -> 'bash')
        completion_script_content = _obtain_completion_script_content(c, shell_name)
        venv_script_name = _guess_venv_script_name(shell_name)
        venv_script_path = _get_venv_script_path(venv_script_name)
        _enrich_venv_script(c, venv_script_path, completion_script_content)

        _success(
            c,
            (
                f"successfully enriched the venv's activation "
                f"script {str(venv_script_path)!a}, by adding to "
                f"it a {shell_name!a}-specific completion stuff "
                f"for our (*n6*-dedicated) *Invoke* tasks"
            ),
        )


@task
def delete_pycs(
    c: Context,
) -> None:
    """
    Delete all cached Python bytecode (`*.pyc`) files

    (more precisely: all `*.pyc` files being ordinary files as well as
    all `__pycache__` directories, in your local *n6*'s source code
    top-level directory and, recursively, in all its subdirectories;
    if a directory cannot be traversed or a file/directory cannot be
    deleted, only a warning is printed by the underlying 'find' command,
    but the entire task is still considered successful).
    """
    with _top_dir_as_cwd(c) as top_dir:
        _intent(
            f"delete any cached Python bytecode "
            f"stuff beneath {str(top_dir)!a}",
        )

        c.run(
            "( find . -type f -name '*.pyc' -delete"
            "; find . -type d -name '__pycache__' -delete"
            "; true )",
        )

        _success(
            c,
            (
                "deleted local `**/*.pyc` files and `**/__pycache__` "
                "directories (if any deletable ones existed)"
            ),
        )


@task(
    pre=[delete_pycs],
    aliases=['test', 'tests'],
    help={
        'doctests': (
            f"Shall also doctests be run, i.e., shall the "
            f"`{PYTEST_DOCTEST_OPT}` option be passed to "
            f"'pytest'? (default: yes)"
        ),
        'pytest_args': (
            "Any extra command-line arguments to 'pytest' "
            "(typically, they need to be quoted as a whole, "
            "to form a single STRING)."
        ),
        'tasks_module_doctests': (
            "Before the main test suite, run also "
            "the \"tasks.py\"'s own doctests."
        ),
    },
)
def pytest(
    c: Context,
    doctests: str = True,
    pytest_args: str = '',
    tasks_module_doctests: bool = False,
) -> None:
    """
    Run tests for the currently installed *n6* packages, using *pytest*

    (in the currently used venv; optionally, with additional *pytest*
    command-line arguments, if you specify `--pytest-args`...).

    It should be emphasized that (at least for now) only unit tests and
    doctests are run.

    Note: before the start of this task, the 'delete-pycs' task is invoked
    automatically.
    """
    _info_on_venv_detection(c)
    quo = _make_commandline_arg_quoter(c)

    with _top_dir_as_cwd(c):
        if tasks_module_doctests:
            _intent("run \"tasks.py\"'s doctests (using *pytest*)")
            c.run(
                (
                    f"{quo(_python_exe_path())}"
                    f" -m pytest"
                    f" {quo(PYTEST_DOCTEST_OPT)}"
                    f" tasks.py"
                ),
                pty=True,
            )
            _success(
                c,
                f"successfully ran \"tasks.py\"'s doctests (using *pytest*)"
            )

        if installed_n6_package_dirnames := _list_installed_n6_package_dirnames():
            _intent("test all installed *n6* packages (using *pytest*)")

            _verify_shell_safe(installed_n6_package_dirnames)
            all_pytest_args = []
            if doctests:
                all_pytest_args.append(PYTEST_DOCTEST_OPT)
            if pytest_args:
                all_pytest_args.extend(_split_commandline_args(c, pytest_args))
            all_pytest_args.extend(installed_n6_package_dirnames)
            assert all_pytest_args

            all_pytest_args_part = ' '.join(map(quo, all_pytest_args))
            c.run(
                (
                    f"{quo(_python_exe_path())}"
                    f" -m pytest"
                    f" {all_pytest_args_part}"
                ),
                pty=True,
            )

            _success(
                c,
                (
                    f"successfully ran tests (using *pytest*) for: "
                    f"{', '.join(map(ascii, installed_n6_package_dirnames))}"
                ),
            )
        else:
            _warning("no *n6* packages installed, nothing to test")


@task(
    iterable=['upgrade_package'],
    help={
        'upgrade': "Upgrade all packages (respecting any `--upgrade-package` constraints).",
        'upgrade_package': (
            "The name of a package to be upgraded/constrained, alone "
            "or with some version specification(s). You can use this "
            "option multiple times (referring to multiple packages)."
        ),
    },
)
def regen_requirements(
    c: Context,
    *,
    upgrade: bool = False,
    upgrade_package: list[str],
) -> None:
    """
    Maintain and regenerate ("compile") all *n6*'s `requirements*.txt` files

    (typically, you will want to commit the resultant file modifications,
    additions and deletions).

    By default, locked versions of packages *are not changed* at all. To
    upgrade (all or some of) them, you need to specify the `--upgrade`
    and/or `--upgrade-package` option(s). Read more on their semantics:
    https://pip-tools.readthedocs.io/en/stable/#updating-requirements
    and https://docs.astral.sh/uv/pip/compile/#upgrading-requirements
    (the main parts of this task just run 'uv pip compile' with suitable
    arguments...).

    If you recently added/removed some *optional dependencies* (aka
    *extras*) to/from any *n6* packages' 'pyproject.toml' files, this
    task may create or delete the corresponding `requirements-*.txt`
    files, as needed.

    Note: in any case, nothing in the currently used venv is modified,
    i.e., no *n6* packages or their dependencies are [un]installed or
    {up,down}graded. To do so, either invoke the 'sync-dev' task (for
    a development-only installation/update) or use the 'do_setup.py'
    script, as appropriate...
    """
    _info_on_venv_detection(c)

    explicit_upgrade_req_spec_and_name_pairs: Sequence[tuple[str, NormalizedName]] = list(
        _generate_explicit_upgrade_req_spec_and_name_pairs(upgrade_package),
    )
    all_core_requirements_dir = PosixPath(ALL_CORE_REQUIREMENTS_DIRNAME)
    all_bc_requirements_dir = _get_all_bc_requirements_dir_or_none()

    with (
        _top_dir_as_cwd(c),
        _temporary_input_deps_files(c) as (
            core_input_deps_paths,
            bc_input_deps_paths,
        ),
    ):
        _intent(
            "perform maintenance and [re]generation "
            "of `requirements*.txt` files",
        )

        _verify_no_unrelated_packages_specified(
            explicit_upgrade_req_spec_and_name_pairs,
        )

        compiled_n6_package_requirements_file_paths = set()

        # * For n6 *core* packages:

        all_core_requirements_path = all_core_requirements_dir / ALL_REQUIREMENTS_FILENAME
        _compile_all_requirements_file(
            c,
            upgrade,
            explicit_upgrade_req_spec_and_name_pairs,
            all_external_req_names=_get_all_external_req_names(only_core=True),
            input_deps_paths=sorted(core_input_deps_paths),
            constraint_paths=[
                all_core_requirements_dir / MANUAL_CONSTRAINTS_FILENAME,
            ],
            target_file_path=all_core_requirements_path,
        )

        for core_dirname in _list_n6_package_dirnames(only_core=True):
            core_dir = PosixPath(core_dirname)
            for kind in _list_install_kinds():
                core_target_file_path = core_dir / _get_n6_pkg_requirements_filename(kind)
                core_input_deps_file_path = core_dir / _get_n6_pkg_input_deps_filename(kind)
                if core_input_deps_file_path in core_input_deps_paths:
                    _compile_requirements_file_for_n6_pkg_and_kind(
                        c,
                        target_file_path=core_target_file_path,
                        n6_pkg_input_deps_path=core_input_deps_file_path,
                        constraint_paths=[
                            all_core_requirements_path,
                        ],
                    )
                    compiled_n6_package_requirements_file_paths.add(core_target_file_path)

        # * For n6 *bonus companion* packages (if any):

        if all_bc_requirements_dir is None:
            assert not bc_input_deps_paths
        else:
            all_bc_requirements_path = all_bc_requirements_dir / ALL_REQUIREMENTS_FILENAME
            _compile_all_requirements_file(
                c,
                upgrade,
                explicit_upgrade_req_spec_and_name_pairs,
                all_external_req_names=_get_all_external_req_names(only_bc=True),
                input_deps_paths=sorted(bc_input_deps_paths),
                constraint_paths=[
                    all_core_requirements_path,
                    all_bc_requirements_dir / MANUAL_CONSTRAINTS_FILENAME,
                ],
                target_file_path=all_bc_requirements_path,
            )

            for bc_dirname in _list_n6_package_dirnames(only_bc=True):
                bc_dir = PosixPath(bc_dirname)
                for kind in _list_install_kinds():
                    bc_target_file_path = bc_dir / _get_n6_pkg_requirements_filename(kind)
                    bc_input_deps_file_path = bc_dir / _get_n6_pkg_input_deps_filename(kind)
                    if bc_input_deps_file_path in bc_input_deps_paths:
                        _compile_requirements_file_for_n6_pkg_and_kind(
                            c,
                            target_file_path=bc_target_file_path,
                            n6_pkg_input_deps_path=bc_input_deps_file_path,
                            constraint_paths=[
                                all_core_requirements_path,
                                all_bc_requirements_path,
                            ],
                        )
                        compiled_n6_package_requirements_file_paths.add(bc_target_file_path)

        # * Get rid of any removed *extra*'s requirements files:

        for unneeded_file_path in _find_no_longer_compiled_n6_package_requirements_file_paths(
            compiled_n6_package_requirements_file_paths,
        ):
            _ensure_unneeded_file_is_deleted(c, unneeded_file_path)

        _success(
            c,
            (
                "finished maintenance and [re]generation "
                "of `requirements*.txt` files"
            ),
        )


@task(
    aliases=['dev_sync'],
    pre=[delete_pycs],
)
def sync_dev(
    c: Context,
) -> None:
    """
    Update venv to reflect requirements and install *n6*, in 'dev' manner

    (under the hood, the 'uv pip sync' command is used to adequately
    [un]install and/or {up,down}grade dependencies, including the 'dev'
    ones, to make them accordant with the contents of the suitable
    `requirements*.txt` files; then all *n6* packages are installed,
    using 'uv pip install', in the "editable" mode; all this is done
    in the currently used venv).

    The point of this task is developer convenience. The task should not
    be used for any *production* or *CI/tests* installation; for any such
    stuff, use the 'do_setup.py' script, as appropriate...

    Note: before the start of this task, the 'delete-pycs' task is invoked
    automatically.
    """
    _info_on_venv_detection(c)
    quo = _make_commandline_arg_quoter(c)

    all_requirements_dirs = [PosixPath(ALL_CORE_REQUIREMENTS_DIRNAME)]
    if all_bc_requiements_dir := _get_all_bc_requirements_dir_or_none():
        all_requirements_dirs.append(all_bc_requiements_dir)

    with _top_dir_as_cwd(c):
        constraint_opts_part = ' '.join(
            _generate_constraint_opts(
                c,
                constraint_paths=[
                    req_dir / filename
                    for req_dir in all_requirements_dirs
                    for filename in [
                        ALL_REQUIREMENTS_FILENAME,
                        MANUAL_CONSTRAINTS_FILENAME,
                    ]
                ],
            ),
        )
        requirements_part = ' '.join(
            quo(PosixPath(n6_pkg_dirname) / _get_n6_pkg_requirements_filename(kind))
            for n6_pkg_dirname in _list_n6_package_dirnames()
            for kind in [
                StaticallyKnownInstallKind.PROD,
                StaticallyKnownInstallKind.DEV,
            ]
        )
        editable_opts_part = ' '.join(
            f"-e {quo(f'{n6_pkg_dirname}[{EXTRA_DEV}]')}"
            for n6_pkg_dirname in _list_n6_package_dirnames()
        )

        _intent(
            "[un]install and {up,down}grade *n6*'s dependencies, as needed",
        )
        c.run(
            (
                f"{_uv_pip(c, 'sync')}"
                f" {constraint_opts_part}"
                f" --"
                f" {requirements_part}"
            ),
            pty=True,
        )

        _intent(
            'install all *n6* packages (in the "editable" mode)',
        )
        c.run(
            (
                f"{_uv_pip(c, 'install')}"
                f" --no-deps"
                f" {editable_opts_part}"
            ),
            pty=True,
        )

        _intent(
            "check consistency of all packages "
            "installed in the current venv",
        )
        c.run(
            f"{_uv_pip(c, 'check')}",
            pty=True,
        )

        _success(
            c,
            (
                f'successfully installed all *n6* packages '
                f'(in the "editable" mode), together with '
                f'the necessary dependencies (including '
                f'the {EXTRA_DEV!a} optional dependencies)'
            ),
        )


#
# Internal helpers
#


#
# `add_completion_to_venv()`-related helpers


def _obtain_completion_script_content(
    c: Context,
    shell_name: str,
) -> bytes:
    quo = _make_commandline_arg_quoter(c)
    _verify_shell_safe(shell_name, what='shell name')

    with _temporary_file() as tmp_path:
        try:
            c.run(
                f"invoke --print-completion-script {quo(shell_name)} "
                f"> {quo(tmp_path)}",
            )
        except UnexpectedExit as exc:
            _error(
                (
                    f"Failed to obtain the completion script "
                    f"appropriate for the {shell_name!a} shell!"
                ),
                exc=exc,
            )
        completion_script_content = tmp_path.read_bytes()

    if c.config.run.dry:
        assert not completion_script_content
    elif not completion_script_content:
        _error("Something wrong: the obtained completion script has no content!")

    _success(
        c,
        f"obtained the completion script appropriate for the {shell_name!a} shell",
    )
    return completion_script_content


def _guess_venv_script_name(shell_name: str) -> str:
    match shell_name:
        case 'csh':
            return 'activate.csh'
        case 'fish':
            return 'activate.fish'
        case _:
            return 'activate'


def _get_venv_script_path(venv_script_name: str) -> PosixPath:
    venv_script_path = _venv_path() / 'bin' / venv_script_name
    _verify_venv_script_readable_and_writable(venv_script_path)
    return venv_script_path


def _verify_venv_script_readable_and_writable(venv_script_path: PosixPath) -> None:
    try:
        venv_script_path.open('r+b').close()
    except OSError as exc:
        _error(
            f"A problem with accessing the venv activation "
            f"script file {str(venv_script_path)!a}! ({exc})",
            exc=exc,
        )


def _enrich_venv_script(
    c: Context,
    venv_script_path: PosixPath,
    completion_script_content: bytes,
) -> None:
    quo = _make_commandline_arg_quoter(c)
    tmp_copy_path = venv_script_path.with_name(venv_script_path.name + '--N6-TEMPORARY-FILE')
    try:
        c.run(f"cp -a -- {quo(venv_script_path)} {quo(tmp_copy_path)}")
        if not c.config.run.dry:
            orig_venv_script_content = _get_orig_venv_script_content(tmp_copy_path)
            _save_enriched_venv_script_content(
                c,
                orig_venv_script_content,
                completion_script_content,
                target=tmp_copy_path,
            )
        _success(c, "obtained the venv activation script's enriched content")
        c.run(f"mv -- {quo(tmp_copy_path)} {quo(venv_script_path)}")
    finally:
        c.run(f"rm -f -- {quo(tmp_copy_path)}")


def _get_orig_venv_script_content(source: PosixPath) -> bytes:
    content = source.read_bytes()
    try:
        i = content.index(VENV_ACTIVATE_SCRIPT_COMPLETION_PART_START_MARKER)
    except ValueError:
        return content
    else:
        return content[:i]


def _save_enriched_venv_script_content(
    c: Context,
    orig_venv_script_content: bytes,
    completion_script_content: bytes,
    *,
    target: PosixPath,
) -> None:
    assert not c.config.run.dry
    with target.open('wb') as f:
        f.write(orig_venv_script_content.rstrip(b'\n'))
        f.write(b'\n\n\n\n')
        f.write(VENV_ACTIVATE_SCRIPT_COMPLETION_PART_START_MARKER)
        f.write(b'\n\n\n\n')
        f.write(completion_script_content)


#
# `compile_requirements()`-and-`sync_dev()`-related helpers


def _generate_explicit_upgrade_req_spec_and_name_pairs(
    upgrade_package: Sequence[str],
) -> Iterator[tuple[str, NormalizedName]]:
    for req_spec in upgrade_package:
        try:
            req_name = _get_req_normalized_name(req_spec)
            if req_name.startswith('n6'):
                raise ValueError(
                    'n6 packages cannot be passed to `--upgrade-package`',
                )
        except ValueError as exc:
            _error(
                f"A problem with `--upgrade-package={req_spec!a}` ({exc}).",
                code=2,
                exc=exc,
            )
        yield req_spec, req_name


def _get_all_bc_requirements_dir_or_none() -> PosixPath | None:
    top_dir = _get_top_dir()
    dirname_glob_pattern = ALL_BONUS_COMPANIONS_REQUIREMENTS_DIRNAME_GLOB_PATTERN

    if found_paths := list(top_dir.glob(dirname_glob_pattern)):
        paths = [p.relative_to(top_dir) for p in found_paths]
        try:
            [bc_req_path] = paths
        except ValueError as exc:
            _error(
                (
                    f"Only one *bonus companions' all-requirements "
                    f"directory* is supported (at least for now...), "
                    f"but found {len(paths)} such directories: "
                    f"{', '.join(ascii(str(p)) for p in paths)}."
                ),
                exc=exc,
            )
    elif bc_dirnames := _list_n6_package_dirnames(only_bc=True):
        _error(
            f"Missing *bonus companions' all-requirements directory* "
            f"(given that some n6 *bonus companion* packages do exist: "
            f"{', '.join(map(ascii, bc_dirnames))})."
        )
    else:
        bc_req_path = None

    assert bc_req_path is None or not bc_req_path.is_absolute()
    return bc_req_path


@contextlib.contextmanager
def _temporary_input_deps_files(c: Context) -> Generator[
    tuple[
        Set[PosixPath],
        Set[PosixPath],
    ]
]:
    quo = _make_commandline_arg_quoter(c)
    top_dir = _get_top_dir()

    core_input_deps_paths = set()
    bc_input_deps_paths = set()

    def make_input_deps_files_for_n6_pkg(input_deps_paths, n6_pkg_dirname):
        for kind in _list_install_kinds():
            path = PosixPath(n6_pkg_dirname) / _get_n6_pkg_input_deps_filename(kind)
            path_abs = top_dir / path
            if _does_file_exist(path_abs):
                _warning(
                    f"the file {str(path_abs)!a} exists, and that is "
                    f"unexpected. It needs to be deleted, before it "
                    f"is created from scratch",
                )
                c.run(f"rm -f -- {quo(path_abs)}")
                _success(c, f"deleted the file {str(path_abs)!a}")

            req_strings = sorted(
                str(req)
                for req in _get_kind_specific_reqs_from_n6_pkg_pyproject_file(
                    n6_pkg_dirname,
                    kind,
                )
            )
            if req_strings:
                input_deps_paths.add(path)
                if not c.config.run.dry:
                    with path_abs.open('xt') as f:
                        f.write('\n'.join(req_strings))

    try:
        for core_dirname in _list_n6_package_dirnames(only_core=True):
            make_input_deps_files_for_n6_pkg(core_input_deps_paths, core_dirname)
        for bc_dirname in _list_n6_package_dirnames(only_bc=True):
            make_input_deps_files_for_n6_pkg(bc_input_deps_paths, bc_dirname)

        assert not any(p.is_absolute() for p in core_input_deps_paths)
        assert not any(p.is_absolute() for p in bc_input_deps_paths)

        yield (
            core_input_deps_paths,
            bc_input_deps_paths,
        )

    finally:
        for p in sorted(core_input_deps_paths | bc_input_deps_paths):
            c.run(f"rm -f -- {quo(top_dir / p)}")


def _verify_no_unrelated_packages_specified(
    explicit_upgrade_req_spec_and_name_pairs: Sequence[tuple[str, NormalizedName]],
) -> None:
    all_core_and_bc_external_req_names = _get_all_external_req_names()
    if unrelated_req_specs := [
        req_spec
        for req_spec, req_name in explicit_upgrade_req_spec_and_name_pairs
        if req_name not in all_core_and_bc_external_req_names
    ]:
        _error(
            (
                f"The following `--upgrade-package` values are *not* "
                f"our requirements for any kind of *n6* installation: "
                f"{', '.join(map(ascii, unrelated_req_specs))}."
            ),
            code=2,
        )


def _get_all_external_req_names(
    *,
    only_core: bool = False,
    only_bc: bool = False,
) -> Set[NormalizedName]:
    return _get_all_req_names_from_n6_pkg_pyproject_files(
        only_core=only_core,
        only_bc=only_bc,
    ) | _get_all_req_names_from_n6_pkg_requirements_files(
        only_core=only_core,
        only_bc=only_bc,
    )


def _get_all_req_names_from_n6_pkg_pyproject_files(
    *,
    only_core: bool = False,
    only_bc: bool = False,
) -> Set[NormalizedName]:
    return {
        req_name
        for n6_pkg_dirname in _list_n6_package_dirnames(only_core=only_core, only_bc=only_bc)
        for kind in _list_install_kinds()
        for req_name in _iter_kind_specific_req_names_from_n6_pkg_pyproject_file(
            n6_pkg_dirname,
            kind,
        )
    }


def _iter_kind_specific_req_names_from_n6_pkg_pyproject_file(
    n6_pkg_dirname: str,
    kind: InstallKind,
) -> Iterator[NormalizedName]:
    return map(
        _get_req_normalized_name,
        _get_kind_specific_reqs_from_n6_pkg_pyproject_file(n6_pkg_dirname, kind),
    )


def _get_kind_specific_reqs_from_n6_pkg_pyproject_file(
    n6_pkg_dirname: str,
    kind: InstallKind,
) -> Set[Requirement]:
    project_config: Mapping[str, Any] = _get_parsed_pyproject(n6_pkg_dirname)['project']
    direct_req_specs: list[str]
    if kind is None:
        direct_req_specs = project_config['dependencies'].copy()
    elif found_req_specs := project_config['optional-dependencies'].get(kind):
        direct_req_specs = found_req_specs.copy()
    else:
        direct_req_specs = []
    return {
        req
        for req in map(_get_requirement, direct_req_specs)
        if not _get_req_normalized_name(req).startswith('n6')
    }


def _get_all_req_names_from_n6_pkg_requirements_files(
    *,
    only_core: bool = False,
    only_bc: bool = False,
) -> Set[NormalizedName]:
    return {
        req_name
        for n6_pkg_dirname in _list_n6_package_dirnames(only_core=only_core, only_bc=only_bc)
        for kind in _list_install_kinds()
        for req_name in _iter_kind_specific_req_names_from_n6_pkg_requirements_file_if_any(
            n6_pkg_dirname,
            kind,
        )
    }


def _iter_kind_specific_req_names_from_n6_pkg_requirements_file_if_any(
    n6_pkg_dirname: str,
    kind: InstallKind,
) -> Iterator[NormalizedName]:
    requirements_path = _get_top_dir() / n6_pkg_dirname / _get_n6_pkg_requirements_filename(kind)
    return map(
        _get_req_normalized_name,
        _iter_reqs_from_requirements_file_if_any(requirements_path),
    )


def _iter_reqs_from_requirements_file_if_any(
    requirements_path: PosixPath,
) -> Iterator[Requirement]:
    # Note: `@functools.cache` should not be used here, because the
    # "requirement*.txt" files may be modified during execution of a
    # single `invoke ...` command.
    try:
        requirements_file_content = requirements_path.read_bytes()
    except FileNotFoundError:
        return
    for lineno, line in enumerate(requirements_file_content.splitlines(), start=1):
        if line[:1].strip() in (b"", b"#"):
            continue
        try:
            req_raw_spec, *rest = line.split(b" ")
            if rest != [b"\\"]:
                raise ValueError(
                    "each line which is not blank or comment-only "
                    "should contain just a requirement spec in "
                    "the NAME==VERSION format, and a backslash",
                )
            yield _get_requirement(req_raw_spec.decode("ascii"))
        except ValueError as exc:
            _error(
                f"Unexpected line (#{lineno}) in {str(requirements_path)!a}: "
                f"{ascii(line)[1:]} ({exc}).",
            )


def _get_req_normalized_name(
    req_or_spec: str | Requirement,
    /,
) -> NormalizedName:
    req = _get_requirement(req_or_spec)
    return canonicalize_name(req.name)


def _get_requirement(
    req_or_spec: str | Requirement,
    /,
) -> Requirement:
    match req_or_spec:
        case Requirement():
            req = req_or_spec
        case str():
            req = Requirement(req_or_spec)
        case wrong:
            assert_never(wrong)
    return req


def _get_n6_pkg_requirements_filename(kind: InstallKind) -> str:
    return N6_PKG_REQUIREMENTS_FILENAME_FMT.format(
        _get_kind_specific_filename_stem_suffix(kind)
    )


def _get_n6_pkg_input_deps_filename(kind: InstallKind) -> str:
    return N6_PKG_INPUT_DEPS_FILENAME_FMT.format(
        _get_kind_specific_filename_stem_suffix(kind)
    )


def _get_kind_specific_filename_stem_suffix(kind: InstallKind) -> str:
    match kind:
        case StaticallyKnownInstallKind.PROD:
            stem_suffix = ''
        case extra if extra in _get_all_n6_package_extras():
            stem_suffix = f'-{extra}'
        case wrong:
            assert_never(wrong)
    return stem_suffix


def _compile_all_requirements_file(
    c: Context,
    upgrade: bool,
    explicit_upgrade_req_spec_and_name_pairs: Sequence[tuple[str, NormalizedName]],
    *,
    all_external_req_names: Set[NormalizedName],
    input_deps_paths: Sequence[PosixPath],
    constraint_paths: Sequence[PosixPath],
    target_file_path: PosixPath,
) -> None:
    assert not any(p.is_absolute() for p in input_deps_paths)
    assert not any(p.is_absolute() for p in constraint_paths)
    assert not target_file_path.is_absolute()

    quo = _make_commandline_arg_quoter(c)
    upgrade_req_specs = [
        req_spec
        for req_spec, req_name in explicit_upgrade_req_spec_and_name_pairs
        if req_name in all_external_req_names
    ]
    upgrade_opts_part = ' '.join(
        _generate_upgrade_opts(
            c,
            upgrade=upgrade,
            upgrade_req_specs=upgrade_req_specs,
        ),
    )
    constraint_opts_part = ' '.join(
        _generate_constraint_opts(
            c,
            constraint_paths,
        ),
    )
    input_deps_paths_part = ' '.join(map(quo, input_deps_paths))
    target_already_existed = _does_file_exist(target_file_path)

    _do_compile_requirements(
        c,
        target_file_path,
        upgrade_opts_part=upgrade_opts_part,
        constraint_opts_part=constraint_opts_part,
        input_deps_paths_part=input_deps_paths_part,
    )
    _success(
        c,
        _format_compile_requirements_success_msg(
            target_file_path,
            created=(not target_already_existed),
            upgrade=upgrade,
            upgrade_req_specs=upgrade_req_specs,
            constraint_paths=constraint_paths,
        ),
    )


def _compile_requirements_file_for_n6_pkg_and_kind(
    c: Context,
    *,
    target_file_path: PosixPath,
    n6_pkg_input_deps_path: PosixPath,
    constraint_paths: Sequence[PosixPath],
) -> None:
    assert not any(p.is_absolute() for p in constraint_paths)

    quo = _make_commandline_arg_quoter(c)
    constraint_opts_part = ' '.join(
        _generate_constraint_opts(
            c,
            constraint_paths,
        ),
    )
    target_already_existed = _does_file_exist(target_file_path)

    _do_compile_requirements(
        c,
        target_file_path,
        constraint_opts_part=constraint_opts_part,
        input_deps_paths_part=quo(n6_pkg_input_deps_path),
    )
    _success(
        c,
        _format_compile_requirements_success_msg(
            target_file_path,
            created=(not target_already_existed),
            constraint_paths=constraint_paths,
        ),
    )


def _generate_upgrade_opts(
    c: Context,
    *,
    upgrade: bool = False,
    upgrade_req_specs: Sequence[str] = (),
) -> Iterator[str]:
    quo = _make_commandline_arg_quoter(c)
    if upgrade:
        yield '--upgrade'
    for req_spec in upgrade_req_specs:
        yield f'--upgrade-package {quo(req_spec)}'


def _generate_constraint_opts(
    c: Context,
    constraint_paths: Sequence[PosixPath],
) -> Iterator[str]:
    quo = _make_commandline_arg_quoter(c)
    for constr_path in constraint_paths:
        yield f'-c {quo(constr_path)}'


def _do_compile_requirements(
    c: Context,
    target_file_path: PosixPath,
    *,
    upgrade_opts_part: str = '',
    constraint_opts_part: str,
    input_deps_paths_part: str,
):
    assert not target_file_path.is_absolute()
    quo = _make_commandline_arg_quoter(c)
    c.run(
        (
            f"{_uv_pip(c, 'compile')}"
            f" {upgrade_opts_part}"
            f" --refresh"
            f" --output-file {quo(target_file_path)}"
            f" {constraint_opts_part}"
            f" --generate-hashes"
            f" --strip-extras"
            f" --quiet"
            f" --"
            f" {input_deps_paths_part}"
        ),
        pty=True,
    )


def _format_compile_requirements_success_msg(
    target_file_path: PosixPath,
    *,
    created: bool,
    upgrade: bool = False,
    upgrade_req_specs: Sequence[str] = (),
    constraint_paths: Sequence[PosixPath] = (),
) -> str:
    op = 'created' if created else 'regenerated'
    msg = f'successfully {op} {str(target_file_path)!a}'
    if upgrade or upgrade_req_specs or constraint_paths:
        msg += ' (with'
        if upgrade:
            msg += ' `--upgrade`'
            if upgrade_req_specs and constraint_paths:
                msg += ','
            elif upgrade_req_specs or constraint_paths:
                msg += ' and'
        if upgrade_req_specs:
            msg += f' {len(upgrade_req_specs)} `--upgrade-package...`'
            if constraint_paths:
                msg += ' and'
        if constraint_paths:
            msg += f" `{' '.join(f'-c {str(p)!a}' for p in constraint_paths)}`"
        msg += ')'
    return msg


def _find_no_longer_compiled_n6_package_requirements_file_paths(
    compiled_n6_package_requirements_file_paths: Set[PosixPath],
):
    top_dir = _get_top_dir()
    looking_like = {
        path.relative_to(top_dir)
        for n6_pkg_dirname in _list_n6_package_dirnames()
        for path in (top_dir / n6_pkg_dirname).glob(N6_PKG_REQUIREMENTS_FILENAME_GLOB_PATTERN)
    }
    return sorted(
        looking_like - compiled_n6_package_requirements_file_paths,
    )


def _ensure_unneeded_file_is_deleted(
    c: Context,
    target_file_path: PosixPath,
) -> None:
    if _does_file_exist(target_file_path):
        quo = _make_commandline_arg_quoter(c)
        c.run(f"rm -- {quo(target_file_path)}")
        _success(c, f"deleted {str(target_file_path)!a} (no longer needed)")


#
# General-use helpers


def _info_on_venv_detection(c: Context) -> None:
    venv_path = _venv_path()
    _success(
        c,
        f'detected a venv: {str(venv_path)!a}',
        done_even_for_dry=True,
    )


@contextlib.contextmanager
def _top_dir_as_cwd(c: Context) -> Generator[PosixPath]:
    top_dir = _get_top_dir()
    with (
        contextlib.chdir(top_dir),
        c.cd(top_dir),
    ):
        yield top_dir


def _get_top_dir() -> PosixPath:
    top_dir = _get_do_setup_sf().top_dir_path
    assert top_dir.is_absolute()
    return top_dir


@contextlib.contextmanager
def _temporary_file(filename: str = 'data') -> Generator[PosixPath]:
    with tempfile.TemporaryDirectory(prefix='n6_invoke_tasks_') as tmp_dir:
        tmp_path = PosixPath(tmp_dir) / filename
        tmp_path.write_bytes(b'')
        _verify_shell_safe(tmp_path, what='temporary directory path')
        yield tmp_path


def _does_file_exist(path: PosixPath) -> bool:
    try:
        path.open().close()
    except FileNotFoundError:
        return False
    return True


def _intent(intended_operation_description: str) -> None:
    print(f"About to {intended_operation_description}...")
    sys.stdout.flush()


def _success(
    c: Context,
    successful_operation_description: str,
    *,
    done_even_for_dry: bool = False,
) -> None:
    print(f"OK, {successful_operation_description}.")
    if c.config.run.dry and not done_even_for_dry:
        print("(Well, actually not, because it is a *dry* run...)")
    sys.stdout.flush()


def _warning(warning_msg: str) -> None:
    sf = _get_do_setup_sf()
    sf.logger.warning(warning_msg)


def _error(
    error_msg: str,
    *,
    code: int = 1,
    exc: BaseException | None = None,
) -> NoReturn:
    exit_exc = Exit(f"ERROR! {error_msg}", code=code)
    if exc is None:
        raise exit_exc
    raise exit_exc from exc


def _make_commandline_arg_quoter(
    c: Context,
) -> Callable[[str | PurePosixPath], str]:
    _verify_invoke_uses_bash(c)

    def quo(obj: str | PurePosixPath) -> str:
        # Sanitize a text or a path (to be placed, as a single command-line
        # argument, within a command which will be run using `c.run()`).
        return shlex.quote(str(obj))

    return quo


def _split_commandline_args(
    c: Context,
    commandline_args: str,
) -> list[str]:
    _verify_invoke_uses_bash(c)

    assert isinstance(commandline_args, str), 'cmd-line args must be given as one string'
    if commandline_args:
        return shlex.split(str(commandline_args))
    return []


def _verify_invoke_uses_bash(c: Context) -> None:
    bin_bash = '/bin/bash'
    used_by_invoke = c.config.run.shell
    if used_by_invoke != bin_bash:
        _error(
            f"For the safety of shell syntax manipulation, we insist "
            f"that *invoke* itself uses the {bin_bash!a} shell! "
            f"(whereas actually it seems to use {used_by_invoke!a})",
        )


def _verify_shell_safe(
    obj: str | PurePosixPath | Iterable[str | PurePosixPath],
    *,
    what: str | None = None,
) -> None:
    if not isinstance(obj, (str, PurePosixPath)):
        if what is not None:
            what = f'item of {what}'
        for o in obj:
            _verify_shell_safe(o, what=what)
        return

    if what is None:
        what = 'path' if isinstance(obj, PurePosixPath) else 'string'

    # A simplistic and overstrict way to make sure that a text/path will
    # not give us any surprises in any shell-like context – as it just
    # consists of ASCII letters, digits, slashes, underscores, dots and
    # dashes, and does not start with a dot or dash.
    s = str(obj)
    illegal_chars = set(s) - set(string.ascii_letters + string.digits + '/_.-')
    if illegal_chars:
        _error(
            f"the {s!a} {what} contains unexpected characters! "
            f"({', '.join(map(ascii, sorted(illegal_chars)))})",
        )
    if s.startswith('.'):
        _error(
            f"the {s!a} {what} starts with the '.' character!",
        )
    if s.startswith('-'):
        _error(
            f"the {s!a} {what} starts with the '-' character!",
        )


def _uv_pip(
    c: Context,
    uv_pip_command: LiteralString,
) -> str:
    return (
        f"{_uv_invocation(c)}"
        f" pip {uv_pip_command}"
        f" {' '.join(UV_PIP_CONSTANT_OPTIONS)}"
    )


def _uv_invocation(c: Context) -> str:
    quo = _make_commandline_arg_quoter(c)
    return (
        f"{quo(_python_exe_path())}"
        f" -m uv"
    )


def _venv_path() -> PosixPath:
    venv_path = _get_do_setup_sf().virtual_environment_path
    assert venv_path.is_absolute()
    assert _python_exe_path().is_relative_to(venv_path)
    return venv_path


def _python_exe_path() -> PosixPath:
    python_exe_path = _get_do_setup_sf().python_exe_path
    assert python_exe_path.is_absolute()
    return python_exe_path


def _list_installed_n6_package_dirnames(
    *,
    only_core: bool = False,
    only_bc: bool = False,
):
    found_dirnames = _list_n6_package_dirnames(
        only_core=only_core,
        only_bc=only_bc,
    )
    return [
        n6_pkg_dirname
        for n6_pkg_dirname in found_dirnames
        if _is_n6_pkg_installed(n6_pkg_dirname)
    ]


def _is_n6_pkg_installed(n6_pkg_dirname: str) -> bool:
    n6_pkg_actual_name = canonicalize_name(
        _get_parsed_pyproject(n6_pkg_dirname)['project']['name'],
    )
    try:
        importlib.metadata.version(n6_pkg_actual_name)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def _list_n6_package_dirnames(
    *,
    only_core: bool = False,
    only_bc: bool = False,
) -> Sequence[str]:
    sf = _get_do_setup_sf()
    found_dirnames = sorted(
        n6_pkg_dirname
        for n6_pkg_dirname in sf.all_n6_packages
        if (
            ((n6_pkg_dirname not in sf.bc_to_core) if only_core else True)
            and ((n6_pkg_dirname in sf.bc_to_core) if only_bc else True)
        )
    )
    _verify_shell_safe(found_dirnames)
    return found_dirnames


def _get_parsed_pyproject(n6_pkg_dirname: str) -> Mapping[str, Any]:
    sf = _get_do_setup_sf()
    return sf.n6_pkg_to_pyproject[n6_pkg_dirname]


@functools.cache
def _list_install_kinds() -> Sequence[InstallKind]:
    install_kinds = [
        StaticallyKnownInstallKind.PROD,
        *sorted(
            _get_all_n6_package_extras(),
        ),
    ]
    assert set(install_kinds) >= {
        StaticallyKnownInstallKind.PROD,
        StaticallyKnownInstallKind.DEV,
    }
    assert all(
        (
            kind is None is StaticallyKnownInstallKind.PROD
            or (isinstance(kind, str) and kind.isascii() and kind.isalnum())
        )
        for kind in install_kinds
    )
    return install_kinds


@functools.cache
def _get_all_n6_package_extras() -> Set[str]:
    all_extras = _get_do_setup_sf().all_n6_package_extras
    assert EXTRA_DEV in all_extras
    assert all(
        isinstance(extra, str) and extra.isascii() and extra.isalnum()
        for extra in all_extras
    )
    return all_extras


@functools.cache
def _get_do_setup_sf() -> do_setup.SystemFacade:
    sf = do_setup.sf

    try:
        sf.load()
        sf.configure_logging(
            SimpleNamespace(
                log_config={
                    'version': 1,
                    'formatters': {
                        'simple': {'format': '%(levelname)s: %(message)s!'},
                    },
                    'handlers': {
                        'stderr': {
                            'class': 'logging.StreamHandler',
                            'formatter': 'simple',
                            'stream': 'ext://sys.stderr',
                        },
                    },
                    'root': {
                        'level': 'WARNING',
                        'handlers': ['stderr'],
                    },
                },
            ),
        )
    except (Exception, SystemExit) as exc:
        _error(
            (
                f"{type(exc).__qualname__} from `do_setup` module! "
                f"({str(exc).removeprefix('fatal error: ')})"
            ),
            exc=exc,
        )

    this_module_resolved_parent = PosixPath(__file__).parent.resolve(strict=True)
    if sf.top_dir_path != this_module_resolved_parent:
        raise AssertionError(
            f'{sf.top_dir_path=} does not match {this_module_resolved_parent=}',
        )

    return sf
