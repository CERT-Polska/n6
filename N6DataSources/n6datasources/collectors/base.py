# Copyright (c) 2013-2024 NASK. All rights reserved.

"""
Collector base classes + auxiliary tools.
"""

import contextlib
import datetime
import operator
import pathlib
import pickle
import hashlib
import os
import sys
import time
import traceback
from collections.abc import (
    Iterator,
    Set,
)
from math import trunc
from typing import (
    Any,
    BinaryIO,
    ClassVar,
    Optional,
    Union,
)

import requests

from n6datapipeline.base import LegacyQueuedBase
from n6lib.class_helpers import CombinedWithSuper
from n6lib.config import (
    Config,
    ConfigError,
    ConfigMixin,
    ConfigSection,
    combined_config_spec,
)
from n6lib.common_helpers import (
    AtomicallySavedFile,
    CIDict,
    as_bytes,
    ascii_str,
    make_exc_ascii_str,
)
from n6lib.const import RAW_TYPE_ENUMS
from n6lib.data_spec.fields import (
    FieldValueError,
    SourceField,
)
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.mail_parsing_helpers import ParsedEmailMessage
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


DownloadTimeout = Union[
    int,
    float,
    tuple[Union[int, float], Union[int, float]],
]


#
# Mixin classes
#

class CollectorConfigMixin(ConfigMixin):

    """
    A mixin that provides the configuration-options-related stuff
    (`n6lib.config.ConfigMixin`-based).

    Note: unlike other mixin classes defined in this module, this class
    is already one of the `BaseCollector`'s superclasses (as well as of
    the `StatefulCollectorMixin`'s superclasses) -- so in most cases you
    do not need to explicitly derive your collector class from this
    mixin (one case when you may want to do that is the rare case when
    you derive your class directly from `AbstractBaseCollector` and not
    from `BaseCollector`).
    """

    # The default *config spec pattern* for collectors. It can be
    # overridden in subclasses, but note that the default implementation
    # of the `set_configuration()` method expects that the *config
    # spec pattern* includes the `{collector_class_name}` section
    # (treated by it as the *main section* -- unless the method
    # `get_config_from_config_full()` is overridden in a way that
    # removes that expectation...). *Hint:* values of the attribute
    # declared along the inheritance hierarchy can be easily *combined*
    # (in a cooperative-inheritance-friendly way) by using the
    # `n6lib.config.combined_config_spec()` helper.
    config_spec_pattern: str = combined_config_spec('''
        [{collector_class_name}]
    ''')

    # Instance attributes to be set automatically
    # when `set_configuration()` is called:
    config: ConfigSection   # containing options from the *main section*
    config_full: Config     # containing *all* declared config sections

    def set_configuration(self) -> None:
        """
        Set the configuration-related attributes.

        This method is supposed to be called in the `__init__()` method
        (note: in particular, `BaseCollector`'s `__init__()` does that).
        """
        format_kwargs = self.get_config_spec_format_kwargs()
        collector_class_name = format_kwargs['collector_class_name']
        assert collector_class_name == self.__class__.__name__
        self.config_full = self.get_config_full(**format_kwargs)
        self.config = self.get_config_from_config_full(
            config_full=self.config_full,
            collector_class_name=collector_class_name)

    def get_config_spec_format_kwargs(self) -> KwargsDict:
        """
        A hook invoked by `set_configuration()`: get the *format data
        dict* -- to be used to format the actual *config spec* (based on
        the value of the `config_spec_pattern` attribute).

        The default implementation of this method returns a dictionary
        that contains just one key: `'collector_class_name'` -- the
        value is `__name__` of the collector class.

        This method will need to be extended (typically, using `super()`)
        in your subclasses if their `config_spec_pattern`s contain also
        other replacement fields (apart from `{collector_class_name}`).
        """
        return {'collector_class_name': self.__class__.__name__}

    def get_config_from_config_full(self,
                                    *,
                                    config_full: Config,
                                    collector_class_name: str) -> ConfigSection:
        """
        A hook invoked by `set_configuration()`: given the `Config`
        mapping already being the value of the `config_full` attribute
        and the `collector_class_name` item from the dict returned by
        `get_config_spec_format_kwargs()`, get a `ConfigSection` mapping
        -- `set_configuration()` will set it as the `config` attribute.

        The default implementation of this method should be appropriate
        in most cases.
        """
        return config_full[collector_class_name]


class StatefulCollectorMixin(CollectorConfigMixin):

    """
    A mixin that provides tools to persist some state (whatever it is
    for a particular subclass) between collector script runs.

    Any picklable object can be saved as a state and then be retrieved
    as an object of the same type.
    """

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]

        state_dir = ~/.n6state :: path
    ''')

    unsupported_class_attributes: ClassVar[Set[str]] = CombinedWithSuper(frozenset({
        # (replaced with the constructor argument `state_pickle_protocol`)
        'pickle_protocol',
    }))

    def __init__(self, /, *args,
                 state_pickle_protocol: int = pickle.HIGHEST_PROTOCOL,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._state_pickle_protocol: int = state_pickle_protocol
        self._state_file_path: pathlib.Path = self.config['state_dir'] / self.get_state_file_name()

    #
    # Helper methods (can be used in your collector class)

    def load_state(self) -> Any:
        """
        Load collector's state from the state file.

        Returns:
            Unpickled object of its original type.
        """
        try:
            with open(self._state_file_path, 'rb') as state_file:
                if self.__is_py2_pickle_to_be_loaded(state_file):
                    state = self.__load_py2_pickle(state_file)
                else:
                    state = pickle.load(state_file)
        except FileNotFoundError as exc:
            state = self.make_default_state()
            LOGGER.warning(
                'Could not load the collector state (%s). '
                'The following default state will be used: %a.',
                make_exc_ascii_str(exc), state)
        except Exception as exc:
            LOGGER.error(
                'Could not load the collector state from %a (%s). '
                'You may need to deal with the problem manually!',
                os.fspath(self._state_file_path), make_exc_ascii_str(exc))
            raise
        else:
            LOGGER.info(
                'Loaded the collector state from %a.',
                os.fspath(self._state_file_path))
            LOGGER.debug('The loaded state is: %a.', state)
        return state

    def save_state(self, state: Any) -> None:
        """
        Save any picklable object as a collector's state.

        Args/kwargs:
            `state`: a picklable object.

        Note: when implementing your `StatefulCollectorMixin`-derived
        concrete collector you may want to call this method in your
        customized version of the `after_completed_publishing()`
        collector hook method (see its description in
        `AbstractBaseCollector`).
        """
        state_dir = self._state_file_path.parent
        state_dir.mkdir(0o700, parents=True, exist_ok=True)
        try:
            with AtomicallySavedFile(self._state_file_path, 'wb') as state_file:
                pickle.dump(state, state_file, self._state_pickle_protocol)
        except Exception as exc:
            LOGGER.error(
                'Could not save the collector state to %a (%s). '
                'You may need to deal with the problem manually!',
                os.fspath(self._state_file_path), make_exc_ascii_str(exc))
            raise
        LOGGER.info(
            'Saved the collector state to %a.',
            os.fspath(self._state_file_path))
        LOGGER.debug('The saved state is: %a.', state)

    #
    # Overridable methods (can be overridden/extended in your collector class)

    def make_default_state(self) -> Any:
        return None

    def get_state_file_name(self) -> str:
        module_name = self.__class__.__module__
        class_qualname = self.__class__.__qualname__
        self.__verify_module_is_not_main(module_name, class_qualname)
        return f'{module_name}.{class_qualname}.pickle'

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self) -> KwargsDict:
        # (Note: these values are equivalent to the defaults. We
        # specify them here just for explicitness. In subclasses,
        # they can be shadowed by different ones if necessary.)
        return dict(encoding='ascii', errors='strict')

    def adjust_state_from_py2_pickle(self, state: Any) -> Any:
        return state

    #
    # Private helpers

    __START_BYTE_FOR_PICKLE_PROTOCOL_2_AND_NEWER = b'\x80'

    def __is_py2_pickle_to_be_loaded(self, state_file: BinaryIO) -> bool:
        start_byte = state_file.read(1)
        protocol_byte = state_file.read(1)
        state_file.seek(0)
        if not start_byte or not protocol_byte:
            # Apparently the file is truncated; if so, `pickle.load()`
            # will raise an error anyway...
            return False
        if (start_byte == self.__START_BYTE_FOR_PICKLE_PROTOCOL_2_AND_NEWER
              and protocol_byte[0] >= 2):
            # OK, the file seems to contain data pickled using *either*
            # the Pickle Protocol 2, used by the Python 2 version of this
            # class (then let's return `True`), *or* the Pickle Protocol
            # in a newer version, used by the Python 3 version of this
            # class (then let's return `False`).
            return (protocol_byte[0] == 2)
        sys.exit(
            f'The first two bytes of the state file {state_file.name!a} '
            f'do not look like the beginning of anything properly '
            f'serialized using the Pickle Protocol 2 or newer. You '
            f'need to examine and fix (or remove) the file manually!')

    def __load_py2_pickle(self, state_file: BinaryIO) -> Any:
        load_kwargs = self.get_py2_pickle_load_kwargs()
        LOGGER.warning(
            'Trying to load the state from a Python-2-saved pickle, by '
            'calling `pickle.load(<state file>, **%a)`...', load_kwargs)
        try:
            state = pickle.load(state_file, **load_kwargs)
        except Exception:  # noqa
            sys.exit(
                f'When trying to load the current collector state '
                f'from the state file {state_file.name!a} *saved by '
                f'the Python 2 version of the collector*, the program '
                f'encountered the following exception (to work around '
                f'the problem, you may want to customize, for this '
                f'particular collector, the collector methods '
                f'`get_py2_pickle_load_kwargs()` and/or '
                f'`adjust_state_from_py2_pickle()`):\n\n'
                f'{traceback.format_exc().strip()}\n\n')
        LOGGER.warning(
            'The state from a Python-2-saved pickle has been loaded. '
            'Now the `adjust_state_from_py2_pickle()` method of %a '
            'will be invoked to adjust the loaded data...', self)
        return self.adjust_state_from_py2_pickle(state)

    def __verify_module_is_not_main(self, module_name: str, class_qualname: str) -> None:
        if module_name == '__main__':
            raise ValueError(
                f'{module_name!a} is not the proper name of '
                f'the module containing {class_qualname}')


#
# Base collector classes
#

class AbstractBaseCollector:

    """
    A base class that defines a minimum set of methods that a collector
    script class should have. A few of them (including: `run_script()`,
    `get_script_init_kwargs()` and `run_collection()`) have sensible
    default implementations; a few others (`run()`, `stop()`) are
    *abstract* ones (i.e., need to be overridden in subclasses).
    """

    #
    # Script running

    @classmethod
    def run_script(cls) -> None:
        with logging_configured():
            init_kwargs = cls.get_script_init_kwargs()
            collector = cls(**init_kwargs)  # noqa
            collector.run_collection()

    @classmethod
    def get_script_init_kwargs(cls) -> KwargsDict:
        """
        A class method: get a dict of kwargs for instantiation in a script.

        The default implementation returns an empty `dict`.
        """
        return {}

    #
    # Main activity

    def run_collection(self) -> None:
        """
        This method is expected to implement the main activity of the
        collector.

        The default implementation of this method performs the following
        actions:

        * (1) invoke the collector's `run()` method (which, in its
          typical version implemented in `LegacyQueuedBase`, starts the
          `pika`'s event loop, that will be running until it finishes
          normally, or *Ctrl+C* is pressed, or some fatal error occurs).

        * (2-a) If `run()` raised a `KeyboardInterrupt` exception
          (typically, because *Ctrl+C* was pressed), invoke the
          collector's `stop()` method (which, in its typical version
          implemented in `LegacyQueuedBase`, stops the `pika`'s event
          loop), then re-raise the exception.

        * (2-b) If `run()` raised any other exception, just propagate
          it (without invoking `stop()`).

        * (2-c) If no exception occurred, invoke the collector's method
          `after_completed_publishing()` (note that, in this case,
          `stop()` should not be invoked because the `run()` method
          has finished its activity normally).

        In subclasses, you may want to precede the above actions with
        some preparatory activities, typically focused on obtaining and
        preparation of the input data. You can do that by extending this
        method and placing those preparatory activities before the
        `super().run_collection()` statement (for a good example, see
        the `BaseTwoPhaseCollector`'s implementation of this method...).
        """
        try:
            self.run()
        except KeyboardInterrupt:
            self.stop()
            raise
        else:
            self.after_completed_publishing()

    # * Abstract methods (must be overridden in subclasses):

    def run(self) -> None:
        """
        Perform the process of *publishing* output data.

        [Terminological note: in the context of the *n6* pipeline,
        by *publishing* some data we mean putting the data into the
        component's output queue(s), using the AMQP operation named
        *basic.publish*. Obviously, it has nothing to do with making
        any data public.]

        This is an abstract method. Typically, it will be overridden
        (shadowed) with the implementation of `run()` provided by the
        `n6datapipeline.base.LegacyQueuedBase` class.
        """
        raise NotImplementedError

    def stop(self) -> None:
        """
        Perform any actions/cleanups needed after `run()` was interrupted
        (typically, by pressing *Ctrl+C*).

        This is an abstract method. Typically, it will be overridden
        (shadowed) with the implementation of `stop()` provided by the
        `n6datapipeline.base.LegacyQueuedBase` class.
        """
        raise NotImplementedError

    # * Additional hooks (can be overridden in subclasses if needed):

    def after_completed_publishing(self) -> None:
        """
        A hook invoked by `AbstractBaseCollector`'s version of
        `run_collection()` when `run()` finished its job without
        propagating any exception.

        The default implementation of this method does nothing. In your
        implementations in subclasses you can perform any actions that
        are supposed to be performed if everything went well.
        """


class BaseCollector(CollectorConfigMixin, LegacyQueuedBase, AbstractBaseCollector):

    """
    The main base class for collectors.
    """

    output_queue: Optional[Union[dict, list[dict]]] = {
        'exchange': 'raw',
        'exchange_type': 'topic',
    }

    # `None` or a `str` being a tag denoting the version of the
    # raw data format (aka *raw format version tag*), in the format:
    # `<4-digit year><2-digit month>` (needed only if the raw data
    # format has ever changed, so that a new parser had to be added)
    raw_format_version_tag: Optional[str] = None

    # must be set in concrete subclasses to one of the values
    # the `n6lib.const.RAW_TYPE_ENUMS` constant contains:
    # 'stream', 'file' or 'blacklist'
    raw_type: str = None

    # must be set in concrete subclasses *if*
    # `raw_type` is 'file' or 'blacklist'
    content_type: Optional[str] = None

    # the attribute has to be overridden, if a component should
    # accept the "--n6recovery" argument option and inherits from
    # the `BaseCollector` class or its subclass
    supports_n6recovery: bool = False

    # the `UnsupportedClassAttributesMixin`-related stuff
    unsupported_class_attributes: ClassVar[Set[str]] = CombinedWithSuper(frozenset({
        # (these methods/attributes are no longer supported, and we do
        # not want to let them remain unnoticed in any subclasses)
        'config_spec',            # nowadays, only `config_spec_pattern` should be used
        'source_config_section',  # nowadays, the main config section name is just the class name
        'type',                   # has been renamed to `raw_type`
        'run_handling',           # has been replaced with `run_collection()`
        'get_source_channel',     # nowadays, `get_source()` should be implemented in subclasses
    }))


    #
    # Subclass initialization

    def __init_subclass__(cls, /, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls._is_abstract_base():
            # To catch certain types of bugs early:
            cls._validate_source_type_related_attributes(
                ascii_str(cls.__qualname__),
                raw_type=cls.raw_type,
                content_type=cls.content_type)

    @classmethod
    def _is_abstract_base(cls):
        return (cls.__module__.endswith('.base')
                or cls.__name__.startswith('_'))

    @staticmethod
    def _validate_source_type_related_attributes(owner_repr,
                                                 *,
                                                 raw_type,
                                                 content_type):
        if raw_type is None:
            raise NotImplementedError(
                f"{owner_repr}'s attribute `raw_type` is not set")
        if raw_type not in RAW_TYPE_ENUMS:
            raise ValueError(
                f"{owner_repr}'s attribute `raw_type` should be "
                f"one of: {', '.join(map(ascii, RAW_TYPE_ENUMS))} "
                f"(found: {raw_type!a})")
        if raw_type in ('file', 'blacklist') and content_type is None:
            raise NotImplementedError(
                f"{owner_repr}'s attribute `raw_type` is set to "
                f"{raw_type!a} so `content_type` should be set to "
                f"a non-None value")


    #
    # Instance initialization/configuration

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        self.set_configuration()

    # * Configurable-pipeline-related hooks:

    def get_component_group_and_id(self):
        return 'collectors', self.__class__.__name__

    def make_binding_keys(self, binding_keys, *args, **kwargs):
        """
        Make binding keys for the collector using values from
        the pipeline config, if the collector accepts input messages
        (it has its `input_queue` class attribute implemented).

        Unlike in case of standard components (e.g., 'utils' group),
        values for the collector in the pipeline config are treated
        as target binding keys, not binding states.

        Each value from the config is the new binding key.

        Use the lowercase collector's class' name as associated option
        in the pipeline config, or its group's name - 'collectors'.

        Args/kwargs:
            `binding_keys`:
                The `list` of new binding keys.
            <any other arguments>:
                Ignored.
        """
        self.input_queue['binding_keys'] = binding_keys
        self.set_queue_name()

    def set_queue_name(self):
        """
        If the collector's `input_queue` dict does not have
        the `queue_name` key set, its queue's name defaults
        to the lowercase name of its class.

        The method may be called only for non-standard collectors
        accepting input messages.
        """
        if 'queue_name' not in self.input_queue or not self.input_queue['queue_name']:
            self.input_queue['queue_name'] = self.__class__.__name__.lower()


    #
    # AMQP-config-related hook (invoked in `LegacyQueuedBase.run()`)

    def update_connection_params_dict_before_run(self, params_dict):
        """
        For some collectors there may be a need to override the standard
        AMQP heartbeat interval (e.g., when collecting large files...).
        If this is the case for your collector class, just declare the
        `heartbeat_interval` option (with the `:: int` converter spec
        declaration) in the *main section* (which almost always is the
        `{collector_class_name}` section) of your collector class's
        `config_spec_pattern`; then the `BaseCollector`'s version of
        this hook will take care of the rest automatically.
        """
        super().update_connection_params_dict_before_run(params_dict)
        if 'heartbeat_interval' in self.config:
            params_dict['heartbeat_interval'] = self.config['heartbeat_interval']


    #
    # Input data processing -- preparing output data

    def get_output_components(self, **input_data):
        """
        Prepare the AMQP routing key, raw message body and AMQP headers
        -- to be used to make an AMQP output message.

        Kwargs:
            Some keyword-only arguments suitable
            for the `process_input_data()` method.

        Returns:
            A tuple of positional arguments for the `publish_output()`
            method: `(<routing key (str)>, <actual data body (bytes)>,
            <custom keyword arguments for pika.BasicProperties (dict)>)`.

        This is a "template method" -- calling the following overridable
        methods (in this order):

        * `process_input_data()`,
        * `get_source()` and then `validate_source()`,
        * `get_output_rk()` and then `validate_output_rk()`,
        * `get_output_data_body()` and then validate_output_data_body`()`,
        * `get_output_prop_kwargs()` and then `validate_output_prop_kwargs()`.

        NOTE: if -- in the case of your concrete collector class -- this
        method is used, the `get_source()` and `get_output_data_body()`
        methods should be considered *abstract* ones, i.e., they *must*
        be *overridden* (shadowed by concrete implementations) in your
        class.

        The rest of the aforementioned methods have reasonable default
        implementations which, if necessary, *can* be *extended* (i.e.,
        overridden with such an implementation that also invokes the
        superclass version, preferably using `super()`) in your class.
        """
        processed_data = self.process_input_data(**input_data)
        source = self.get_source(**processed_data)
        self.validate_source(source)
        output_rk = self.get_output_rk(
                source=source,
                **processed_data)
        self.validate_output_rk(output_rk)
        output_data_body = self.get_output_data_body(
                source=source,
                **processed_data)
        self.validate_output_data_body(output_data_body)
        output_prop_kwargs = self.get_output_prop_kwargs(
                source=source,
                output_data_body=output_data_body,
                **processed_data)
        self.validate_output_prop_kwargs(output_prop_kwargs)
        return output_rk, output_data_body, output_prop_kwargs

    def process_input_data(self, **input_data):
        """
        Process the given *input data*.

        Kwargs:
            The *input data* as some (subclass-specific) keyword arguments.

        Returns:
            A `dict` of (additional) keyword arguments to be passed the
            following methods:

            * `get_source()`,
            * `get_output_rk()`,
            * `get_output_data_body()`,
            * `get_output_prop_kwargs()`.

        Typically, this method is used indirectly -- being called in
        `get_output_components()`.

        The default implementation of this method does nothing and returns
        the given *input data* unchanged (as a `dict`).
        """
        return input_data

    # NOTE: typically, this method must be implemented in concrete subclasses
    def get_source(self, **processed_data):
        """
        Get the *source specification* string (aka *source id*, aka *source*).

        Kwargs:
            Processed data (as returned by the `process_input_data()`
            method, here passed in as keyword arguments).

        Returns:
            A `str` based on the pattern: '<source provider>.<source channel>'.

        Typically, this method is used indirectly -- being called in
        get_output_components().

        In `BaseCollector` **this is a method placeholder**. Without a
        concrete implementation of this method provided by a subclass,
        the `get_output_components()` method cannot be used (as it would
        raise `NotImplementedError`).
        """
        raise NotImplementedError

    def get_output_rk(self, *, source, **processed_data):
        """
        Get the output AMQP routing key.

        Kwargs:
            `source`:
                The *source specification* string, aka *source id*, aka *source*
                (as returned by the `get_source()` method; based on the
                pattern: '<source provider>.<source channel>').
            <some keyword arguments>:
                Processed data (as returned by the `process_input_data()`
                method), here passed in as keyword arguments (the default
                implementation ignores them).

        Returns:
            The output AMQP routing key (a `str`).

        Typically, this method is used indirectly -- being called in
        `get_output_components()`.

        The default implementation of this method should be sufficient in
        most cases.
        """
        if self.raw_format_version_tag is None:
            return source
        else:
            return f'{source}.{self.raw_format_version_tag}'

    # NOTE: typically, this method must be implemented in concrete subclasses
    def get_output_data_body(self, *, source, **processed_data):
        """
        Get the output AMQP message data.

        Kwargs:
            `source`:
                The *source specification* string, aka *source id*, aka *source*
                (as returned by the `get_source()` method; based on the
                pattern: '<source provider>.<source channel>').
            <some keyword arguments>:
                Processed data (as returned by the `process_input_data()`
                method, here passed in as keyword arguments).

        Returns:
            The output AMQP message body (a `bytes` object).

        Typically, this method is used indirectly -- being called in
        `get_output_components()`.

        In `BaseCollector` **this is a method placeholder**. Without a
        concrete implementation of this method provided by a subclass,
        the `get_output_components()` method cannot be used (as it would
        raise `NotImplementedError`).
        """
        raise NotImplementedError

    def get_output_prop_kwargs(self, *, source, output_data_body,
                               **processed_data):
        """
        Get a dict of custom keyword arguments for `pika.BasicProperties`.

        Kwargs:
            `source`:
                The *source specification* string, aka *source id*, aka *source*
                (as returned by the `get_source()` method; based on the
                pattern: '<source provider>.<source channel>').
            `output_data_body`:
                A `bytes` object being the output AMQP message data (as
                returned by the `get_output_data_body()` method).
            <some keyword arguments>:
                Processed data (as returned by the `process_input_data()`
                method), here passed in as keyword arguments (the default
                implementation ignores them).

        Returns:
            Custom keyword arguments for `pika.BasicProperties` (a `dict`).

        Typically, this method is used indirectly -- being called in
        `get_output_components()`.

        The default implementation of this method provides the following
        keys: `'message_id'`, `'type'` (corresponding to the collector's
        `raw_type`), `'timestamp'`, `'headers'`, and -- only if the
        collector's `raw_type` is `'file'` or `'blacklist'` -- also
        `'content_type'` (corresponding to the collector's `content_type`).
        This method can be *extended* in subclasses (using `super()`).
        """

        # Note: even though the validation provided by the following
        # call is very similar to the validation already done at the
        # class level (in `__init_subclass__()`), it is still useful
        # here -- because `raw_type` and/or `content_type` may also
        # be set on instances (shadowing the corresponding class
        # attributes).
        self._validate_source_type_related_attributes(
                    ascii(self),
                    raw_type=self.raw_type,
                    content_type=self.content_type)

        created_timestamp = trunc(time.time())
        message_id = self.get_output_message_id(
                    source=source,
                    created_timestamp=created_timestamp,
                    output_data_body=output_data_body,
                    **processed_data)

        properties = {
            'message_id': message_id,
            # (note: the following item is something completely *different*
            # than the 'type' item of a n6lib.record_dict.RecordDict)
            'type': self.raw_type,
            'timestamp': created_timestamp,
            'headers': {},
        }
        if self.raw_type in ('file', 'blacklist'):
            properties['content_type'] = self.content_type
        return properties

    def get_output_message_id(self, *, source, created_timestamp,
                              output_data_body, **processed_data):
        """
        Get the output message id (aka `rid`).

        Kwargs:
            `source`:
                The *source specification* string, aka *source id*, aka *source*
                (as returned by the `get_source()` method; based on the
                pattern: '<source provider>.<source channel>').
            `output_data_body`:
                A `bytes` object being the output AMQP message data (as
                returned by the `get_output_data_body()` method).
            `created_timestamp`:
                Message creation timestamp as an `int` number.
            <some keyword arguments>:
                Processed data (as returned by the `process_input_data()`
                method), here passed in as keyword arguments (the default
                implementation ignores them).

        Returns:
            The output message id (a `str`).

        Typically, this method is used indirectly -- being called in
        `get_output_prop_kwargs()` (which is called in
        `get_output_components()`).

        The default implementation of this method should be sufficient in
        most cases.
        """
        components = (
            as_bytes(source),
            as_bytes('{0:d}'.format(created_timestamp)),
            output_data_body,
        )
        hashed_bytes = b'\0'.join(components)
        return hashlib.md5(hashed_bytes, usedforsecurity=False).hexdigest()

    _source_value_validation_field = SourceField()

    def validate_source(self, source):
        # (checking type and value)
        if not isinstance(source, str):
            raise TypeError(ascii_str(
                f'{self.__class__.__qualname__}: {source=!a} '
                f'(an instance of `{type(source).__qualname__}` '
                f'whereas an instance of `str` was expected)'))
        try:
            cleaned = self._source_value_validation_field.clean_result_value(source)
        except FieldValueError as exc:
            raise ValueError(ascii_str(
                f'{self.__class__.__qualname__}: {source=!a} ({exc})')) from exc
        assert cleaned == source, f'{cleaned!a} vs. {source!a}'

    def validate_output_rk(self, output_rk):
        # (checking *only type*)
        if not isinstance(output_rk, str):
            raise TypeError(ascii_str(
                f'{self.__class__.__qualname__}: {output_rk=!a} '
                f'(an instance of `{type(output_rk).__qualname__}` '
                f'whereas an instance of `str` was expected)'))

    def validate_output_data_body(self, output_data_body):
        # (checking *only type*)
        if not isinstance(output_data_body, bytes):
            raise TypeError(ascii_str(
                f'{self.__class__.__qualname__}: {output_data_body=!a} '
                f'(an instance of `{type(output_data_body).__qualname__}` '
                f'whereas an instance of `bytes` was expected)'))

    def validate_output_prop_kwargs(self, output_prop_kwargs):
        # (checking *only type*)
        if not isinstance(output_prop_kwargs, dict):
            raise TypeError(ascii_str(
                f'{self.__class__.__qualname__}: {output_prop_kwargs=!a} '
                f'(an instance of `{type(output_prop_kwargs).__qualname__}` '
                f'whereas an instance of `dict` was expected)'))


class BaseTwoPhaseCollector(BaseCollector):

    """
    The main base class for such collectors whose activities can be
    divided into two separate phases:

    * (I: *obtaining phase*) obtain the *input pile*, that is, any data
      that needs to be obtained from the outside;

    * (II: *publishing phase*) output the obtained data as a series of
      AMQP messages.

    In fact, this two-phase scheme of action is expected to match the
    needs of most collectors.

    ***

    Note: the following methods must be implemented in subclasses (i.e.,
    they should be considered *abstract methods*):

    * `obtain_input_pile()` and `generate_input_data_dicts()`
      -- see their descriptions in this class;

    * `get_source()` and `get_output_data_body()`
      -- see `BaseCollector`, in particular the descriptions of those
      two methods as well as of the `get_output_components()` template
      method that invokes them (among others); note, also, that the
      items of each of the consecutive dicts expected to be produced by
      `generate_input_data_dicts()` will be used as keyword arguments
      passed to consecutive invocations of `get_output_components()`
      (see the descriptions of the methods `publish_iteratively()` and
      generate_input_data_dicts()`...).
    """

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        self._input_pile: Any = None   # to be set in `run_collection()`

    def run_collection(self):
        """
        The two-phase collectors' version of this method performs the
        following actions:

        * (1) Obtain the *input pile* (whatever it is for a particular
          subclass) by invoking the `obtain_input_pile()` method and
          storing the return value as a non-public instance attribute
          (you should never have to deal with that attribute by yourself)
          -- so that it can be retrieved later, during the activity of
          the `pika`'s event loop (in `publish_iteratively()`).

        * (2-a) If the *input pile* (i.e., the object returned by
          `obtain_input_pile()`) is anything but `None` then go to
          the *publishing phase* by invoking the superclass version of
          `run_collection()` (which, typically, will start by invoking
          this collector's `run()` method as it is defined in the base
          class `LegacyQueuedBase`, running the `pika`'s event loop...).
          Finally, if no exception occurs, the hook method
          `after_completed_publishing()` will be invoked.

        * (2-b) If the *input pile* is `None` then do nothing more (the
          *publishing phase* will *not* be carried out). Note that the
          `after_completed_publishing()` method will *not* be invoked
          in such a case.

        This version of `run_collection()` should be sufficient in most
        cases.
        """
        self._input_pile = self.obtain_input_pile()
        if self._input_pile is None:
            LOGGER.info('%a: nothing to publish.', self)
        else:
            super().run_collection()

    def obtain_input_pile(self) -> Any:
        """
        This is an abstract method; its implementation in a subclass is
        supposed to obtain and return the *input pile*, i.e., any data
        that needs to be obtained from the outside (and maybe prepared
        somehow, if necessary), whatever form it takes.

        If there is *no data* to be published, this method should return
        `None`; then the *publishing phase* (including invocations of
        `generate_input_data_dicts()`, `get_output_components()`, etc.)
        *will not* be carried out at all (so, in particular, the hook
        method `after_completed_publishing()` *will not* be invoked).

        ***

        The `obtain_input_pile()` method is invoked once, during the
        *obtaining phase*, from within `run_collection()`.
        """
        raise NotImplementedError

    def start_publishing(self) -> None:
        self.start_iterative_publishing()

    def publish_iteratively(self) -> None:
        """
        The two-phase collectors' version of this generator method
        performs the following actions:

        * (1) Invoke the `generate_input_data_dicts()` method with the
          *input pile* (i.e., the object being the result of the earlier
          invocation of `obtain_input_pile()`) as the sole argument, to
          obtain an iterator.

        * (2) Perform the following actions *for each* of the *input
          data* dicts yielded by the aforementioned iterator:

          * (a) invoke the `get_output_components()` method with the
            items of the *input data* dict as the keyword arguments
            -- to obtain the *output components* tuple;

          * (b) invoke the `publish_output()` method with the items of
            the *output components* tuple as the *positional arguments*
            -- to trigger publication of the corresponding AMQP message;

          * (c) yield `None` to let the `LegacyQueuedBase`'s *iterative
            publishing* machinery take care of all necessary technical
            details related to AMQP message publication.

        (Note: when the activity of this method finishes, the `pika`'s
        event loop regains control again -- then it should stop soon,
        just after sending any data remaining in the outbound data
        buffer and then closing the AMQP connection.)

        This version of `publish_iteratively()` should be sufficient in
        most cases.
        """
        assert self._input_pile is not None  # (otherwise this code would not be executed...)

        published_anything = False
        for input_data in self.generate_input_data_dicts(self._input_pile):
            output_components = self.get_output_components(**input_data)
            self.publish_output(*output_components)
            published_anything = True
            yield

        if not published_anything:
            LOGGER.warning(
                f'%a: nothing published because no items got from the '
                f'`generate_input_data_dicts()` method', self)

    def generate_input_data_dicts(self, input_pile: Any, /) -> Iterator[KwargsDict]:
        """
        **This is an abstract method**. Its implementation in a subclass
        is supposed to accept the *input pile* (i.e., the object being
        the result of the earlier invocation of `obtain_input_pile()`)
        as the sole positional argument, and return an iterator that
        yields one or more *input data* dicts (typically, you will want
        to implement this method as a generator function, using `yield`
        statements to yield those dicts).

        The items of each of those (consecutive) yielded dicts will
        become the keyword arguments passed to the corresponding
        (consecutive) invocations of `get_output_components()` (to be
        done in `publish_iteratively()`). The set of keys those dicts
        contain, and the types and meaning of values they point to, are
        subclass-specific; they are supposed to match what is expected
        by `get_output_components()` and, mostly, by the methods invoked
        by it (see the descriptions of that method and of the methods
        invoked by it, provided by `BaseCollector`).

        Note that the number of *input data* dicts yielded by this
        method determines the number of *output messages* being
        published (because it determines, one-to-one, the number of
        invocations of `get_output_components()` and `publish_output()`).

        If this method yields *no* input data dicts, then a warning will
        be logged and, obviously, nothing will be published. However,
        still, the hook method `after_completed_publishing()` *will be*
        invoked (because of observing no real errors).

        ***

        During the *publishing phase* (if it is carried out at all), the
        `generate_input_data_dicts()` method is invoked once, from within
        `publish_iteratively()`.
        """
        raise NotImplementedError


class BaseSimpleCollector(BaseTwoPhaseCollector):

    """
    The main base class for simple "one-shot" collectors, i.e., such ones
    that are supposed to publish at most one AMQP message during the whole
    collector run.

    When implementing a collector based on this class, the only methods
    that need to be overridden (i.e., *abstract methods*) are:

    * `obtain_data_body()` -- see its description in this class;
    * `get_source()` (as always; see its description in `BaseCollector`).
    """

    def obtain_data_body(self) -> Optional[bytes]:
        """
        This is an abstract method; its implementation in a subclass
        is supposed to obtain and return a `bytes` instance that will
        become the body of the published AMQP message (aka *output data
        body*).

        If there is *no data* to be published, this method should return
        `None`; then the *publishing phase* (including invocations of
        `generate_input_data_dicts()`, `get_output_components()`, etc.)
        *will not* be carried out at all (so, in particular, the hook
        method `after_completed_publishing()` *will not* be invoked).

        ***

        The `obtain_data_body()` method is invoked once, from within
        `obtain_input_pile()` (in its `BaseSimpleCollector`'s version).
        """
        raise NotImplementedError

    def obtain_input_pile(self):
        data_body = self.obtain_data_body()
        if data_body is not None:
            return {'data_body': data_body}
        return None

    def generate_input_data_dicts(self, input_data, /):
        # Note: in the case of this particular implementation of this
        # method, the *input pile* originating from `obtain_input_pile()`
        # becomes just the *input data* dict that will be passed, as
        # keyword arguments, to `get_output_components()` (and,
        # consequently, to `get_output_data_body()` defined below).
        assert isinstance(input_data, dict)
        assert 'data_body' in input_data
        yield input_data

    def get_output_data_body(self, *, data_body, **kwargs):
        return data_body


class BaseSimpleEmailCollector(BaseSimpleCollector):

    """
    The main base class for "one-shot" collectors spawned when an e-mail
    message arrives (e.g., by *procmail* or a similar tool); exactly one
    e-mail message in its raw form (as arrived, with all its headers and
    body) is expected to be sent to the standard input of the collector
    script.

    When implementing a collector based on this class, the only methods
    that need to be overridden (i.e., *abstract methods*) are:

    * `obtain_data_body()` -- typically, its implementation will make
      use of the `email_msg` instance attribute which is always set
      (on collector initialization) to an instance of the helper class
      `n6lib.mail_parsing_helpers.ParsedEmailMessage` (see its docs...)
      representing the e-mail message received via the standard input of
      the collector script;

      also, see the description of the `obtain_data_body()` method in
      `BaseSimpleCollector`;

    * `get_source()` (as always; see its description in `BaseCollector`).
    """

    @classmethod
    def get_script_init_kwargs(cls) -> KwargsDict:
        raw_email_msg: bytes = sys.stdin.buffer.read()
        return super().get_script_init_kwargs() | {
            'raw_email_msg': raw_email_msg,
        }

    email_msg: ParsedEmailMessage

    def __init__(self, /, *, raw_email_msg: bytes, **kwargs):
        super().__init__(**kwargs)
        self.email_msg = ParsedEmailMessage.from_bytes(raw_email_msg)

    #
    # Extension of `BaseCollector`-specific method

    def get_output_prop_kwargs(self, **processed_data) -> KwargsDict:
        prop_kwargs = super().get_output_prop_kwargs(**processed_data)
        mail_time_dt = self.email_msg.get_utc_datetime()
        mail_subject = self.email_msg.get_subject()
        if mail_time_dt is not None or mail_subject is not None:
            prop_kwargs['headers'].setdefault('meta', dict())
            if mail_time_dt is not None:
                prop_kwargs['headers']['meta']['mail_time'] = str(mail_time_dt)
            if mail_subject is not None:
                prop_kwargs['headers']['meta']['mail_subject'] = mail_subject
        return prop_kwargs

    #
    # Helper methods (can be used in your collector class)

    def get_email_msg_text(self, content_type: str) -> str:
        try:
            text = self.email_msg.find_content(content_type=content_type)
        except ValueError as exc:
            raise ValueError(
                f'unexpected e-mail message format: '
                f'multiple `{content_type}` parts found') from exc
        if text is None:
            raise ValueError(
                f'unexpected e-mail message format: '
                f'no `{content_type}` content found')
        if not isinstance(text, str):
            raise TypeError(
                f'resultant text is expected to be an instance '
                f'of str, got a {text.__class__.__qualname__}')
        return text


class BaseDownloadingCollector(BaseCollector):

    """
    TODO: docs & tests.
    """

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]

        download_retries = 3 :: int
        
        # Connect and read timeout. Accepted values: int, float, 
        # or 2-tuple of ints/floats.
        # See more: https://docs.python-requests.org/en/latest/user/advanced/#timeouts
        download_timeout = (12.1, 25) :: download_timeout
        
        base_request_headers = {{}} :: py_namespaces_dict
    ''')   # (`{{}}` is just escaped `{}` -- to avoid treating it as a pattern's replacement field)

    @property
    def custom_converters(self) -> dict:
        return {
            'download_timeout': self._conv_download_timeout_from_config,
        }

    @classmethod
    def _conv_download_timeout_from_config(cls, raw_value: str) -> DownloadTimeout:
        value = Config.BASIC_CONVERTERS['py'](raw_value)
        if isinstance(value, (float, int)):
            if value <= 0:
                raise ValueError('value should be > 0')
        elif isinstance(value, (tuple, list)):
            if isinstance(value, list):
                value = tuple(value)
            if len(value) != 2:
                raise ValueError('value should have exactly 2 items')
            invalid_values = [v for v in value if not isinstance(v, (float, int))]
            if invalid_values:
                raise TypeError(f'wrong type(s): {", ".join(invalid_values)}')
            if any(v <= 0 for v in value):
                raise ValueError('each value should be > 0')
        else:
            raise TypeError(
                'value should be one of the following types: '
                'int, float, 2-tuple of ints/floats'
            )
        return value

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        self._http_response = None          # to be set in request_performer()
        self._http_last_modified = None     # to be set in request_performer()

    #
    # Extension of `BaseCollector`-specific method

    def get_output_prop_kwargs(self, **processed_data) -> KwargsDict:
        prop_kwargs = super().get_output_prop_kwargs(**processed_data)
        if self.http_last_modified is not None:
            prop_kwargs['headers'].setdefault('meta', dict())
            prop_kwargs['headers']['meta']['http_last_modified'] = str(self.http_last_modified)
        return prop_kwargs

    #
    # Helper properties and methods (can be used in your collector class)

    @property
    def http_response(self) -> Optional[requests.Response]:
        return self._http_response

    @property
    def http_last_modified(self) -> Optional[datetime.datetime]:
        return self._http_last_modified

    def download(self, *args, stream=False, **kwargs) -> bytes:
        with self.request_performer(*args, stream=stream, **kwargs) as perf:
            content = perf.response.content
        if not isinstance(content, bytes):
            raise TypeError(f'something wrong: {type(content) = !a} (expected bytes)')
        return content

    def download_text(self, *args, stream=False, **kwargs) -> str:
        with self.request_performer(*args, stream=stream, **kwargs) as perf:
            text = perf.response.text
        if not isinstance(text, str):
            raise TypeError(f'something wrong: {type(text) = !a} (expected str)')
        return text

    @contextlib.contextmanager
    def request_performer(self,
                          url: str,
                          *,
                          method: str = 'GET',
                          retries: Optional[int] = None,
                          timeout: Optional[DownloadTimeout] = None,
                          custom_request_headers: Optional[dict] = None,
                          **rest_performer_constructor_kwargs):
        retries = self.__get_request_retries(retries)
        timeout = self.__get_request_timeout(timeout)
        headers = self.__get_request_headers(custom_request_headers)

        with RequestPerformer(method=method,
                              url=url,
                              retries=retries,
                              timeout=timeout,
                              headers=headers,
                              **rest_performer_constructor_kwargs) as perf:
            self._http_response = perf.response
            self._http_last_modified = perf.get_dt_header('Last-Modified')
            yield perf

    #
    # Private helpers

    def __get_request_retries(self, retries: Optional[int]) -> int:
        if retries is None:
            retries = self.config['download_retries']
            if retries < 0:
                raise ConfigError(f'config option `download_retries` is '
                                  f'a negative number: {retries!a}')
        return retries

    def __get_request_timeout(self, timeout: Optional[DownloadTimeout]
                              ) -> DownloadTimeout:
        if timeout is None:
            timeout = self.config['download_timeout']
        return timeout

    def __get_request_headers(self, custom_request_headers: Optional[dict]) -> dict:
        if custom_request_headers:
            case_insensitive_keys_mapping = CIDict(self.config['base_request_headers'])
            case_insensitive_keys_mapping.update(custom_request_headers)
            new_dict = dict(case_insensitive_keys_mapping)
        else:
            new_dict = self.config['base_request_headers'].copy()
        return new_dict


class BaseTimeOrderedRowsCollector(StatefulCollectorMixin, BaseTwoPhaseCollector):

    """
    The base class for collectors obtaining "row-like" data, i.e., data
    consisting of individual *rows* (in any sense that can be expressed
    by implementing the appropriate methods the machinery of this class
    consists of). Each *row* should include its *time/order* marker (such
    as date, timestamp or ordinal number...). New rows (with increasing
    or at least non-decreasing values of that marker) are expected, over
    time, to be *added* by the data source provider to the file/resource
    accessed by our collector.

    For more information -- in particular, some examples of input data
    with references to `BaseTimeOrderedRowsCollector`-specific methods
    -- see the further parts of this description...

    ***

    Implementation/overriding of methods and attributes:

    * required:
        * `get_source()`
          -- see `BaseCollector.get_source()`
        * `obtain_orig_data()`
          -- see its docs,
        * `pick_raw_row_time()`
          -- see its docs (and the docs of `extract_row_time()`),
        * `clean_row_time()`
          -- see its docs (and the docs of `extract_row_time()`);

    * optional: see the attributes and methods defined within the body
      of this class below the "Stuff that can be overridden..." comment.

    ***

    Original data (as returned by `obtain_orig_data()`) should consist
    of *rows* that can be decoded from `bytes` and then singled out (see:
    `all_rows_from_orig_data()` and the methods it calls), then selected
    (see: `get_fresh_rows_only()` and the methods it calls), and finally
    joined and encoded to `bytes` (see: `output_data_from_fresh_rows()`
    and the methods it calls).

    Rows (those for whom `should_row_be_used()` returns true) should
    contain the time/order field; its values are to be extracted by
    the `extract_row_time()` method; or -- let's be more specific --
    by certain methods called by it, namely: `pick_raw_row_time()`
    (which picks the raw time/order value from the given row) and
    `clean_row_time()` (which validates, converts and normalizes that
    time/order value).

    For example, for rows such as:

        '"123", "2019-07-18 14:29:05", "sample", "data"\n'
        '"987", "2019-07-17 15:13:13", "other", "data"\n'

    ...the `pick_raw_row_time()` should pick the values from the second
    column (for an example implementation -- see the docstring of the
    `pick_raw_row_time()` method).

    Values returned by `clean_row_time()` can have any form and type
    -- provided that a **newer** one always sorts as **greater than**
    an older one, and values representing the **same** time are always
    **equal**. An important related requirement is that the value returned
    by the `get_oldest_possible_row_time()` method **must always** sort
    as **less than** any value returned by `clean_row_time()`.

    ***

    A very important requirement, concerning the data source itself,
    is that values of the *time/order* field of any **new** (fresh) rows
    encountered by the collector **must** be **greater than or equal to**
    the *time/order* field's values of all rows collected during any past
    runs of the collector (when we say that values are *greater than or
    equal to* we refer to comparing values already prepared with
    `clean_row_time()`).

    When it is detected that *the data source does not satisfy* the
    requirement described above:

    * if the value of the `row_count_mismatch_is_fatal` option is
      false then a warning signalling row counts mismatch is logged
      and the collector continues its work (**beware:** some rows may
      be lost, i.e., *never* collected);

    * if the value of the `row_count_mismatch_is_fatal` option is
      true then a `ValueError` is raised (the collector's activity
      is aborted; no rows are collected).

    For example, let's assume that a certain data source provided
    the following data:

        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    Assuming that our imaginary collector treats the second column
    as the *time/order* field and that we just ran that collector,
    all those rows have been collected by it and the collector's saved
    state points on the `3`-rd row as the recent one.

    Now, let's imagine that the source added three new rows -- so that
    the data provided by the source looks like this:

        '"6", "2019-07-20 02:00:00", "sample_2", "data"\n'
        '"5", "2019-07-18 02:00:00", "sample_1", "data"\n'
        '"4", "2019-07-21 02:00:00", "sample_3", "data"\n'
        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    Even though the `4`-th and `6`-th rows could be collected, the
    `5`-th one **could not** -- as it would be considered a row *from
    the past* (as being older that the aforementioned `3`-rd row).
    Indeed, the problem is with the data source itself: it does not
    satisfy the requirement described above.

    ***

    One more thing concerning the original data from the data source:
    while it is OK to have several rows with exact same values of the
    time/order field, whole rows should be *unique* (if duplicates are
    detected, a warning is logged or, if the `row_count_mismatch_is_fatal`
    option is true, a `ValueError` is raised; in any case, there is *no
    guarantee* that such surplus rows will be collected).
    """

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]

        row_count_mismatch_is_fatal = no :: bool
    ''')


    _NEWEST_ROW_TIME_STATE_KEY = 'newest_row_time'
    _NEWEST_ROWS_STATE_KEY = 'newest_rows'
    _ROWS_COUNT_KEY = 'rows_count'


    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        self._state: Optional[dict] = None   # to be set in `obtain_input_pile()`

    def obtain_input_pile(self, **_kwargs):
        self._state = self.load_state()
        orig_data = self.obtain_orig_data()
        all_rows = self.all_rows_from_orig_data(orig_data)
        fresh_rows = self.get_fresh_rows_only(all_rows)
        if fresh_rows:
            return fresh_rows
        return None

    def make_default_state(self):
        return {
            self._NEWEST_ROW_TIME_STATE_KEY: self.get_oldest_possible_row_time(),
            self._NEWEST_ROWS_STATE_KEY: set(),
            self._ROWS_COUNT_KEY: 0,
        }

    def generate_input_data_dicts(self, fresh_rows, /):
        yield {'fresh_rows': fresh_rows}

    def get_output_data_body(self, *, fresh_rows, **kwargs):
        return self.output_data_from_fresh_rows(fresh_rows)

    def after_completed_publishing(self):
        super().after_completed_publishing()
        self.save_state(self._state)


    #
    # Stuff that can be overridden in subclasses (only if needed,
    # as sensible defaults are provided -- *except* for the three
    # abstract methods: `obtain_orig_data()`, `pick_raw_row_time()`
    # and `clean_row_time()`)

    # * basic raw event attributes:

    raw_type = 'file'
    content_type = 'text/csv'

    # * stuff related to writable state management:

    def get_oldest_possible_row_time(self):
        """
        The value returned by this method should sort as *less than*
        any real row time returned by `clean_row_time()`.

        **Important:** when implementing your subclass, you need to
        ensure that the value returned by this method meets the above
        condition for any non-`None` value returned by `clean_row_time()`.

        The value returned by the default implementation of this method
        is `""` (empty `str`) -- appropriate for such implementations
        of `clean_row_time()` that produce ISO-8601-formatted strings.
        Note that for other implementations of `clean_row_time()` the
        appropriate value may be, for example, `datetime.datetime.min`
        or the `0` integer...

        See also: the docs of the method `clean_row_time()` and the
        description of the return value of the method `extract_row_time()`
        (in its docs).
        """
        return ''

    # * obtaining original data:

    def obtain_orig_data(self) -> bytes:
        """
        An abstract method: obtain the original raw data and return it.

        Example implementation:

            return RequestPerformer.fetch(method='GET',
                                          url=self.config['...some-option...'],
                                          retries=self.config['...another-option...'])

        (Though, in practice -- when it comes to obtaining the original
        data with the `RequestPerformer` stuff -- you should use the
        `BaseDownloadingTimeOrderedRowsCollector` class, rather than
        implement `RequestPerformer`-based `obtain_orig_data()` by your
        own.)
        """
        raise NotImplementedError

    # * decoding + splitting original data:

    def all_rows_from_orig_data(self, orig_data: bytes):
        decoded = self.decode_orig(orig_data)
        return self.split_orig(decoded)

    def decode_orig(self, orig_data: bytes):
        return orig_data.decode('utf-8', 'surrogateescape')

    def split_orig(self, decoded):
        return decoded.split('\n')

    # * re-joining + encoding output data:

    def output_data_from_fresh_rows(self, fresh_rows) -> bytes:
        joined = self.join_output(fresh_rows)
        return self.encode_output(joined)

    def join_output(self, fresh_rows):          # should be `split_orig()`'s reversion
        return '\n'.join(fresh_rows)

    def encode_output(self, joined) -> bytes:   # should be `decode_orig()`'s reversion
        return joined.encode('utf-8', 'surrogateescape')

    # * selection of fresh rows:

    def get_fresh_rows_only(self, all_rows):
        prev_newest_row_time = self._state[self._NEWEST_ROW_TIME_STATE_KEY]
        prev_newest_rows = self._state[self._NEWEST_ROWS_STATE_KEY]
        # (a legacy state may not include `rows_count`)
        prev_rows_count = self._state.get(self._ROWS_COUNT_KEY)

        newest_row_time = None
        newest_rows = set()
        rows_count = 0

        fresh_rows_and_their_times = []

        for row in all_rows:
            row_time = self.extract_row_time(row)
            if row_time is None:
                continue

            rows_count += 1

            if row_time < prev_newest_row_time:
                # this row is old enough to assume it must have already
                # been collected (within a past collector run)
                continue

            if newest_row_time is None or row_time > newest_row_time:
                # this row time is *newer* than any of the rows already
                # processed within this run
                newest_row_time = row_time
                newest_rows.clear()

            assert row_time <= newest_row_time
            if row_time == newest_row_time:
                # this row is amongst those with the *newest* row time
                # (at least so far within this run)
                newest_rows.add(row)

            if row in prev_newest_rows:
                # this row is amongst those which had the *newest*
                # row time within the previous collector run (so,
                # in particular, must have already been collected)
                assert row_time == prev_newest_row_time
                continue

            # this row has *not* been collected yet -> let's collect it
            fresh_rows_and_their_times.append((row, row_time))

        fresh_rows_and_their_times.reverse()   # <- as the original order is often newest-to-oldest
        fresh_rows_and_their_times.sort(   # <- let's ensure the row order will be oldest-to-newest
            key=operator.itemgetter(1))    #    (not a *must* here, but still a welcome feature...)
        fresh_rows = [row for row, _ in fresh_rows_and_their_times]

        self._check_counts(prev_rows_count, rows_count, fresh_rows)

        if fresh_rows:
            self._state.update({
                self._NEWEST_ROW_TIME_STATE_KEY: newest_row_time,
                self._NEWEST_ROWS_STATE_KEY: newest_rows,
                self._ROWS_COUNT_KEY: rows_count,
            })

            # sanity assertions
            fresh_newest_rows = newest_rows - prev_newest_rows
            assert newest_row_time is not None and fresh_newest_rows
        else:
            # sanity assertions
            assert (newest_row_time is None and not newest_rows
                    or
                    newest_row_time == prev_newest_row_time and newest_rows == prev_newest_rows)

        return fresh_rows


    def extract_row_time(self, row):
        """
        Extract the row time indicator from the given row.

        Args/kwargs:
            `row`:
                An item yielded by an iterable returned by
                `all_rows_from_orig_data()`.

        Returns:
            *Either* `None` -- indicating that `row` should just be
            ignored (skipped); *or* a sortable date/time value, i.e.,
            an object that represents the date or timestamp extracted
            from `row`, e.g., an ISO-8601-formatted string (that
            represents some date or date+time), or a `float`/`int`
            value being a UNIX timestamp, or a `datetime.datetime`
            instance; its type does not matter -- provided that such
            values (returned by this method, and also by the method
            `get_oldest_possible_row_time()`) sort in a sensible way:
            a newer one is always greater than an older one, and values
            representing the same time are always equal.

        This is a template method that calls the following methods:

        * `should_row_be_used()` (has a sensible default implementation
          but, of course, can be overridden/extended in your subclass
          if needed) -- takes the given `row` and returns a boolean
          value; if a false value is returned, the result of the whole
          `extract_row_time()` call will be `None`, and calls of the
          further methods (that is, of `pick_raw_row_time()` and
          `clean_row_time()`) will *not* be made;

        * `pick_raw_row_time()` (must be implemented in subclasses)
          -- takes the given `row` and extracts the raw value of its
          date-or-timestamp field, and then returns that raw value
          (typically, as a `str`); alternatively it can return `None`
          (to indicate that the whole row should be ignored) -- then
          the result of the whole `extract_row_time()` call will also
          be `None`, and the call of `clean_row_time()` will *not* be
          made;

        * `clean_row_time()` (must be implemented in subclasses) --
          takes the value just returned by `pick_raw_row_time()` and
          cleans it (i.e., validates and normalizes -- in particular,
          converts to some target type, if needed), and then returns
          the cleaned value; alternatively it can return `None` (to
          indicate that the whole row should be ignored); the returned
          value will become the result of the whole `extract_row_time()`
          call.
        """
        if not self.should_row_be_used(row):
            return None
        raw_row_time = self.pick_raw_row_time(row)
        if raw_row_time is None:
            return None
        return self.clean_row_time(raw_row_time)

    def should_row_be_used(self, row):
        """
        See the docs of `extract_row_time()`.

        The default implementation of this method returns `False` if
        the given `row` starts with the `#` character or contains only
        whitespace characters (or no characters at all); otherwise the
        returned value is `True`.
        """
        return row.strip() and not row.startswith('#')

    def pick_raw_row_time(self, row):
        """
        An abstract method. See also the docs of `extract_row_time()`.

        Below we present an implementation for a case when data rows
        are expected to be formatted according to the following pattern:
        `"<row number>","<row date+time>",<other data fields...>`.

            def pick_raw_row_time(self, row):
                # (here we use `extract_field_from_csv_row()` --
                # imported from `n6lib.csv_helpers`)
                return extract_field_from_csv_row(row, column_index=1)

        An alternative version of the above example:

            def pick_raw_row_time(self, row):
                # Here we return `None` if an error occurs when trying
                # to parse the row -- because:
                # * we assume that (for our particular data source)
                #   some wrongly formatted rows may appear,
                # * and we want to skip such rows.
                try:
                    return extract_field_from_csv_row(row, column_index=1)
                except Exception as exc:
                    LOGGER.warning(
                        'Cannot extract the time field from the %a row '
                        '(%a) -- so the row will be skipped.', row, exc)
                    return None
        """
        raise NotImplementedError

    def clean_row_time(self, raw_row_time):
        """
        An abstract method. See also the docs of `extract_row_time()`.

        An example implementation for a case when `raw_row_time` is
        expected to be an ISO-8601-formatted date+time indicator --
        such as `"2020-01-23T19:52:17+01:00"`:

            def clean_row_time(self, raw_row_time):
                # (here we use `parse_iso_datetime_to_utc()` --
                # imported from `n6lib.datetime_helpers`)
                return str(parse_iso_datetime_to_utc(raw_row_time))

        An alternative version of the above example:

            def clean_row_time(self, raw_row_time):
                # Here we return `None` if a conversion error occurs
                # -- because:
                # * we assume that (for our particular data source)
                #   rows containing wrongly formatted time indicators
                #   may appear,
                # * and we want to skip such rows.
                try:
                    return str(parse_iso_datetime_to_utc(raw_row_time))
                except ValueError:
                    LOGGER.warning(
                        'Cannot parse %a as an ISO date+time so the row '
                        'containing it will be skipped.', raw_row_time)
                    return None

        **Important:** the resultant value, if not `None`, must be
        compatible, in terms of sorting, with the value returned by
        `get_oldest_possible_row_time()` (see its docs, as well as the
        return value description in the docs of `extract_row_time()`).
        """
        raise NotImplementedError

    def _check_counts(self, prev_rows_count, rows_count, fresh_rows):
        problems = []

        if len(fresh_rows) != len(set(fresh_rows)):
            problems.append('Found duplicates among the fresh rows.')

        if prev_rows_count is not None:
            expected_rows_count = prev_rows_count + len(fresh_rows)
            if rows_count != expected_rows_count:
                problems.append(
                    f'The currently stated count of all rows ({rows_count}) '
                    f'is not equal to the sum of the count stated by the '
                    f'previous run of the collector ({prev_rows_count}) '
                    f'and the count of the currently collected fresh rows '
                    f'({len(fresh_rows)}). It means that we are faced with '
                    f'at least one of the following cases:'

                    f'\n* the data provided by the external source has '
                    f'changed in such a way that the expected count of '
                    f'the rows which should have already been collected '
                    f'(according to the current data from the external '
                    f'source) is different than the actual count of the '
                    f'already collected rows (by the previous runs of '
                    f'the collector), or'

                    f'\n* some of the fresh rows duplicate some of the '
                    f'rows collected earlier.')

        if problems:
            separator = '\n\nThe following problem also occurred:\n\n'
            msg = separator.join(problems)
            if self.config['row_count_mismatch_is_fatal']:
                raise ValueError(msg)
            LOGGER.warning(msg)


class BaseDownloadingTimeOrderedRowsCollector(BaseDownloadingCollector,
                                              BaseTimeOrderedRowsCollector):

    """
    TODO: docs.
    """

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]

        url :: str
    ''')

    def obtain_orig_data(self) -> bytes:
        return self.download(self.config['url'])


#
# Entry point factory

def add_collector_entry_point_functions(module):
    if isinstance(module, str):
        module = sys.modules[module]
    for name in dir(module):
        if not name.startswith('_'):
            obj = getattr(module, name)
            is_collector_class = isinstance(obj, type) and issubclass(obj, AbstractBaseCollector)
            if is_collector_class:
                assert hasattr(obj, 'run_script')
                setattr(module, f'{name}_main', obj.run_script)
