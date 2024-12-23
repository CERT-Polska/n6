# Copyright (c) 2017-2024 NASK. All rights reserved.

from n6lib.amqp_helpers import SimpleAMQPExchangeTool
from n6lib.auth_api import AuthAPI
from n6lib.log_helpers import get_logger, logging_configured


LOGGER = get_logger(__name__)


class ExchangeUpdater:

    """
    Use this tool to update Stream-API-related AMQP exchange declarations
    and bindings (adding and deleting them as appropriate), according to
    the relevant Stream API settings in Auth DB.
    """

    def __init__(self):
        self._auth_api = AuthAPI()
        self._amqp_tool = SimpleAMQPExchangeTool()

    def run(self):
        LOGGER.info('Checking AuthAPI for stream-api authorized '
                    'and unauthorized organizations...')
        with self._auth_api:
            authorized_orgs = self._get_authorized_orgs()
            unauthorized_orgs = self._get_unauthorized_orgs()
        LOGGER.info('Updating (declaring and binding, and/or deleting) '
                    'exchanges for individual organizations...')
        with self._amqp_tool:
            self._declare_needed_org_exchanges(authorized_orgs)
            self._bind_needed_org_exchanges(authorized_orgs)
            self._delete_obsolete_org_exchanges(unauthorized_orgs)
        LOGGER.info('Exchanges updated')

    def _get_authorized_orgs(self):
        org_ids = self._auth_api.get_stream_api_enabled_org_ids()
        return sorted(org_ids)

    def _get_unauthorized_orgs(self):
        org_ids = self._auth_api.get_stream_api_disabled_org_ids()
        return sorted(org_ids)

    def _declare_needed_org_exchanges(self, orgs):
        for org_id in orgs:
            self._amqp_tool.declare_exchange(exchange=org_id,
                                             exchange_type='topic',
                                             durable=True)

    def _bind_needed_org_exchanges(self, orgs):
        for org_id in orgs:
            self._amqp_tool.bind_exchange_to_exchange(exchange=org_id,
                                                      source_exchange='clients',
                                                      arguments={'n6-client-id': org_id})

    def _delete_obsolete_org_exchanges(self, orgs):
        for org_id in orgs:
            self._amqp_tool.delete_exchange(exchange=org_id)


def main():
    with logging_configured():
        exchange_updater = ExchangeUpdater()
        exchange_updater.run()


if __name__ == "__main__":
    main()
