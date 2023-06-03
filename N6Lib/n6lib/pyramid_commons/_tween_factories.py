# Copyright (c) 2021 NASK. All rights reserved.

"""
This modules provides custom Pyramid-compliant *tweens* (see:
https://docs.pylonsproject.org/projects/pyramid/en/stable/narr/hooks.html#registering-tweens).
"""

import collections
import sys

from pyramid.response import Response

from n6lib.const import (
    HTTP_AC_REQUEST_HEADERS_HEADER,
    HTTP_AC_REQUEST_METHOD_HEADER,
)
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.data_backend_api import (
    N6DataBackendAPI,
    transact,
)


def preflight_requests_handler_tween_factory(handler, registry):

    def preflight_requests_handler_tween(request):
        if (request.method == 'OPTIONS'
                and HTTP_AC_REQUEST_HEADERS_HEADER in request.headers
                and HTTP_AC_REQUEST_METHOD_HEADER in request.headers):
            # return empty response with "No Content" status
            return Response(status=204)
        return handler(request)

    return preflight_requests_handler_tween


def auth_db_apis_maintenance_tween_factory(handler, registry):

    """
    The `AuthManageAPI`-maintenance tween factory.

    See also: `n6lib.auth_db.api`.
    """

    def auth_db_apis_maintenance_tween(request):
        _do_maintenance_of_auth_db_api(request.registry.auth_manage_api, request)
        return handler(request)

    def _do_maintenance_of_auth_db_api(api, request):
        if api is None:
            return
        force_exit_on_any_remaining_entered_contexts(api)
        org_id, user_id = _get_org_id_and_user_id(request)
        api.set_audit_log_external_meta_items(**{
            key: value for key, value in [
                ('n6_module', request.registry.component_module_name),
                ('request_client_addr', request.client_addr),
                ('request_org_id', org_id),
                ('request_user_id', user_id),
            ]
            if value is not None})

    def _get_org_id_and_user_id(request):
        if request.auth_data:
            org_id = request.auth_data.get('org_id')
            user_id = request.auth_data.get('user_id')
        else:
            org_id = user_id = None
        return org_id, user_id

    return auth_db_apis_maintenance_tween


def auth_api_context_tween_factory(handler, registry):

    """
    The AuthAPI-context tween factory.

    This tween automatically wraps views in the AuthAPI context
    (using the AuthAPI context manager interface).

    See also: n6lib.auth_api.AuthAPI.
    """

    sys_exc_info = sys.exc_info

    auth_api = registry.auth_api
    auth_api_enter = auth_api.__enter__
    auth_api_exit = auth_api.__exit__

    def auth_api_context_tween(request):
        force_exit_on_any_remaining_entered_contexts(auth_api)
        response = unwrapped_app_iter = None
        auth_api_enter()
        try:
            response = handler(request)
            unwrapped_app_iter = getattr(response, 'app_iter', None)
            if isinstance(unwrapped_app_iter, collections.Iterator):
                response.app_iter = _auth_api_exiting_app_iter(unwrapped_app_iter)
            return response
        finally:
            if response is None or response.app_iter is unwrapped_app_iter:
                # The above `try` block has been interrupted by an
                # exception *or* `response` is an ordinary (non-stream)
                # response -- so let's call API's `__exit__()` *now*
                # (rationale: the handler has already done everything it
                # was supposed to do, unless an exception foiled that).
                auth_api_exit(*sys_exc_info())
            else:
                # The response is a *stream* one, and...
                if sys_exc_info()[0] is None:
                    # ...no exception occurred -- so we should *not*
                    # finalize anything yet; in particular, we do
                    # *not* want Auth API's `__exit__()` be called
                    # now, as it will be called later, namely: when
                    # the `response.app_iter` generator will be
                    # finalized (see the comment in the definition
                    # of the `_auth_api_exiting_app_iter()` function
                    # below).
                    pass
                else:
                    # ...we have an exception -- so `response.app_iter`
                    # needs to be finalized *now* (note: this includes,
                    # in particular, calling Auth API's `__exit__()` --
                    # see: `_auth_api_exiting_app_iter()` below).
                    response.app_iter.close()

    def _auth_api_exiting_app_iter(unwrapped_app_iter):
        # Note: the code placed in the following `finally` blocks is to
        # be executed:
        #
        # * when the `for` loop (see below) finishes normally (i.e.,
        #   when the WSGI stuff consumes all items yielded by this
        #   generator),
        #
        #   or -- if that does not happen (because of some exceptional
        #   event, for example, a premature disconnect of the HTTP
        #   client) --
        #
        # * when the `close()` method of this generator is called by
        #   the WSGI stuff (which is obliged, by PEP 3333, to do so),
        #
        #   or -- if even that does not happen (hardly probable) --
        #
        # * when this generator is finalized by the Python garbage
        #   collector.
        try:
            try:
                for item in unwrapped_app_iter:
                    yield item
            finally:
                close = getattr(unwrapped_app_iter, 'close', None)
                if close is not None:
                    # Apparently, `unwrapped_app_iter` is an iterator
                    # which is closable (e.g., a generator).
                    close()
        finally:
            auth_api_exit(*sys_exc_info())

    return auth_api_context_tween


def event_db_session_maintenance_tween_factory(handler, registry):

    """
    The Event-DB-session-maintenance tween factory.

    See also: n6lib.data_backend_api.
    """

    def event_db_session_maintenance_tween(request):
        force_exit_on_any_remaining_entered_contexts(transact)
        N6DataBackendAPI.get_db_session().remove()
        return handler(request)

    return event_db_session_maintenance_tween
