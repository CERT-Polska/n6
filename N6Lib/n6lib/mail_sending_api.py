# Copyright (c) 2020-2021 NASK. All rights reserved.

import copy
import datetime
import smtplib
from email.generator import BytesGenerator
from email.message import EmailMessage
from email.policy import (
    EmailPolicy,
    SMTP as EMAIL_POLICY_FOR_SMTP,
)
from email.utils import formatdate
from io import BytesIO
from math import trunc
from typing import (
    Any,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
)

from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    EMAIL_OVERRESTRICTED_SIMPLE_REGEX,
    ascii_str,
    make_hex_id,
)
from n6lib.config import (
    ConfigError,
    ConfigMixin,
)
from n6lib.context_helpers import ThreadLocalContextDeposit
from n6lib.datetime_helpers import int_timestamp_from_datetime
from n6lib.jinja_helpers import JinjaTemplateBasedRenderer
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import String


LOGGER = get_logger(__name__)


#
# Constants
#

SUBJECT_MAX_LENGTH = 160

ADDR_HEADER_LOWERCASE_NAMES = frozenset({
    'sender',
    'from',
    'to',
})

# Maybe TODO later: we may want to support these headers (or some of them).
# That, of course, would need certain changes in the implementation of
# `MailSendingAPI.send_message()`.
UNSUPPORTED_HEADER_NAMES = frozenset({
    'Cc',
    'Bcc',
    'Resent-Date',
    'Resent-From',
    'Resent-Sender',
    'Resent-To',
    'Resent-Cc',
    'Resent-Bcc',
    'Resent-Message-ID',
})


#
# Static typing helpers
#

UsualHeaderRaw = String
AddressHeaderRaw = Union[String, Iterable[String]]
DateHeaderRaw = Union[datetime.datetime, String]
HeaderRaw = Union[
    UsualHeaderRaw,
    AddressHeaderRaw,
    DateHeaderRaw,
]

# (types of something that *either* is a `dict` *or* can be coerced
# to `dict` or passed as the positional argument to `dict.update()`)
DictyCollection = Union[
    Mapping[String, Any],
    Iterable[Tuple[String, Any]],
]
DictyCollectionOfHeaderRaw = Union[
    Mapping[String, HeaderRaw],
    Iterable[Tuple[String, HeaderRaw]],
]
DictyCollectionOfHeaderRawOrRenderFrom = Union[
    Mapping[String, Union[HeaderRaw, 'RenderFrom']],
    Iterable[Tuple[String, Union[HeaderRaw, 'RenderFrom']]],
]


#
# Actual classes
#

class _MessageHelpersMixin(object):

    def copy_message(self, message):
        assert isinstance(message, EmailMessage)
        assert isinstance(message.policy, EmailPolicy)
        return self._deep_copy_keeping_orig_policy_objects(message)

    def add_multiple_headers(self, message, headers):
        # type: (EmailMessage, DictyCollectionOfHeaderRaw) -> None
        assert isinstance(message, EmailMessage)
        assert isinstance(message.policy, EmailPolicy)
        for header_name, value in sorted(dict(headers).items()):
            message[header_name] = self.prepare_header_value(header_name, value)

    def drop_and_add_header(self, message, header_name, new_header_value):
        # type: (EmailMessage, String, HeaderRaw) -> None
        assert isinstance(message, EmailMessage)
        assert isinstance(message.policy, EmailPolicy)
        del message[header_name]
        message[header_name] = self.prepare_header_value(header_name, new_header_value)

    def prepare_header_value(self, header_name, value):
        # type: (String, HeaderRaw) -> String
        if header_name.lower() in ADDR_HEADER_LOWERCASE_NAMES:
            value = self._adjust_addr_value(value)
        elif isinstance(value, datetime.datetime):
            value = self._format_dt(value)
        if not isinstance(value, str):
            raise TypeError('{!a} is not a `str`'.format(value))
        if header_name.lower() == 'subject':
            self.validate_subject_value(value)
        return value

    def validate_subject_value(self, value):
        if value is None:
            raise ValueError('subject is missing')
        if not value.strip():
            raise ValueError('subject is blank')
        if len(value) > SUBJECT_MAX_LENGTH:
            raise ValueError(
                'subject is too long; maximum length of its *not-encoded* '
                'form considered by us safe *and* reasonable is: {} '
                'characters; got: {} characters ({!a})'.format(
                    SUBJECT_MAX_LENGTH,
                    len(value),
                    value))


    def _deep_copy_keeping_orig_policy_objects(self, message):
        # Note: objects that are set as the `policy` attribute of a
        # message or of any of its parts, are generally considered
        # immutable, so copying them is not necessary. Moreover, because
        # they have many various attributes, we deem making deep copies
        # of them too risky when it comes to possible unknown problems
        # (e.g., related to copying "too much" or "too less") -- so we
        # want to keep all those policy objects *as-is*, without copying
        # them.
        all_parts = message.walk()
        all_policies = (getattr(part, 'policy', None)
                        for part in all_parts)
        id_to_policy = {id(policy): policy
                        for policy in all_policies
                        if policy is not None}
        assert id(message.policy) in id_to_policy
        return copy.deepcopy(message, memo=id_to_policy)  # noqa

    def _adjust_addr_value(self, value):
        if not value:
            raise ValueError('no e-mail address given (got: {!a})'.format(value))
        if isinstance(value, str):
            all_values = [value]
        else:
            all_values = list(value)
            if not all_values:
                raise ValueError('no e-mail address given (got: {!a})'.format(value))
        assert isinstance(all_values, list) and all_values
        return ", ".join(all_values)

    def _format_dt(self, value):
        timestamp = int_timestamp_from_datetime(value)
        return formatdate(timestamp, localtime=True)


class MailSendingAPI(ConfigMixin, _MessageHelpersMixin):

    """
    TODO: docs
    """

    config_spec = '''
        [mail_sending_api]
        smtp_host :: str
        smtp_port :: int
        smtp_login = "" :: str
        smtp_password = "" :: str
    '''

    def __init__(self, settings=None):
        self.config = self._get_config(settings)
        self._smtp_client_deposit = ThreadLocalContextDeposit(
            repr_token=self.__class__.__qualname__)

    def __enter__(self):
        self._smtp_client_deposit.on_enter(context_factory=self._connect)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._smtp_client_deposit.on_exit(exc_type, exc, tb, context_finalizer=self._disconnect)

    def send_message(self,
                     message,             # type: EmailMessage
                     sender=None,         # type: Optional[UsualHeaderRaw]
                     to=None,             # type: Optional[AddressHeaderRaw]
                     subject=None,        # type: Optional[UsualHeaderRaw]
                     extra_headers=None   # type: Optional[DictyCollectionOfHeaderRaw]
                     ):   # type: (...) -> Tuple[Set[String], Dict[String, Tuple[int, String]]]

        if not isinstance(message, EmailMessage):
            raise TypeError('unsupported type of `message`: '
                            '{!a}'.format(type(message)))
        if not isinstance(message.policy, EmailPolicy):
            raise TypeError('unsupported type of `message.policy`: '
                            '{!a}'.format(type(message.policy)))

        message = self.copy_message(message)

        if sender is not None:
            del message['Sender']
            self.drop_and_add_header(message, 'From', sender)
        if to is not None:
            self.drop_and_add_header(message, 'To', to)
        if subject is not None:
            self.drop_and_add_header(message, 'Subject', subject)
        if extra_headers is not None:
            self.add_multiple_headers(message, extra_headers)

        from_addr_items = self._from_addr_items(message)
        from_addr = self._pure_addr(from_addr_items[0])
        to_addr_items = self._to_addr_items(message)
        to_addrs = list(map(self._pure_addr, to_addr_items))

        if 'Date' not in message:
            message['Date'] = self.prepare_header_value('Date', datetime.datetime.utcnow())
        if 'Message-ID' not in message:
            message['Message-ID'] = self._generate_message_id(message['Date'], from_addr)
        if 'Sender' not in message and len(from_addr_items) >= 2:  # see: RFC 5322, section 3.6.2
            message['Sender'] = str(from_addr_items[0])

        self.validate_subject_value(message['Subject'])
        self._verify_no_unsupported_headers(message)

        client = self._get_current_smtp_client()
        (flattening_policy,
         mail_options) = self._prepare_flattening_policy_and_mail_options(message, client)
        flattened_message = self._flatten_message(message, flattening_policy)
        recipient_problems = client.sendmail(from_addr,
                                             to_addrs,
                                             flattened_message,
                                             mail_options=mail_options)
        if recipient_problems:
            # Some recipients have been rejected by the SMTP server,
            # but not all (if all of them had been rejected an exception
            # would have been raised).
            LOGGER.warning('Unable to send e-mail to some recipient(s): %a', recipient_problems)

        ok_recipients = set(to_addrs).difference(recipient_problems.keys())
        return (
            # A set of successful dispatch recipient (`To`) addresses
            # (`str` objects).
            ok_recipients,          # type: Set[String]

            # A dict that collects information on *recipient problems*,
            # i.e., that maps failed dispatch recipient (`To`) addresses
            # (`str` objects) to pairs (2-tuples) consisting of the
            # following error data from the SMTP server:
            #   * (1) error code (`int`),
            #   * (2) message (`str`).
            recipient_problems,     # type: Dict[String, Tuple[int, String]]
        )


    def _get_config(self, settings):
        config = self.get_config_section(settings=settings)
        if config['smtp_login'] or config['smtp_password']:
            if not config['smtp_login']:
                raise ConfigError(
                    '[mail_sending_api] `smtp_login` is missing '
                    '(though `smtp_password` is present)')
            if not config['smtp_password']:
                raise ConfigError(
                    '[mail_sending_api] `smtp_password` is missing '
                    '(though `smtp_login` is present)')
        return config

    def _connect(self):
        # TODO: add SSL/TLS as an option.
        client = smtplib.SMTP(self.config['smtp_host'],
                              self.config['smtp_port'])
        if self.config['smtp_login']:
            assert self.config['smtp_password']
            client.login(self.config['smtp_login'],
                         self.config['smtp_password'])
        return client

    def _disconnect(self, client, *_exc_info):
        client.quit()

    def _from_addr_items(self, message):
        addr_header_values = (message.get_all('Sender') if 'Sender' in message
                              else message.get_all('From'))
        addr_items = self._addr_items_from_header_values(addr_header_values)
        if not addr_items:
            raise ValueError('no `Sender`/`From` address(es) specified')
        return addr_items

    def _to_addr_items(self, message):
        addr_header_values = message.get_all('To')
        addr_items = self._addr_items_from_header_values(addr_header_values)
        if not addr_items:
            raise ValueError('no `To` address(es) specified')
        return addr_items

    def _addr_items_from_header_values(self, addr_header_values):
        return [addr_item
                for header_value in addr_header_values
                    for addr_item in header_value.addresses]

    def _pure_addr(self, addr_item):
        addr = addr_item.addr_spec
        assert isinstance(addr, str)
        if not EMAIL_OVERRESTRICTED_SIMPLE_REGEX.search(addr):
            raise ValueError(
                'e-mail address {!a} does not match '
                'n6lib.common_helpers.EMAIL_OVERRESTRICTED_SIMPLE_REGEX'
                .format(addr))
        assert addr == ascii_str(addr)
        return addr

    def _generate_message_id(self, date_header, from_addr):
        timestamp = date_header.datetime.timestamp()
        msg_id = 'n6.{}.{}'.format(trunc(timestamp), make_hex_id(length=32))
        _, domain = from_addr.split('@')
        return '<{}@{}>'.format(msg_id, domain)

    def _verify_no_unsupported_headers(self, message):
        for header_name in UNSUPPORTED_HEADER_NAMES:
            values = message.get_all(header_name)
            if values:
                raise NotImplementedError('header {!a} is not supported by {} '
                                          '(got: {!a})'.format(header_name,
                                                               self.__class__.__qualname__,
                                                               values))

    def _get_current_smtp_client(self):
        client = self._smtp_client_deposit.innermost_context
        if client is None:
            raise RuntimeError(
                'no SMTP connection is active (you need '
                'to make use of the {}\'s context manager '
                'interface)'.format(self.__class__.__qualname__))
        return client

    def _prepare_flattening_policy_and_mail_options(self, message, client):
        flattening_policy = message.policy
        mail_options = ()
        # See:
        # * https://bugs.python.org/issue32814
        # * https://github.com/python/cpython/pull/8303/files
        if flattening_policy.cte_type == '8bit':
            client.ehlo_or_helo_if_needed()
            if client.does_esmtp and client.has_extn('8bitmime'):
                mail_options += ('BODY=8BITMIME',)
            else:
                flattening_policy = flattening_policy.clone(cte_type='7bit')
        return flattening_policy, mail_options

    def _flatten_message(self, message, flattening_policy):
        bytes_io = BytesIO()
        generator = BytesGenerator(bytes_io, mangle_from_=False, policy=flattening_policy)
        generator.flatten(message, unixfrom=False, linesep='\r\n')
        return bytes_io.getvalue()


class MailMessageBuilder(_MessageHelpersMixin):

    """
    TODO: docs
    """

    PUBLIC_SETTABLE_ATTRS = frozenset({
        'body',
        'sender',
        'to',
        'subject',
        'misc_headers',
        'render_context',
        'policy',
    })

    def __init__(
        self,

        # This parameter is provided for convenience -- as in many cases
        # it is just convenient to specify the template name of the mail
        # body as the first positional argument. Note, however, that
        # setting it to `'something'` is perfectly equivalent to setting
        # the `body` parameter to `RenderFrom('something')` (see below).
        body_template_name=None,     # type: Optional[String]

        # * Public settable attributes:

        # [If a given value is a `RenderFrom` instance then it will be
        # (later, when the builder is called) automatically replaced with
        # a `str` rendered from the template referred to by the value.]
        body=None,                   # type: Optional[Union[String, RenderFrom]]
        sender=None,                 # type: Optional[Union[AddressHeaderRaw, RenderFrom]]
        to=None,                     # type: Optional[Union[AddressHeaderRaw, RenderFrom]]
        subject=None,                # type: Optional[Union[UsualHeaderRaw, RenderFrom]]
        # [When it comes to the following two parameters/attributes, an
        # acceptable runtime type is such one whose instances can be
        # coerced to `dict` (obviously, it can also be just `dict`).
        # Such automatic coercion is always applied immediately (by the
        # builder's customized variant of `__setattr__()`); also, if the
        # value of any of these parameters/attributes is `None` then it
        # is immediately replaced with an empty dict.]
        misc_headers=None,           # type: Optional[DictyCollectionOfHeaderRawOrRenderFrom]
        render_context=None,         # type: Optional[DictyCollection]
        # [If the value of the following parameter/attribute is `None`
        # then it is immediately replaced (by the builder's customized
        # variant of `__setattr__()`) with the `email.policy.SMTP`
        # policy object.]
        policy=None,                 # type: Optional[EmailPolicy]

        # * Rendering setup customization:

        settings=None,               # type: Optional[Dict]  # a *Pyramid settings* dict or `None`
        render_context_base=None,    # type: Optional[DictyCollection]
    ):

        if body_template_name is not None:
            if body is not None:
                raise TypeError(
                    'both `body_template_name` and `body` arguments '
                    'given (at most one of them should be)')
            body = RenderFrom(body_template_name)

        self._plain_setattr('_renderer',
                            JinjaTemplateBasedRenderer.from_predefined(
                                settings=settings,
                                render_context_base=render_context_base))
        self.body = body
        self.sender = sender
        self.to = to
        self.subject = subject
        self.misc_headers = misc_headers
        self.render_context = render_context
        self.policy = policy

    def clear(self):
        for attr_name in self.PUBLIC_SETTABLE_ATTRS:
            setattr(self, attr_name, None)

    def __setattr__(self, name, value):
        if name not in self.PUBLIC_SETTABLE_ATTRS:
            raise AttributeError('setting attribute {!a} is illegal'.format(name))
        if name in {'misc_headers', 'render_context'}:
            value = dict(value) if value is not None else {}
        elif name == 'policy':
            value = self._adjust_policy(value)
        self._plain_setattr(name, value)

    def __call__(self):
        # type: () -> EmailMessage
        message = self._make_message_obj()
        if self.sender is not None:
            message['From'] = self.prepare_header_value(
                'From',
                self._ready_value(self.sender))
        if self.to is not None:
            message['To'] = self.prepare_header_value(
                'To',
                self._ready_value(self.to))
        if self.subject is not None:
            message['Subject'] = self.prepare_header_value(
                'Subject',
                self._ready_value(self.subject))
        self.add_multiple_headers(message, self._ready_misc_headers())
        self._set_body(message, body=self._ready_body())
        self._verify_content_type_supported(message)
        return message


    def _plain_setattr(self, name, value):
        super(MailMessageBuilder, self).__setattr__(name, value)

    def _adjust_policy(self, policy):
        if policy is None:
            policy = EMAIL_POLICY_FOR_SMTP
        elif not isinstance(policy, EmailPolicy):
            raise TypeError('unsupported type of `policy`: '
                            '{!a}'.format(type(policy)))
        return policy

    def _make_message_obj(self):
        return EmailMessage(policy=self.policy)

    def _ready_value(self, value):
        if isinstance(value, RenderFrom):
            # noinspection PyUnresolvedReferences
            value = self._renderer.render(value.template_name, self.render_context)
        return value

    def _ready_misc_headers(self):
        return {name: self._ready_value(value)
                for name, value in sorted(self.misc_headers.items())}

    def _ready_body(self):
        body = self._ready_value(self.body)
        if body is None:
            raise RuntimeError('{!a}.body has not been set (without it '
                               'no message can be built)'.format(self))
        if isinstance(body, str):
            return body
        # In the future we may want to support multipart messages --
        # but see the comment in `_verify_content_type_supported()`.
        raise NotImplementedError('{!a}.body is of an unsupported '
                                  'type: {!a} (the value is: {!a})'
                                  .format(self, type(body), body))

    def _set_body(self, message, body):
        # See:
        # * https://docs.python.org/library/email.message.html#email.message.EmailMessage.set_content
        # * https://docs.python.org/library/email.contentmanager.html#email.contentmanager.set_content
        assert isinstance(body, str)
        message.set_content(body)

    def _verify_content_type_supported(self, message):
        content_type = message.get_content_type()
        if content_type != 'text/plain':
            # In the future we may want to support other content types,
            # in particular `multipart...` or `text/html` -- but then,
            # **for the sake of security**, we need to ensure that the
            # contents of any HTML (and maybe also other, e.g. XML???)
            # parts will be properly escaped.
            raise NotImplementedError('unsupported Content-Type: '
                                      '{!a}'.format(content_type))


class RenderFrom(object):

    """
    TODO: docs
    """

    def __init__(self, template_name):
        self._template_name = template_name

    @property
    def template_name(self):
        # type: () -> String
        return self._template_name

    __repr__ = attr_repr('template_name')
