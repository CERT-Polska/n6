# Copyright (c) 2021 NASK. All rights reserved.

import contextlib
import copy
import string
from smtplib import (
    SMTPException,
    SMTPRecipientsRefused,
)
from typing import (
    Any,
    ContextManager,
    Dict,
    Optional,
    Set,
    Tuple,
    Union,
)

from n6lib.common_helpers import make_exc_ascii_str
from n6lib.config import (
    Config,
    ConfigError,
    ConfigMixin,
    ConfigSection,
)
from n6lib.log_helpers import get_logger
from n6lib.mail_sending_api import (
    AddressHeaderRaw,
    MailMessageBuilder,
    MailSendingAPI,
    RenderFrom,
)
from n6lib.structured_data_conversion.converters import (
    DataConversionError,
    NameValuePairConverter,
    NamespaceMappingConverter,
)
from n6lib.typing_helpers import String


LOGGER = get_logger(__name__)


class MailNoticesAPI(ConfigMixin):

    """
    This class constructs a higher-level mail notice dispatch interface
    on top of the lower lever stuff defined in `n6lib.mail_sending_api`.

    A small example of use:

        with mail_notices_api.dispatcher('org_config_update_requested', lang='EN') as dispatch:
            dispatch('somebody@example.com', my_data_dict, lang='PL')
            dispatch('another@wherever.example.org', another_dict)  # no lang, so defaults to 'EN'
    """

    #
    # Configuration-related stuff

    MAIL_COMPONENT_TEMPLATE_NAME_PREFIX = '$:'

    config_spec = r'''
        [mail_notices_api]

        # Should mail notices be dispatched at all? If this option is
        # false then any invocations of a dispatcher obtained from a
        # context manager returned by the `MailNoticesAPI.dispatcher()`
        # method do nothing, and *no* other options from this section or
        # from the `[mail_sending_api]`/`[jinja_template_based_renderer]`
        # sections (which normally are also engaged) are used by the
        # `MailNoticesAPI` machinery.
        active = false :: bool

        # The value of the following option, if not being empty, should
        # be a Python dict literal representing a dict that maps *notice
        # keys* (str, e.g.: 'org_config_update_requested') to dicts that
        # map 2-character codes of a supported *language* (such as 'EN'
        # or 'PL) to dicts specifying the following mail components:
        # *body*, *subject*, *sender* and (optionally) *misc headers*
        # (which stands for *miscellaneous mail headers*).
        #
        # Lack of a certain *notice key* means that the mail notices
        # stuff is not active for that *notice key* (meaning that any
        # invocations of a dispatcher obtained from a context manager
        # returned by any `MailNoticesAPI.dispatcher(<that notice key>)`
        # call do nothing).
        #
        # Each of the *mail components* dicts (i.e., the dicts mentioned
        # above as those specifying mail components) contains some or
        # all of the following items:
        #
        # * 'body' -- a *string value* (required),
        #
        # * 'subject' -- a *string value* (required),
        #
        # * 'sender' -- a *string value* (required if the value of
        #   the `default_sender` option [see below] is left empty,
        #   otherwise optional),
        #
        # * 'misc_headers' -- a dict that maps any mail header names
        #   to their values, specified as *string values* (optional);
        #
        # **Important note:** each of the *string values* mentioned
        # above shall be a `str` which is:
        #
        # * (1) **either** a Jinja template name preceded with a `$:`
        #   (*dollar sign* followed by *colon*) marker,
        #
        # * (2) **or** any other string -- which *literally* specifies
        #   the item's value (**no HTML/XML escaping** will be applied
        #   to it!).
        #
        # Ad (1): those Jinja templates will be used by an instance of
        # `JinjaTemplateBasedRenderer` (see `n6lib.jinja_helpers` and
        # the `[jinja_template_based_renderer]` config section) as the
        # basis for rendering of actual values -- with the *rendering
        # context* containing the `data_dict` variable being a deep copy
        # of the `notice_data` dict passed in to the dispatcher [where
        # *dispatcher* is a callable object obtained as the `as` target
        # (`__enter__()`'s return value) of a context manager returned
        # by `MailNoticesAPI.dispatcher()`].
        #
        # **Beware** that HTML/XML escaping will be applied **only if**
        # the template name has a `.html`, `.htm` or `.xml` suffix
        # (checked in a case-insensitive manner).
        #
        # For example templates -- see the template files in the
        # `data/templates` subdirectory of the `n6lib` package source
        # tree.
        #
        # The default value of this option seems to be quite sensible
        # for most important use cases. The basic versions of the
        # Jinja templates it refers to are already defined in the
        # `data/templates` subdirectory of the `n6lib` package; note:
        # you can customize them by creating your own template files --
        # named the same but placed in (an)other location(s) (specified
        # with the `template_locations` configuration option in the
        # section `[jinja_template_based_renderer]`).
        notice_key_to_lang_to_mail_components =
            {
                'mfa_config_done': {
                    'EN': {
                        'subject':
                            'New configuration of multi-factor authentication',
                        'body': '$:mail_notice__mfa_config_done__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Nowa konfiguracja uwierzytelniania wielosk\u0142adnikowego',
                        'body': '$:mail_notice__mfa_config_done__PL.txt',
                    },
                },
                'mfa_config_erased': {
                    'EN': {
                        'subject':
                            'Deleted configuration of multi-factor authentication',
                        'body': '$:mail_notice__mfa_config_erased__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Usuni\u0119ta konfiguracja uwierzytelniania wielosk\u0142adnikowego',
                        'body': '$:mail_notice__mfa_config_erased__PL.txt',
                    },
                },

                'new_org_and_user_created': {
                    'EN': {
                        'subject':
                            'Welcome to the n6 system',
                        'body': '$:mail_notice__new_org_and_user_created__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Witamy w systemie n6',
                        'body': '$:mail_notice__new_org_and_user_created__PL.txt',
                    },
                },

                'org_config_update_requested': {
                    'EN': {
                        'subject':
                            'A new request to update the organization configuration',
                        'body': '$:mail_notice__org_config_update_requested__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Nowa propozycja zmian w konfiguracji Twojej organizacji',
                        'body': '$:mail_notice__org_config_update_requested__PL.txt',
                    },
                },
                'org_config_update_applied': {
                    'EN': {
                        'subject':
                            'Acceptance of the requested update of the organization configuration',
                        'body': '$:mail_notice__org_config_update_applied__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Akceptacja zmian w konfiguracji Twojej organizacji',
                        'body': '$:mail_notice__org_config_update_applied__PL.txt',
                    },
                },
                'org_config_update_rejected': {
                    'EN': {
                        'subject':
                            'Rejection of the requested update of the organization configuration',
                        'body': '$:mail_notice__org_config_update_rejected__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Odmowa wprowadzenia zmian w konfiguracji Twojej organizacji',
                        'body': '$:mail_notice__org_config_update_rejected__PL.txt',
                    },
                },

                'password_reset_done': {
                    'EN': {
                        'subject':
                            'New log-in password',
                        'body': '$:mail_notice__password_reset_done__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Nowe has\u0142o logowania',
                        'body': '$:mail_notice__password_reset_done__PL.txt',
                    },
                },
                'password_reset_requested': {
                    'EN': {
                        'subject':
                            'Setting new log-in password',
                        'body': '$:mail_notice__password_reset_requested__EN.txt',
                    },
                    'PL': {
                        'subject':
                            'Ustawianie nowego has\u0142a logowania',
                        'body': '$:mail_notice__password_reset_requested__PL.txt',
                    },
                },
            } :: notice_key_to_lang_to_mail_components

        # The following option specifies (using a 2-character string)
        # the *default language* -- to be used when *neither* of the
        # `MailNoticesAPI.dispatcher()` and `<the obtained dispatcher>()`
        # invocations has included the `lang` argument (specifying the
        # desired mail notice language variant); but also when it has
        # been included but its value is missing from the *notice key*-
        # specific subdict of the `notice_key_to_lang_to_mail_components`
        # dict (see its description above).
        default_lang = EN :: lang

        # The value of the following option, if not left empty, should
        # be a text to be used as the default value of the 'sender'
        # item of dicts that define mail components (see the above
        # description of the `notice_key_to_lang_to_mail_components`
        # option; the remarks about `$:`-prepended *template names*
        # and HTML/XML escaping apply also here).
        default_sender = :: single_mail_component

        # The value of the following option, if not left empty, should
        # be a Python dict literal that defines additional mail headers,
        # to be used to complement (but never overwrite) the items of
        # each 'misc_headers' dict (ad 'misc_headers` -- see the above
        # description of the `notice_key_to_lang_to_mail_components`
        # option; the remarks about `$:`-prepended *template names* and
        # HTML/XML escaping apply also here).
        common_misc_headers = :: name_to_single_mail_component
    '''

    @property
    def custom_converters(self):
        return {
            'notice_key_to_lang_to_mail_components': _conv_notice_key_to_lang_to_mail_components,
            'lang': _conv_lang,
            'single_mail_component': _conv_single_mail_component,
            'name_to_single_mail_component': _conv_name_to_single_mail_component,
        }

    #
    # Public interface

    def __init__(self, settings=None):
        # type: (Optional[dict]) -> None
        self._settings = settings
        self._sending_api = MailSendingAPI(settings)
        self._config = self._get_config(settings)

    def is_active(self, notice_key=None):
        # type: (Optional[String]) -> bool
        if not self._config['active']:
            return False
        if notice_key is None:
            return True
        return notice_key in self._config['notice_key_to_lang_to_mail_components']

    def dispatcher(
        self,
        notice_key,                       # type: String
        lang=None,                        # type: Optional[String]
        suppress_and_log_smtp_exc=False   # type: bool
    ):
        # type: (...) -> ContextManager[MailNoticesDispatcher]
        return self._dispatcher_context_manager(notice_key, lang, suppress_and_log_smtp_exc)

    #
    # Internal helpers

    def _get_config(self, settings):
        config = self.get_config_section(settings)
        if config['default_sender'] is None:
            nkey_to_lang_to_mc = config['notice_key_to_lang_to_mail_components']
            nkey_lang_pairs_with_no_sender = sorted(
                (notice_key, lang)
                for notice_key, lang_to_mail_components in nkey_to_lang_to_mc.items()
                    for lang, mail_components in lang_to_mail_components.items()
                    if 'sender' not in mail_components)
            if nkey_lang_pairs_with_no_sender:
                raise ConfigError(
                    "[mail_notices_api] when `default_sender` is "
                    "not set then all *mail components* dicts within "
                    "`notice_key_to_lang_to_mail_components` should "
                    "contain the 'sender' key; it has been found that "
                    "for the following *notice key* and *language* "
                    "combinations the corresponding *mail components* "
                    "dicts do not contain 'sender': {}".format(', '.join(
                        '{!a} and {!a}'.format(*pair)
                        for pair in nkey_lang_pairs_with_no_sender)))
        return config

    @contextlib.contextmanager
    def _dispatcher_context_manager(self, notice_key, lang, suppress_and_log_smtp_exc):
        if self.is_active(notice_key):
            context_entered = important_done = False
            try:
                msg_builder = MailMessageBuilder(settings=self._settings)
                sending_api = self._sending_api
                actual_dispatcher = _ActualMailNoticesDispatcher(
                    msg_builder=msg_builder,
                    sending_api=sending_api,
                    config=self._config,
                    notice_key=notice_key,
                    fallback_lang=lang,
                    suppress_and_log_smtp_exc=suppress_and_log_smtp_exc)
                try:
                    with sending_api:
                        context_entered = True
                        yield actual_dispatcher
                        important_done = True
                except SMTPException:
                    if not suppress_and_log_smtp_exc:
                        raise
                    self._log_exc(notice_key, context_entered, important_done, exc_suppressed=True)
            except:
                self._log_exc(notice_key, context_entered, important_done)
                raise
            if not context_entered:
                assert suppress_and_log_smtp_exc
                yield _ErrorLoggingMailNoticesDispatcher(notice_key)
        else:
            yield _DummyMailNoticesDispatcher()

    def _log_exc(self, notice_key, context_entered, important_done, exc_suppressed=False):
        exc_descr = make_exc_ascii_str()
        msg_preamble = 'Suppressing an exception which ' if exc_suppressed else 'An exception '
        if important_done:
            LOGGER.warning(
                msg_preamble + (
                    'occurred *after* dealing with dispatch of %a '
                    'mail notice(s) [problem with closing the SMTP '
                    'connection?] (%s)'),
                notice_key,
                exc_descr)
        elif context_entered:
            LOGGER.error(
                msg_preamble + (
                    'occurred *while* dealing with dispatch of %a mail '
                    'notice(s) (%s) -- it broke the whole activity '
                    'during it, so it is probable that some or all '
                    'dispatch actions have not even been tried!'),
                notice_key,
                exc_descr,
                exc_info=exc_suppressed)
        else:
            LOGGER.error(
                msg_preamble + (
                    'occurred *before* dealing with dispatch of %a mail '
                    'notice(s) (%s) -- all dispatch actions must fail!'),
                notice_key,
                exc_descr,
                exc_info=exc_suppressed)


class MailNoticesDispatcher(object):

    #
    # Public interface

    active = None  # type: bool

    def __call__(
        self,
        to,                # type: Union[AddressHeaderRaw, RenderFrom]  # recipient address(es)
        notice_data=None,  # type: Optional[Dict[String, Any]]  # items of `data_dict` template var
        lang=None,         # type: Optional[String]             # 2-letter language code
    ):
        # type: (...) -> Tuple[Set[String], Dict[String, Tuple[int, String]]]

        # A concrete implementation should return a pair (2-element
        # tuple) consisting of:
        # * (1) a set of successful dispatch recipient (`To`) addresses
        #       (`str` objects);
        # * (2) a dict collecting information on *recipient problems*
        #       -- mapping failed dispatch recipient (`To`) addresses
        #       (`str` objects) to pairs (2-tuples) consisting of the
        #       following error data from the SMTP server:
        #       * (1) error code (`int`),
        #       * (2) message (`str`).
        raise NotImplementedError


#
# Non-public concrete implementations of `MailNoticesDispatcher`
#

class _DummyMailNoticesDispatcher(MailNoticesDispatcher):

    active = False

    def __call__(self, to, notice_data=None, lang=None):
        ok_recipients = set()
        recipient_problems = dict()
        return ok_recipients, recipient_problems


class _ErrorLoggingMailNoticesDispatcher(_DummyMailNoticesDispatcher):

    def __init__(self, notice_key):
        self._notice_key = notice_key

    def __call__(self, to, *args, **kwargs):
        LOGGER.error(
            'An earlier error (which should have already been logged) '
            'causes that a %a mail notice cannot be sent [to: %a]',
            self._notice_key, to)
        return super(_ErrorLoggingMailNoticesDispatcher, self).__call__(to, *args, **kwargs)


class _ActualMailNoticesDispatcher(MailNoticesDispatcher):

    active = True

    def __init__(self, msg_builder, sending_api, config, notice_key, fallback_lang,
                 suppress_and_log_smtp_exc):
        self._msg_builder = msg_builder      # type: MailMessageBuilder
        self._sending_api = sending_api      # type: MailSendingAPI
        self._config = config                # type: ConfigSection
        self._notice_key = notice_key        # type: String
        self._fallback_lang = fallback_lang  # type: Optional[String]
        self._suppress_and_log_smtp_exc = suppress_and_log_smtp_exc  # type: bool

    def __call__(self, to, notice_data=None, lang=None):
        mail_components = self._mail_components_from_config(lang)
        message = self._build_message(mail_components, to, notice_data)
        ok_recipients, recipient_problems = self._send_message(message, to)
        return ok_recipients, recipient_problems


    def _mail_components_from_config(self, lang):
        config = self._config
        notice_key = self._notice_key
        assert notice_key in config['notice_key_to_lang_to_mail_components']
        lang_to_mail_components = config['notice_key_to_lang_to_mail_components'][notice_key]
        assert config['default_lang'].isupper()
        lang = (lang
                or self._fallback_lang
                or config['default_lang']).upper()
        mail_components = lang_to_mail_components.get(lang)
        if mail_components is None:
            if config['default_lang'] == lang:
                raise ValueError(
                    'no mail components configuration for the notice '
                    'key {!a} and the language {!a} (which is also '
                    'the default language)'.format(
                        notice_key,
                        lang))
            mail_components = lang_to_mail_components.get(config['default_lang'])
            if mail_components is None:
                raise ValueError(
                    'no mail components configuration for the notice '
                    'key {!a} -- neither for the language {!a} nor '
                    'for the default language {!a}'.format(
                        notice_key,
                        lang,
                        config['default_lang']))
        return mail_components

    def _build_message(self, mail_components, to, notice_data):
        self._msg_builder.clear()
        self._msg_builder.body = mail_components['body']
        self._msg_builder.subject = mail_components['subject']
        self._msg_builder.sender = mail_components.get('sender', self._config['default_sender'])
        self._msg_builder.misc_headers = self._get_misc_headers(mail_components)
        assert (self._msg_builder.body          # (this condition is guaranteed by the custom
                and self._msg_builder.subject   # config converters of `MailNoticesAPI` or its
                and self._msg_builder.sender    # method `_get_config()`)
                and all(self._msg_builder.misc_headers.values()))
        self._msg_builder.to = to
        self._msg_builder.render_context = {'data_dict': copy.deepcopy(notice_data)}
        return self._msg_builder()

    def _get_misc_headers(self, mail_components):
        misc_headers = dict(mail_components.get('misc_headers', {}))
        for name, value in self._config.get('common_misc_headers', {}).items():
            misc_headers.setdefault(name, value)
        return misc_headers

    def _send_message(self, message, to):
        ok_recipients = set()
        recipient_problems = dict()
        try:
            ok_recipients, recipient_problems = self._sending_api.send_message(
                message,
                extra_headers={'X-N6-Notice-Key': self._notice_key})
        except SMTPRecipientsRefused as exc:
            if not self._suppress_and_log_smtp_exc:
                raise
            recipient_problems = exc.recipients
            self._log_smtp_recipients_exc(recipient_problems)
        except SMTPException:
            if not self._suppress_and_log_smtp_exc:
                raise
            self._log_other_smtp_exc(to)
        else:
            self._log_non_exc_summaries(ok_recipients, recipient_problems)
        return ok_recipients, recipient_problems

    def _log_smtp_recipients_exc(self, recipient_problems):
        recipients_str = ', '.join(map(ascii, sorted(recipient_problems.keys())))
        exc_descr = make_exc_ascii_str()
        LOGGER.error(
            'Suppressing a mail-recipients-related exception which '
            'signals that a %a mail notice could not be sent to '
            'any of the given recipients: %s (%s)',
            self._notice_key, recipients_str, exc_descr)

    def _log_other_smtp_exc(self, to):
        exc_descr = make_exc_ascii_str()
        LOGGER.error(
            'Suppressing an exception which signals an error which '
            'caused that a %a mail notice could not be sent [to: %a] '
            '(%s)', self._notice_key, to, exc_descr, exc_info=True)

    def _log_non_exc_summaries(self, ok_recipients, recipient_problems):
        if recipient_problems:
            err_recipients_str = ', '.join(map(ascii, sorted(recipient_problems.keys())))
            LOGGER.warning(
                'A %a mail notice could not be sent to *some* '
                'of the given recipients -- namely to: %s (%a)',
                self._notice_key, err_recipients_str, recipient_problems)
        if ok_recipients:
            ok_recipients_str = ', '.join(map(ascii, sorted(ok_recipients)))
            LOGGER.info(
                'A %a mail notice has been sent to: %s',
                self._notice_key, ok_recipients_str)


#
# Non-public stuff related to conversion of configuration option values
#

def _conv_notice_key_to_lang_to_mail_components(opt_value):
    if not opt_value:
        return {}
    raw_dict = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)
    [result] = _adjust_notice_key_to_lang_to_mail_components(raw_dict)
    return result


def _conv_lang(opt_value):
    [result] = _adjust_lang(opt_value)
    return result


def _conv_single_mail_component(opt_value):
    if not opt_value:
        return None
    [result] = _adjust_single_mail_component(opt_value)
    return result


def _conv_name_to_single_mail_component(opt_value):
    if not opt_value:
        return {}
    raw_dict = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)
    [result] = _adjust_name_to_single_mail_component(raw_dict)
    return result


# Attention! *Config converters* and *structured data converters* are
# **two distinct concepts** -- even though in this module we make them
# cooperate. Above we defined some *config converters* that make use of
# the *structured data converters* defined below. Don't get confused!


def _adjust_lang(value):
    assert isinstance(value, str)  # already guaranteed by config-related stuff
    value = value.upper()
    if len(value) == 2 and set(value).issubset(string.ascii_uppercase):
        yield value
    else:
        raise DataConversionError('{!a} is not a valid two-letter '
                                  'language code'.format(value))


def _adjust_single_mail_component(value):
    if not isinstance(value, str):
        raise DataConversionError('{!a} is not a str'.format(value))
    if value.startswith(MailNoticesAPI.MAIL_COMPONENT_TEMPLATE_NAME_PREFIX):
        template_name = value[len(MailNoticesAPI.MAIL_COMPONENT_TEMPLATE_NAME_PREFIX):]
        if not template_name.strip():
            raise DataConversionError('template name cannot be empty or whitespace-only')
        value = RenderFrom(template_name)
    elif not value.strip():
        raise DataConversionError('value cannot be empty or whitespace-only')
    yield value


_adjust_name_to_single_mail_component = NamespaceMappingConverter(
    free_item_converter_maker=NameValuePairConverter.maker(
        value_converter_maker=lambda: _adjust_single_mail_component,
    ),
)

_adjust_mail_components = NamespaceMappingConverter(
    required_input_names=[
        'body',
        'subject',
    ],
    input_name_to_item_converter_maker={
        'body': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_single_mail_component,
        ),
        'subject': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_single_mail_component,
        ),
        'sender': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_single_mail_component,
        ),
        'misc_headers': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_name_to_single_mail_component,
        ),
    },
)

_adjust_lang_to_mail_components = NamespaceMappingConverter(
    free_item_converter_maker=NameValuePairConverter.maker(
        name_converter_maker=lambda: _adjust_lang,
        value_converter_maker=lambda: _adjust_mail_components,
    ),
)

_adjust_notice_key_to_lang_to_mail_components = NamespaceMappingConverter(
    free_item_converter_maker=NameValuePairConverter.maker(
        value_converter_maker=lambda: _adjust_lang_to_mail_components,
    ),
)
