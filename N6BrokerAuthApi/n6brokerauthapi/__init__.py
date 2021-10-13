# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
This package provides a REST API implementation intended to cooperate
with `rabbitmq-auth-backend-http` -- the RabbitMQ AMQP message broker's
HTTP-API-based authorization/authentication plugin.

The primary purpose of this package is to provide authorization
mechanisms for users of the n6's Stream API (STOMP-based).  However,
the code can be easily extended to provide such mechanisms for any
other case when RabbitMQ needs to authorize (and optionally, also,
authenticate by password) its clients.

See also the documentation of the `rabbitmq-auth-backend-http` plugin:
https://github.com/rabbitmq/rabbitmq-auth-backend-http
"""

# Ensure all monkey-patching provided by `n6lib`
# and `n6sdk` is applied as early as possible.
import n6lib  # noqa

from n6brokerauthapi.views import (
    N6BrokerAuthResourceView,
    N6BrokerAuthTopicView,
    N6BrokerAuthUserView,
    N6BrokerAuthVHostView,
)
from n6lib.config import ConfigMixin
from n6sdk.pyramid_commons import (
    BasicConfigHelper,
    HttpResource,
)


class N6BrokerAuthApiConfigHelper(ConfigMixin, BasicConfigHelper):

    config_spec = '''
        [broker_auth_api]
        auth_manager_maker_class :: importable_dotted_name
    '''

    def prepare_pyramid_configurator(self, pyramid_configurator):
        pyramid_configurator.registry.auth_manager_maker = self._get_auth_manager_maker()
        return super(N6BrokerAuthApiConfigHelper,
                     self).prepare_pyramid_configurator(pyramid_configurator)

    def _get_auth_manager_maker(self):
        settings = self.settings
        auth_manager_maker_class = self.get_config_section(settings)['auth_manager_maker_class']
        auth_manager_maker = auth_manager_maker_class(settings)
        return auth_manager_maker


# (see: https://github.com/rabbitmq/rabbitmq-auth-backend-http#what-must-my-web-server-do)
RESOURCES = [
    HttpResource(
        resource_id='user',
        url_pattern='/user',
        view_base=N6BrokerAuthUserView,
    ),
    HttpResource(
        resource_id='vhost',
        url_pattern='/vhost',
        view_base=N6BrokerAuthVHostView,
    ),
    HttpResource(
        resource_id='resource',
        url_pattern='/resource',
        view_base=N6BrokerAuthResourceView,
    ),
    HttpResource(
        resource_id='topic',
        url_pattern='/topic',
        view_base=N6BrokerAuthTopicView,
    ),
]


def main(global_config, **settings):
    return N6BrokerAuthApiConfigHelper(
        settings=settings,
        resources=RESOURCES,
    ).make_wsgi_app()
