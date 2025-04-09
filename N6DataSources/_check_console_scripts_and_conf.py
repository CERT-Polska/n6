# Copyright (c) 2023-2025 NASK. All rights reserved.

"""
A quick-and-dirty helper script to detect discrepancies between the
existing collector/parser modules+classes and the contents of:

* the `N6DataSources/console_scripts` file,
* the `etc/n6/60_*.conf` files.
"""

import collections
import dataclasses
import functools
import importlib
import operator
import pathlib
import pkgutil
import re
import sys
from collections.abc import (
    Generator,
    Iterator,
    Sequence,
)
from types import (
    FunctionType as Function,
    MethodType as BoundMethod,
)

from n6lib.class_helpers import all_subclasses
from n6lib.common_helpers import (
    OPSet,
    memoized,
)
from n6lib.config import Config


#
# Constants

NP_MARK = 'nonpub'

N6DATASOURCES_TOPLEVEL_DIR_PATH = pathlib.Path(__file__).resolve(strict=True).parent
assert NP_MARK not in str(N6DATASOURCES_TOPLEVEL_DIR_PATH)
assert N6DATASOURCES_TOPLEVEL_DIR_PATH.is_absolute()
assert N6DATASOURCES_TOPLEVEL_DIR_PATH.is_dir()
assert N6DATASOURCES_TOPLEVEL_DIR_PATH.name == 'N6DataSources'

CONSOLE_SCRIPTS_PATH = N6DATASOURCES_TOPLEVEL_DIR_PATH / 'console_scripts'
assert NP_MARK not in str(CONSOLE_SCRIPTS_PATH)
assert CONSOLE_SCRIPTS_PATH.is_absolute()

CONFIG_DIR_PATH = N6DATASOURCES_TOPLEVEL_DIR_PATH.parent / 'etc' / 'n6'
assert NP_MARK not in str(CONFIG_DIR_PATH)
assert CONFIG_DIR_PATH.is_absolute()
assert CONFIG_DIR_PATH.is_dir()
CONFIG_FILENAME_PREFIX = '60_'
CONFIG_FILENAME_SUFFIX = '.conf'
CONFIG_SECTION_REGEX = re.compile(r'^\[(?P<name>.*)]\s*$', re.MULTILINE)

N6DATASOURCES_MODULE_NAME = 'n6datasources'
COLLECTORS_MODULE_NAME_PREFIX = f'{N6DATASOURCES_MODULE_NAME}.collectors.'
PARSERS_MODULE_NAME_PREFIX = f'{N6DATASOURCES_MODULE_NAME}.parsers.'
assert NP_MARK not in N6DATASOURCES_MODULE_NAME
assert NP_MARK not in COLLECTORS_MODULE_NAME_PREFIX
assert NP_MARK not in PARSERS_MODULE_NAME_PREFIX

BASE_COLLECTORS_MODULE_NAME = 'n6datasources.collectors.base'
BASE_PARSERS_MODULE_NAME = 'n6datasources.parsers.base'
assert BASE_COLLECTORS_MODULE_NAME.startswith(COLLECTORS_MODULE_NAME_PREFIX)
assert BASE_PARSERS_MODULE_NAME.startswith(PARSERS_MODULE_NAME_PREFIX)

# * Special (exceptional) cases:

EXPECTED_MISSING_COLLECTOR_MODULE_LEAF_NAMES = frozenset({
    'malwarepatrol',
})
EXPECTED_MISSING_PARSER_MODULE_LEAF_NAMES = frozenset({
    'amqp',
})

EXPECTED_MISSING_COLLECTOR_CONFIG_FILE_LEAF_NAMES = frozenset({
    'manual',
})
EXPECTED_MISSING_PARSER_CONFIG_FILE_LEAF_NAMES = frozenset({
    'manual',
})

EXPECTED_MISSING_CONFIG_SECTION_NAMES = frozenset({
    'AMQPCollector',
    'MispCollector',
})
EXPECTED_EXTRA_CONFIG_SECTION_NAMES = frozenset({
    'amqp_collector_example_config_section_name',
    'misp_circl',
})


#
# Main logic

def main() -> None:
    if not __debug__:
        raise sys.exit(
            "FATAL ERROR! This script requires that Python's "
            "`__debug__` flag is true (as the script makes use "
            "of `assert` statements to check for some errors).")

    classes = _get_collector_and_parser_classes()
    _verify_no_duplicate_class_names(classes)

    defects = []
    defects.extend(_check_console_script_files(classes))
    defects.extend(_check_config_prototype_files(classes))

    print('\n---', _format_proc_summary(classes), '---',
          sep='\n', end='\n\n')
    if defects:
        listing = '\n* '.join(defects)
        sys.exit(
            f'Defects detected:\n\n* {listing}\n\n'
            f'ERROR! See the defects listed above.')
    else:
        print(f'OK.')


#
# Helpers

_DefectStr = str


@dataclasses.dataclass
class _ConfigFileData:

    path: pathlib.Path

    @functools.cached_property
    def leaf_name(self) -> str:
        assert NP_MARK not in str(self.path)
        name = self.path.name
        assert name.startswith(CONFIG_FILENAME_PREFIX)
        assert name.endswith(CONFIG_FILENAME_SUFFIX)
        return (
            name
            .removeprefix(CONFIG_FILENAME_PREFIX)
            .removesuffix(CONFIG_FILENAME_SUFFIX)
        )

    @functools.cached_property
    def corresponding_collector_modname(self) -> str:
        modname = COLLECTORS_MODULE_NAME_PREFIX + self.leaf_name
        assert NP_MARK not in modname
        return modname

    @functools.cached_property
    def corresponding_parser_modname(self) -> str:
        modname = PARSERS_MODULE_NAME_PREFIX + self.leaf_name
        assert NP_MARK not in modname
        return modname

    @functools.cached_property
    def config_section_names(self) -> set[str]:
        file_content = self.path.read_text(encoding='utf-8')
        names = {match['name'] for match in CONFIG_SECTION_REGEX.finditer(file_content)}
        if not names:
            sys.exit(
                f'FATAL ERROR! Config prototype (template) file '
                f'{str(self.path)!a} does not contain any config section.')
        assert not any(NP_MARK in name.lower() for name in names)
        return names


_imported_module_names = list()

_seen_script_names = set()
_seen_entry_point_refs = set()

_checked_config_files_num = 0


@memoized
def _get_collector_and_parser_classes() -> Sequence[type]:
    assert N6DATASOURCES_MODULE_NAME not in sys.modules
    assert BASE_COLLECTORS_MODULE_NAME not in sys.modules
    assert BASE_PARSERS_MODULE_NAME not in sys.modules

    _import_all_n6datasources_modules()

    assert N6DATASOURCES_MODULE_NAME in sys.modules
    assert BASE_COLLECTORS_MODULE_NAME in sys.modules
    assert BASE_PARSERS_MODULE_NAME in sys.modules

    (AbstractBaseCollector,
     BaseParser) = _get_root_classes()

    classes = [
        cls
        for cls in (all_subclasses(AbstractBaseCollector) | all_subclasses(BaseParser))
        if (cls.__module__ not in {BASE_COLLECTORS_MODULE_NAME, BASE_PARSERS_MODULE_NAME}
            and cls.__module__.split('.')[:2] != [N6DATASOURCES_MODULE_NAME, 'tests']
            and not cls.__name__.startswith('_'))]
    classes.sort(key=operator.attrgetter('__module__', '__qualname__'))

    assert all(cls.__module__ in sys.modules for cls in classes)
    return tuple(classes)


@memoized
def _import_all_n6datasources_modules() -> None:
    assert N6DATASOURCES_MODULE_NAME not in sys.modules
    module_path_str = str(N6DATASOURCES_TOPLEVEL_DIR_PATH)
    if not (sys.path and sys.path[0] == module_path_str):
        sys.path.insert(0, module_path_str)

    assert sys.path and sys.path[0] == module_path_str
    for _, modname, _ in pkgutil.walk_packages([module_path_str]):
        if modname.split('.')[:1] == [N6DATASOURCES_MODULE_NAME]:
            importlib.import_module(modname)
            _imported_module_names.append(modname)


def _verify_no_duplicate_class_names(classes: Sequence[type]):
    seen = set()
    for cls in classes:
        assert cls.__name__ not in seen, cls.__name__
        seen.add(cls.__name__)


def _check_console_script_files(classes: Sequence[type]) -> Iterator[_DefectStr]:
    expected_console_script_lines = OPSet(map(_format_console_script_line, classes))
    assert len(expected_console_script_lines) == len(classes)
    console_script_lines = OPSet(_iter_actual_console_script_lines())
    if missing := (expected_console_script_lines - console_script_lines):
        for line in missing:
            yield f'Missing console script line: {line!a}'
    if unexpected := (console_script_lines - expected_console_script_lines):
        for line in unexpected:
            yield f'Unexpected console script line: {line!a}'
    for line in console_script_lines:
        if NP_MARK in line.lower():
            yield f'Unexpected substring {NP_MARK!a} in console script line {line!a}'


@memoized
def _format_console_script_line(cls: type) -> str:
    assert BASE_COLLECTORS_MODULE_NAME in sys.modules
    assert BASE_PARSERS_MODULE_NAME in sys.modules
    assert cls.__module__ in sys.modules

    AbstractBaseCollector = sys.modules[BASE_COLLECTORS_MODULE_NAME].AbstractBaseCollector
    BaseParser = sys.modules[BASE_PARSERS_MODULE_NAME].BaseParser

    assert isinstance(cls, type), cls
    assert issubclass(cls, AbstractBaseCollector) or issubclass(cls, BaseParser), cls.__mro__
    assert not (issubclass(cls, AbstractBaseCollector)
                and issubclass(cls, BaseParser)), cls.__mro__

    kind = 'collector' if issubclass(cls, AbstractBaseCollector) else 'parser'
    distinct_part = cls.__name__.lower().removesuffix(kind)

    assert cls.__name__ == cls.__qualname__, f'{cls.__name__=!a} != {cls.__qualname__=!a}'
    assert cls.__name__.lower().endswith(kind), cls.__name__
    assert kind not in distinct_part, distinct_part

    script_name = f'n6{kind}_{distinct_part}'
    assert script_name not in _seen_script_names, script_name
    _seen_script_names.add(script_name)

    entry_point_callable_loc = f'{cls.__name__}_main'
    entry_point_callable = getattr(sys.modules[cls.__module__], entry_point_callable_loc, None)
    assert isinstance(entry_point_callable, BoundMethod), entry_point_callable
    assert isinstance(entry_point_callable.__func__, Function), entry_point_callable.__func__
    assert entry_point_callable.__self__ is cls, entry_point_callable.__self__
    assert entry_point_callable.__name__ == 'run_script', entry_point_callable.__name__

    entry_point_ref = f'{cls.__module__}:{entry_point_callable_loc}'
    assert entry_point_ref not in _seen_entry_point_refs, entry_point_ref
    _seen_entry_point_refs.add(entry_point_ref)

    return f'{script_name} = {entry_point_ref}'


def _iter_actual_console_script_lines() -> Iterator[str]:
    try:
        with open(CONSOLE_SCRIPTS_PATH, encoding='ascii') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                if line.endswith('\n'):
                    line = line[:-1]
                yield line
    except (OSError, UnicodeError) as exc:
        sys.exit(
            f'FATAL ERROR! Could not read from the file '
            f'{str(CONSOLE_SCRIPTS_PATH)!a} ({exc})')


def _check_config_prototype_files(classes: Sequence[type]) -> Iterator[_DefectStr]:
    config_file_paths = yield from _obtain_config_file_paths()
    config_file_data_seq = list[_ConfigFileData](map(_ConfigFileData, config_file_paths))

    (unhandled_collector_modname_to_cls_names,
     unhandled_parser_modname_to_cls_names,
     ) = _get_unhandled_modname_to_cls_names_dicts(classes)

    for cf_data in config_file_data_seq:
        if cf_data.leaf_name in EXPECTED_MISSING_COLLECTOR_MODULE_LEAF_NAMES:
            continue
        collector_modname = cf_data.corresponding_collector_modname
        try:
            collector_cls_names = unhandled_collector_modname_to_cls_names.pop(collector_modname)
        except KeyError:
            yield (f'No collector module corresponding to the '
                   f'existing file {str(cf_data.path)!a}')
            continue
        while collector_cls_names:
            collector_name = collector_cls_names.popleft()
            try:
                cf_data.config_section_names.remove(collector_name)
            except KeyError:
                if collector_name not in EXPECTED_MISSING_CONFIG_SECTION_NAMES:
                    yield (f'Missing config section {collector_name!a} '
                           f'(corresponding to the existing collector '
                           f'class) in file {str(cf_data.path)!a}')

    for cf_data in config_file_data_seq:
        if cf_data.leaf_name in EXPECTED_MISSING_PARSER_MODULE_LEAF_NAMES:
            continue
        parser_modname = cf_data.corresponding_parser_modname
        try:
            parser_cls_names = unhandled_parser_modname_to_cls_names.pop(parser_modname)
        except KeyError:
            yield (f'No parser module corresponding to the '
                   f'existing file {str(cf_data.path)!a}')
            continue
        while parser_cls_names:
            parser_name = parser_cls_names.popleft()
            try:
                cf_data.config_section_names.remove(parser_name)
            except KeyError:
                if parser_name not in EXPECTED_MISSING_CONFIG_SECTION_NAMES:
                    yield (f'Missing config section {parser_name!a} '
                           f'(corresponding to the existing parser '
                           f'class) in file {str(cf_data.path)!a}')

    for collector_modname in unhandled_collector_modname_to_cls_names:
        leaf_name = collector_modname.split('.')[-1]
        if leaf_name not in EXPECTED_MISSING_COLLECTOR_CONFIG_FILE_LEAF_NAMES:
            yield (f'Missing config prototype (template) file for the '
                   f'existing collector module {collector_modname!a}')

    for parser_modname in unhandled_parser_modname_to_cls_names:
        leaf_name = parser_modname.split('.')[-1]
        if leaf_name not in EXPECTED_MISSING_PARSER_CONFIG_FILE_LEAF_NAMES:
            yield (f'Missing config prototype (template) file for the '
                   f'existing parser module {parser_modname!a}')

    for cf_data in config_file_data_seq:
        for name in cf_data.config_section_names:
            if name not in EXPECTED_EXTRA_CONFIG_SECTION_NAMES:
                yield (f'No collector/parser class (in the related module(s)) '
                       f'corresponding to the existing config section {name!a} '
                       f'in file {str(cf_data.path)!a}')


@memoized
def _obtain_config_file_paths() -> Generator[_DefectStr, None, Sequence[pathlib.Path]]:
    global _checked_config_files_num

    config_file_data_seq = []
    for path in sorted(CONFIG_DIR_PATH.iterdir()):
        if not path.name.startswith(CONFIG_FILENAME_PREFIX):
            continue
        _checked_config_files_num += 1
        if (re.search(Config.DEFAULT_CONFIG_FILENAME_EXCLUDING_REGEX, path.name)
              or not re.search(Config.DEFAULT_CONFIG_FILENAME_REGEX, path.name)):
            yield f'Incorrect config file name: {path.name!a} (ignored by n6 stuff!)'
            continue
        assert path.name.endswith(CONFIG_FILENAME_SUFFIX)
        if NP_MARK in str(path):
            yield (
                f'Incorrect config file path: {str(path)!a} '
                f'(contains unexpected substring {NP_MARK!a})')
            continue
        config_file_data_seq.append(path)
    return tuple(config_file_data_seq)


def _get_unhandled_modname_to_cls_names_dicts(classes: Sequence[type],
                                              ) -> tuple[dict[str, collections.deque[str]],
                                                         dict[str, collections.deque[str]]]:
    (AbstractBaseCollector,
     BaseParser) = _get_root_classes()

    unhandled_collector_modname_to_cls_names = collections.defaultdict(collections.deque)
    unhandled_parser_modname_to_cls_names = collections.defaultdict(collections.deque)
    for cls in classes:
        assert NP_MARK not in cls.__module__
        assert NP_MARK not in cls.__qualname__.lower()
        assert cls.__module__ in _imported_module_names
        assert cls.__module__ in sys.modules
        assert cls.__module__.startswith((COLLECTORS_MODULE_NAME_PREFIX,
                                          PARSERS_MODULE_NAME_PREFIX))
        if issubclass(cls, AbstractBaseCollector):
            unhandled_collector_modname_to_cls_names[cls.__module__].append(cls.__name__)
        else:
            assert issubclass(cls, BaseParser)
            unhandled_parser_modname_to_cls_names[cls.__module__].append(cls.__name__)
    unhandled_collector_modname_to_cls_names = dict(unhandled_collector_modname_to_cls_names)
    unhandled_parser_modname_to_cls_names = dict(unhandled_parser_modname_to_cls_names)
    return unhandled_collector_modname_to_cls_names, unhandled_parser_modname_to_cls_names


def _format_proc_summary(classes: Sequence[type]) -> str:
    (AbstractBaseCollector,
     BaseParser) = _get_root_classes()

    collectors_num = len([cls for cls in classes if issubclass(cls, AbstractBaseCollector)])
    parsers_num = len([cls for cls in classes if issubclass(cls, BaseParser)])
    imported_n6datasources_submodules_num = len(_imported_module_names) - 1

    assert len(classes) == collectors_num + parsers_num
    assert len(classes) == len(_seen_script_names) == len(_seen_entry_point_refs)

    return (
        f'Checked *console script* entry points and *config prototype* '
        f'files for {collectors_num} collectors and {parsers_num} parsers '
        f'({len(classes)} components in total).'
        f'\n'
        f'Processed {imported_n6datasources_submodules_num} submodules of '
        f'{N6DATASOURCES_MODULE_NAME!a} and {_checked_config_files_num} '
        f'config prototype (template) files (only those whose names start '
        f'with {CONFIG_FILENAME_PREFIX!a}).')


def _get_root_classes() -> tuple[type, type]:
    assert BASE_COLLECTORS_MODULE_NAME in sys.modules
    assert BASE_PARSERS_MODULE_NAME in sys.modules

    AbstractBaseCollector = sys.modules[BASE_COLLECTORS_MODULE_NAME].AbstractBaseCollector
    BaseParser = sys.modules[BASE_PARSERS_MODULE_NAME].BaseParser

    return AbstractBaseCollector, BaseParser


#
# Actual script

if __name__ == '__main__':
    main()
