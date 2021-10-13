# Copyright (c) 2020-2021 NASK. All rights reserved.

import contextlib

from rt import (
    Rt,
    RtError,
)

from n6lib.common_helpers import (
    ascii_str,
    make_exc_ascii_str,
)
from n6lib.config import (
    Config,
    ConfigMixin,
)
from n6lib.jinja_helpers import JinjaTemplateBasedRenderer
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class RTClientAPIError(Exception):
    """To be raised on RT-related operation/communication failures."""


# TODO: more comprehensive tests
# (most important portions *are* tested indirectly in
# `n6lib.tests.test_pyramid_commons.TestN6RegistrationView`)
class RTClientAPI(ConfigMixin):

    config_spec_pattern = '''
        [{config_section}]

        # Should the RT stuff be used at all? (if false, any invocations
        # of the `RTClientAPI.new_ticket()` method do nothing, and no
        # other options from this configuration section are really used)
        active = false :: bool

        rest_api_url = https://localhost/rt/REST/1.0/
        username = root       ; `root` is default user name in RT from DockerHub
        password = password   ; `password` is default user password in RT from DockerHub

        # The value of the following option, if not left empty, should
        # be a Python dict literal that, separately for each *ticket
        # kind* (identified by a `str`), specifies the RT fields to
        # be submitted to the RT REST API to create a new RT ticket.
        # Each key in the dict is a *ticket kind* key (such as
        # 'registration_requested' or 'org_config_update_requested')
        # and each value is a subdict.
        #
        # Lack of a certain *ticket kind* key means that the RT stuff is
        # not active for that *ticket kind* (i.e., invocations of the
        # method `RTClientAPI.new_ticket()` with that *ticket kind* key
        # as the first argument do nothing).
        #
        # The following requirements and remarks apply to the keys and
        # values of each of aforementioned subdicts:
        #
        # * ad keys:
        #   * each key should be a `str` being an RT field name;
        #   * custom RT fields can be specified with keys such as
        #     'CF_MyCustomFldName';
        #   * the `Queue` field *must* be included;
        #   * the 'id' field must *not* be included;
        #
        # * ad values:
        #   * each value should be a `str` being a Jinja template
        #     of the actual RT field value, to be rendered with a
        #     context that includes the 'data_dict' variable whose value
        #     is the `data_dict` argument taken by the `new_ticket()`
        #     method of an `n6lib.rt_client_api.RTClientAPI` instance;
        #   * the *autoescape* Jinja option is *enabled*; if you are
        #     absolutely sure that, for some expression, you need to
        #     *disable* HTML escaping, mark that expression with the
        #     `safe` Jinja filter, e.g.:
        #         {{ data_dict['some_item']|safe }}
        #     (BEWARE: doing that without proper thought is *dangerous*
        #     as it may result in an HTML injection/XSS vulnerability!).
        new_ticket_kind_to_fields_render_spec = :: ticket_kind_to_fields_render_spec
    '''

    # This is a (quite minimalistic) example of a value of the option
    # `new_ticket_kind_to_fields_render_spec` (see the `N6Portal/*.ini`
    # files for more realistic examples):
    #
    #     {
    #         'example_ticket_kind': {
    #             'Queue': 'General',
    #             'Subject': 'From n6',
    #             'Content-Type': 'text/html; charset="UTF-8"',
    #             'Text': """<!DOCTYPE html><html>
    #                 <head>
    #                     <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    #                 </head>
    #                 <body>
    #                     <dl>
    #                         {% for key, value in data_dict|dictsort %}
    #                             <dt>{{ key }}</dt>
    #                             <dd>{{ value }}</dd>
    #                         {% endfor %}
    #                     </dl>
    #                 </body>
    #             </html>""",
    #         },
    #     }


    default_config_section = 'rt'

    @property
    def custom_converters(self):
        return {
            'ticket_kind_to_fields_render_spec': self._conv_ticket_kind_to_fields_render_spec,
        }

    @classmethod
    def _conv_ticket_kind_to_fields_render_spec(cls, opt_value):
        result = {}
        if not opt_value:
            return result
        raw_dict = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)
        raw_items = raw_dict.items()
        for ticket_kind, field_to_template in raw_items:
            assert isinstance(ticket_kind, str)
            try:
                ticket_fields_renderer = _TicketFieldsRenderer(field_to_template)
            except Exception as exc:
                raise ValueError(
                    'error when trying to create RT ticket fields '
                    'renderer for ticket kind {!a} - {}'.format(
                        ticket_kind,
                        make_exc_ascii_str(exc)))
            result[ticket_kind] = ticket_fields_renderer
        return result


    def __init__(self, settings=None, config_section=None):
        self._config_sect_name = (config_section if config_section is not None
                                  else self.default_config_section)
        self._config = self.get_config_section(settings, config_section=self._config_sect_name)
        self._new_ticket_kind_to_renderer = self._config['new_ticket_kind_to_fields_render_spec']


    def new_ticket(self, ticket_kind, data_dict):
        if not self._config['active']:
            return None
        renderer = self._new_ticket_kind_to_renderer.get(ticket_kind)
        if renderer is None:
            return None
        try:
            field_name_to_value = self._prepare_new_ticket_fields(renderer, data_dict)
            with self.rt_client_session() as rt:
                ticket_id = rt.create_ticket(**field_name_to_value)
                self._verify_ticket_created(ticket_id)
            if not isinstance(ticket_id, int):
                # (the `rt` library's API changed or what?!)
                raise TypeError('ticket_id={!a} is not an int'.format(ticket_id))
            if ticket_id < 1:
                # (the `rt` library's API changed or what?!)
                raise ValueError('ticket_id={!a} is not a positive number'.format(ticket_id))
        except:
            LOGGER.error('Could not create a new RT ticket - %s', make_exc_ascii_str())
            raise
        else:
            LOGGER.info('RT ticket #%s created successfully', ticket_id)
            assert isinstance(ticket_id, int) and ticket_id >= 1
            return ticket_id

    def _prepare_new_ticket_fields(self, renderer, data_dict):
        assert isinstance(renderer, _TicketFieldsRenderer)
        field_name_to_value = {
            field_name: field_value
            for field_name, field_value in renderer.generate_rendered_field_items(data_dict)}
        assert _QUEUE_RT_FIELD_NAME in field_name_to_value
        assert all(isinstance(field_name, str) and
                   isinstance(field_value, str)
                   for field_name, field_value in field_name_to_value.items())
        LOGGER.debug('Prepared fields for a new ticket: %a', field_name_to_value)
        return field_name_to_value

    def _verify_ticket_created(self, ticket_id):
        if ticket_id == -1:
            raise RTClientAPIError('failed to create a new RT ticket')


    ## These may be implemented later if necessary:
    # def update_ticket...
    # def search_for_tickets...
    # ...


    @contextlib.contextmanager
    def rt_client_session(self):
        # This method is made public to make it possible to operate
        # on an `rt.Rt` instance directly. However, if possible, it
        # is recommended to use other `RTClientAPI`'s public methods
        # rather than this one.
        if not self._config['active']:
            raise RuntimeError('RT is turn off in the configuration '
                               '(i.e., the `active` option is false)')
        rest_api_url = self._config['rest_api_url']
        username = self._config['username']
        try:
            rt = Rt(url=rest_api_url)
            if not rt.login(login=username, password=self._config['password']):
                raise RTClientAPIError('could not log in to RT')
            try:
                yield rt
            finally:
                self._try_logout(rt)
        except (RtError, RTClientAPIError) as exc:
            raise RTClientAPIError(
                'RT-related error - {} ('
                'config option {}: {!a}; '
                'config option {}: {!a})'.format(
                    make_exc_ascii_str(exc),
                    self._repr_opt_name('rest_api_url'), rest_api_url,
                    self._repr_opt_name('username'), username))

    def _repr_opt_name(self, config_opt_name):
        return '`{}.{}`'.format(
            ascii_str(self._config_sect_name),
            config_opt_name)

    def _try_logout(self, rt):
        try:
            logged_out = rt.logout()
        except RtError as exc:
            LOGGER.warning('Could not log out from RT properly (%s)',
                           make_exc_ascii_str(exc),
                           exc_info=True)
        else:
            if not logged_out:
                LOGGER.warning('Could not log out from RT properly')


_QUEUE_RT_FIELD_NAME = 'Queue'


class _TicketFieldsRenderer(object):

    def __init__(self, field_to_template):
        field_to_template = dict(self.__gen_cleaned_field_to_template_items(field_to_template))
        self._field_names = list(field_to_template)
        self._actual_renderer = JinjaTemplateBasedRenderer.from_dict(field_to_template,
                                                                     autoescape=True)
    def __gen_cleaned_field_to_template_items(self, raw_dict):
        if not isinstance(raw_dict, dict):
            raise TypeError('not a dict: {!a}'.format(raw_dict))
        if _QUEUE_RT_FIELD_NAME not in raw_dict:
            raise ValueError('required RT field name {!a} is missing'
                             .format(_QUEUE_RT_FIELD_NAME))
        raw_items = raw_dict.items()
        for field_name, template_string in raw_items:
            assert isinstance(field_name, str)
            if not isinstance(template_string, str):
                raise TypeError('non-`str` object as RT field value '
                                'template (for field {!a}): {!a}'
                                .format(field_name, template_string))
            yield field_name, template_string

    def generate_rendered_field_items(self, data_dict):
        for field_name in self._field_names:
            field_value = self._actual_renderer.render(field_name, {'data_dict': data_dict})
            yield field_name, field_value
