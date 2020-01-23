# Copyright (c) 2013-2020 NASK. All rights reserved.

import datetime
import urllib
utcnow = datetime.datetime.utcnow  # for easier mocking in unit tests

from pyramid.httpexceptions import HTTPTemporaryRedirect

from n6lib.auth_api import AuthAPI
from n6lib.auth_db.api import AuthQueryAPI
from n6lib.common_helpers import provide_surrogateescape
from n6lib.data_backend_api import (
    N6DataBackendAPI,
    N6TestDataBackendAPI,
)
from n6lib.data_spec import (
    N6DataSpec,
    N6InsideDataSpec,
)
from n6lib.pyramid_commons import (
    N6ConfigHelper,
    N6DefaultStreamViewBase,
    SSLUserAuthenticationPolicy,
)
from n6lib.pyramid_commons.renderers import StreamRenderer_iodef
from n6sdk.pyramid_commons import (
    HttpResource,
)



provide_surrogateescape()



class RestAPIViewBase(N6DefaultStreamViewBase):

    DEFAULT_TIME_MIN = 7
    SAFE_ACTIVE_MIN_DELTA = datetime.timedelta(days=182)  # half a year


    def prepare_params(self):
        cleaned_param_dict = super(RestAPIViewBase, self).prepare_params()
        default_delta = datetime.timedelta(days=int(
            self.request.registry.settings.get('default_time_min', self.DEFAULT_TIME_MIN)))
        redirect_url = self.get_redirect_url_if_no_time_min(cleaned_param_dict, default_delta)
        if redirect_url is not None:
            raise HTTPTemporaryRedirect(redirect_url)
        return cleaned_param_dict


    def get_redirect_url_if_no_time_min(self, cleaned_param_dict, default_delta):

        """
        Get a redirection URL with limited `time.min` when `time.min`
        is not given (to prevent requesting to much data...).

        Args:
            `cleaned_param_dict`:
                A cleaned dictionary of query parameters.
            `default_delta`:
                A datetime.timedelta object that represents the default
                time interval between: `time.min` and UTC-now/`time.max`/
                /`modified.min`; and between: `modified.min` and
                `modified.max`.

        Returns:
            None if 'time.min' *is* present in `cleaned_param_dict`,
            a redirection URL otherwise.
        """

        if 'time.min' in cleaned_param_dict:
            return None

        redir_params = {}
        redir_template_parts = []
        if self.request.query_string:
            redir_template_parts.append(self.request.query_string)

        time_min = utcnow() - default_delta

        if 'modified.min' in cleaned_param_dict:
            # Set time.min to a value being not bigger than
            #  `default_time_min` days earlier than modified.min
            #  (note that `modified` is always bigger than `time`).
            [modified_min] = cleaned_param_dict['modified.min']
            assert isinstance(modified_min, datetime.datetime)
            time_min = min(time_min, modified_min - default_delta)
        elif ('modified.max' in cleaned_param_dict or
              'modified.until' in cleaned_param_dict):
            # Set modified.min to a value that is `default_time_min`
            #  days earlier than modified.max/until; and set time.min
            #  to a value being not bigger than `default_time_min` days
            #  earlier than modified.min (note that `modified` is always
            #  bigger than `time`).
            [modified_max_until] = cleaned_param_dict.get(
                'modified.max',
                cleaned_param_dict.get('modified.until', [None]))
            assert isinstance(modified_max_until, datetime.datetime)
            modified_min = modified_max_until - default_delta
            time_min = min(time_min, modified_min - default_delta)
            redir_params['modified_min'] = modified_min
            redir_template_parts.append('modified.min={modified_min}')

        if 'active.min' in cleaned_param_dict:
            [active_min] = cleaned_param_dict['active.min']
            assert isinstance(active_min, datetime.datetime)
            time_min = min(time_min, active_min - self.SAFE_ACTIVE_MIN_DELTA)
        elif ('active.max' in cleaned_param_dict or
              'active.until' in cleaned_param_dict):
            [active_max_until] = cleaned_param_dict.get(
                'active.max',
                cleaned_param_dict.get('active.until', [None]))
            assert isinstance(active_max_until, datetime.datetime)
            active_min = active_max_until - default_delta
            time_min = min(time_min, active_min - self.SAFE_ACTIVE_MIN_DELTA)
            redir_params['active_min'] = active_min
            redir_template_parts.append('active.min={active_min}')

        if 'time.max' in cleaned_param_dict or 'time.until' in cleaned_param_dict:
            [time_max_until] = cleaned_param_dict.get(
                'time.max',
                cleaned_param_dict.get('time.until', [None]))
            assert isinstance(time_max_until, datetime.datetime)
            time_min = min(time_min, time_max_until - default_delta)

        redir_params['time_min'] = time_min
        redir_template_parts.append('time.min={time_min}')

        return self._get_redirect_url(redir_template_parts, redir_params)


    def _get_redirect_url(self, template_parts, params):
        template = '&'.join(template_parts)
        quoted_params = {
            param: urllib.quote_plus(str(value))
            for param, value in params.items()}
        query_str = template.format(**quoted_params)
        return "{}?{}".format(self.request.path_url, query_str)



n6_data_spec = N6DataSpec()
n6_inside_data_spec = N6InsideDataSpec()

STREAM_RENDERERS = [
    'json', 'csv', 'sjson',
    'snort-dns', 'snort-http', 'snort-ip', 'snort-ip-bl',
    'suricata-dns', 'suricata-http', 'suricata-ip', 'suricata-ip-bl',
]
if StreamRenderer_iodef is not None:
    STREAM_RENDERERS.append('iodef')

DATA_RESOURCES = [
    HttpResource(
        resource_id='/search/events',
        url_pattern='/search/events.{renderer}',
        view_base=RestAPIViewBase,
        view_properties=dict(
            data_spec=n6_data_spec,
            data_backend_api_method='search_events',
            renderers=STREAM_RENDERERS,
        ),
    ),
    HttpResource(
        resource_id='/report/inside',
        url_pattern='/report/inside.{renderer}',
        view_base=RestAPIViewBase,
        view_properties=dict(
            data_spec=n6_inside_data_spec,
            data_backend_api_method='report_inside',
            renderers=STREAM_RENDERERS,
        ),
    ),
    HttpResource(
        resource_id='/report/threats',
        url_pattern='/report/threats.{renderer}',
        view_base=RestAPIViewBase,
        view_properties=dict(
            data_spec=n6_data_spec,
            data_backend_api_method='report_threats',
            renderers=STREAM_RENDERERS,
        ),
    ),
]



def main(global_config, **settings):
    return N6ConfigHelper(
        settings=settings,
        data_backend_api_class=N6DataBackendAPI,
        component_module_name='n6web',
        auth_api_class=AuthAPI,                 # <- XXX: legacy stuff, to be removed in the future
        auth_query_api=AuthQueryAPI(settings),  # <- XXX: dummy stuff yet; to be used in the future
        authentication_policy=SSLUserAuthenticationPolicy(settings),
        resources=DATA_RESOURCES,
    ).make_wsgi_app()


def main_test_api(global_config, **settings):
    return N6ConfigHelper(
        settings=settings,
        data_backend_api_class=N6TestDataBackendAPI,
        component_module_name='n6web',
        auth_api_class=AuthAPI,                 # <- XXX: legacy stuff, to be removed in the future
        auth_query_api=AuthQueryAPI(settings),  # <- XXX: dummy stuff yet; to be used in the future
        authentication_policy=SSLUserAuthenticationPolicy(settings),
        resources=DATA_RESOURCES,
    ).make_wsgi_app()
