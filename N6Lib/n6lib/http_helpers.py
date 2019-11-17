# Copyright (c) 2019 NASK. All rights reserved.

import datetime
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from n6lib.datetime_helpers import parse_iso_datetime_to_utc


class RequestPerformer(object):

    """
    A simple yet flexible tool to download data with HTTP/HTTPS (able to deal
    with huge downloads in a memory-efficient manner).


    RequestPerformer is intended to be used in one of the following ways:

    (1) using its `fetch()` class method to perform a "one-shot" download (in
        this case the `stream` option is automatically forced to be `False`,
        so it cannot be passed in):

        content = RequestPerformer.fetch('GET', 'https://example.com')

    (2) using its *context manager* and *iterator* interfaces to download
        the content in a stream-like way (making it possible to deal with
        large amounts of data in a memory-efficient manner):

        with RequestPerformer('GET', 'https://example.com') as perf:
            for chunk in perf:  # `chunk` is a byte string (str)
                my_temp_file.write(chunk)

    (3) using the *context manager* interface to initialize the download and
        use `requests.Response` and/or `requests.Session` objects directly
        (within its `with` block a `RequestPerformer` instance has the
        following public attributes: `request` set to `requests.Response`
        instance, and `session` set to `requests.Session` instance):

        with RequestPerformer('GET', 'https://example.com') as perf:
            print perf.response.content   # download all data now!
            print perf.response.headers   # get headers
            print perf.session.cookies    # get cookies (as a CookieJar instance)
            # etc...

    The (2) and (3) ways can be combined, except that -- if the `stream`
    keyword argument is true (see below) -- you can **either** use the
    *iterator* interface [see above: (2)] **or** get directly the `content`
    attribute of the `response` attribute [see above: (3)], but should
    **not** do both.

    Apart from specifying the HTTP method and the URL, you can also pass in a
    lot of other arguments (see the constructor args/kwargs described below),
    especially various options related to the `requests` library's stuff
    (used under the hood). For example:

        with RequestPerformer('POST',
                              'https://www.example.com',
                              data={'example': 'data'},
                              headers={'header-test: 'true'},
                              retries=3,
                              allow_redirects=True) as perf:
            # (...)


    Required constructor args/kwargs:

        `method` (str or unicode):
            The HTTP method name (the `SUPPORTED_HTTP_METHODS` class attribute
            contains its allowed values). To be passed into
            `requests.Session.request()`.

        `url` (str or unicode):
            The URL to download from (must start with one of the strings
            the `SUPPORTED_URL_PREFIXES` class attribute contains). To be
            passed into `requests.Session.request()`.

    Optional constructor kwargs:

        `data` (str or file-like, or dict, or list of 2-tuples;
                default: `None`):
            The data to be optionally sent as the request body. To be
            passed into `requests.Session.request()`.

        `headers` (dict; default: `None`):
            The headers to be optionally attached to the request. To be passed
            into `requests.Session.request()`.

        `allow_redirects` (boolean; default: `False`):
            Set to `True` to allow redirects in case of
            GET/OPTIONS/POST/PUT/PATCH/DELETE/HEAD method.
            To be passed into `requests.Session.request()`.

        `timeout` (int or float, or 2-tuple of ints/floats;
                   default: `(12.1, 25)`):
            The request timeout specification -- to be passed into
            `requests.Session.request()`. See also:
            http://docs.python-requests.org/en/stable/user/advanced/#timeouts.

        `retries` (int; default: `0`):
            Maximum number of attempts to retry on request failures (such as
            a connection problem or a server-side error whose HTTP status code
            suggests that a repeated request may succeed). If non-zero, it is,
            along with `backoff_factor`, passed into the `Retry` constructor
            (as the `total` argument -- see: `urllib3.util.retry.Retry`).
            If equal to 0 (the default), no retries are attempted (that is,
            an exception is raised on first failure). Note that the `retries`
            number does not include the first request, e.g., `retries=3` means
            that there can be up to 4 request attempts (the first one plus
            maximum of 3 retries). *Beware* that, depending on the server
            semantics, each attempt may change the server-side state/data
            (especially when `method` is POST or PATCH).

        `backoff_factor` (float; default: `0.1`):
            Backoff factor to apply between retry attempts. If the `retries`
            argument is non-zero, the `backoff_factor` argument is passed into
            the `Retry` constructor (see: `urllib3.util.retry.Retry`).
            For non-zero `backoff_factor`, delays between requests increase.
            According to `urllib3` docs, the delay before the first retry is
            `0s` (i.e., the first retry is immediate), and the formula for
            consecutive delays is:
            `backoff_factor * (2 ** (<retry number> - 1)) seconds`
            (but *never more* than `urllib3.util.retry.Retry.BACKOFF_MAX`,
            that is, 120 seconds). Therefore, for `backoff_factor=0.1`
            (default) the sequence of delays between consecutive requests is:
            0s, 0.2s, 0.4s, 0.8s, 1.6s...

        `stream` (boolean; default: `True`):
            * If `True`: contents will be downloaded *in chunks* (see: the
              `chunk_size` argument described below) -- and *only* when:
              (a) the RequestPerformer instance is iterated over (downloading
                  one chunk per iteration step), or
              (b) the `response.content` attribute (or a similar attribute,
                  such as `response.text`...) is accessed the first time (then
                  all contents will be downloaded immediately and set as the
                  `response.content` attribute) -- however, note that if you
                  do not need the *stream-like* (iteration-based) way of
                  downloading the contents you probably just need to use the
                  `stream=False` variant (see below);
              note: the (a) and (b) ways should *not* be combined.
            * If `False`: contents will be downloaded *all at once*, just when
              entering the `with` block; then the contents will be accessible
              as the `response.content` attribute (and also by iteration over
              the RequestPerformer instance).
            This argument will also be passed into `requests.Session.request()`.

        `chunk_size` (int; default: `2 ** 16`):
            When downloading data in the stream-like way -- the amount
            of data (in bytes) to be transferred per iteration. Relevant
            only if the `stream` argument is true, otherwise ignored.
            Note: it is not necessarily the length of each yielded data
            chunk (because of decoding...).

        `custom_session_attrs` (dict; default: `None`):
            Custom `requests.Session()` instance attribute values.
            (see:
            http://docs.python-requests.org/en/master/user/advanced/ and
            http://docs.python-requests.org/en/master/api/#sessionapi)

        Other arbitrary kwargs:
            To be passed into `requests.Session.request()`.

    Exceptions raised by the constructor and/or methods:
        * ValueError -- for:
            * unsupported `method`/`url` values;
            * `data` being a file-like object whose content's length
              cannot be determined without consuming it, *and*, at the
              same time, non-zero `retries` given.
        * Any exception that can be raised by the `requests` or `urrlib3`
          libraries.


    For more information about args/kwargs related to the `requests` or
    `urllib3` libraries mentioned above -- see:
        * http://docs.python-requests.org/en/stable/api/
        * http://docs.python-requests.org/en/stable/user/advanced/
        * https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.retry.Retry
    """

    SUPPORTED_HTTP_METHODS = ('DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT', 'TRACE')
    SUPPORTED_URL_PREFIXES = ('http://', 'https://')

    _RETRY_KWARGS_BASE = {
        'redirect': False,
        'respect_retry_after_header': False,
        # ad `status_forcelist` -- see: https://tools.ietf.org/html/rfc7231#section-6.6
        'status_forcelist': {500, 502, 503, 504},
        'method_whitelist': False,
    }

    # sequence of datetime.strptime() formats tried (consecutively) by
    # the get_dt_header() method to parse date+time response headers
    # (see also: https://tools.ietf.org/html/rfc7231#section-7.1.1.1)
    _HTTP_DATETIME_FORMATS = (
        # *note:* these 3 formats require that the C locale is set
        # (`n6lib` already ensures that; see n6lib/__init__.py...)

        # the preferred format
        '%a, %d %b %Y %H:%M:%S GMT',

        # old RFC-850 format
        '%A, %d-%b-%y %H:%M:%S GMT',

        # old ANSI C's asctime() format
        # (note: using '%d' here is OK, because datetime.strptime()
        # is lenient about '%d' vs. numbers that are *not* zero-padded,
        # as well as about extra spaces *between* input string elements).
        '%a %b %d %H:%M:%S %Y',

        # (apart from trying the above 3 formats, the get_dt_header()
        # method tries -- as the last attempt -- ISO 8601 parsing)
    )

    def __init__(self,
                 method,
                 url,
                 data=None,
                 headers=None,
                 allow_redirects=False,
                 timeout=(12.1, 25),
                 retries=0,
                 backoff_factor=0.1,
                 stream=True,
                 chunk_size=(2 ** 16),
                 custom_session_attrs=None,
                 **extra_request_kwargs):

        method = self._get_valid_method(method=method)
        url = self._get_valid_url(url=url)
        self.session = None             # to be set in __enter__()
        self.response = None            # to be set in __enter__()
        self._actual_iterator = None    # to be set in __enter__()
        self._custom_session_attrs = custom_session_attrs
        self._request_kwargs = dict(extra_request_kwargs,
                                    method=method,
                                    url=url,
                                    data=data,
                                    headers=headers,
                                    timeout=timeout,
                                    allow_redirects=allow_redirects,
                                    stream=stream)
        self._retry_conf = self._get_retry_conf(retries=retries,
                                                backoff_factor=backoff_factor)
        self._chunk_size = chunk_size if stream else None

    @classmethod
    def fetch(cls, *args, **kwargs):
        """
        Download all content at once.

        Args/kwargs:
            The same as constructor args/kwargs, except that `stream`
            is forbidden (internally it is forcibly set to `False`).

        Returns:
            The downloaded content (str).

        Raises:
            * ValueError: for unsupported `method`/`url` values.
            * Any exception that can be raised by the `requests` or `urrlib3`
              libraries.
        """
        with RequestPerformer(*args, stream=False, **kwargs) as perf:
            return perf.response.content

    def __enter__(self):
        self.session = requests.Session()
        try:
            self._set_custom_session_attrs()
            self._set_up_retries()
            self.response = self.session.request(**self._request_kwargs)
            self.response.raise_for_status()
            self._actual_iterator = self.response.iter_content(chunk_size=self._chunk_size)
        except:
            self.session.close()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def __iter__(self):
        return self

    def next(self):
        return next(self._actual_iterator)

    def get_dt_header(self, header_key):
        """
        A helper method to retrieve a response header as a date+time.

        Args/kwargs:
            `header_key`:
                The name of the HTTP response header.

        Returns:
            `None` or UTC date+time as a `datetime.datetime` instance
            (a naive one, i.e., without explicit timezone information).

        Example usage:
            with RequestPerformer('GET', 'http://example.com/FOO') as perf:
                foo_last_modified = perf.get_dt_header('Last-Modified')
            if foo_last_modified is None:
                print 'I have no idea when FOO was modified.`
            else:
                print 'FOO modification date+time:', foo_last_modified.isoformat()
        """
        raw_value = (self.response.headers.get(header_key) or '').strip()
        if raw_value:
            for dt_format in self._HTTP_DATETIME_FORMATS:
                try:
                    return datetime.datetime.strptime(raw_value, dt_format)
                except ValueError:
                    pass
            try:
                return parse_iso_datetime_to_utc(raw_value)
            except ValueError:
                pass
        return None

    def _get_valid_method(self, method):
        method = method.upper()
        if method not in self.SUPPORTED_HTTP_METHODS:
            raise ValueError('HTTP method {!r} not supported'.format(method))
        return method

    def _get_valid_url(self, url):
        url = self._get_url_with_lowercased_proto(url)
        if not url.startswith(self.SUPPORTED_URL_PREFIXES):
            raise ValueError('URL prefix {!r} not supported'.format(url))
        return url

    @staticmethod
    def _get_url_with_lowercased_proto(url):
        url_parts = url.split(':', 1)
        url_parts[0] = url_parts[0].lower()
        url = ':'.join(url_parts)
        return url

    def _get_retry_conf(self, retries, backoff_factor):
        if retries:
            retry_conf = Retry(backoff_factor=backoff_factor,
                               total=retries,
                               **self._RETRY_KWARGS_BASE)
            return retry_conf
        return None

    def _set_custom_session_attrs(self):
        if self._custom_session_attrs:
            for name, value in self._custom_session_attrs.items():
                setattr(self.session, name, value)

    def _set_up_retries(self):
        if self._retry_conf is not None:
            for http_prefix in self.SUPPORTED_URL_PREFIXES:
                self.session.mount(http_prefix,
                                   _HTTPAdapterForRetries(max_retries=self._retry_conf))


class _HTTPAdapterForRetries(HTTPAdapter):

    def send(self, request, *args, **kwargs):
        content_length_is_unknown = (request.body is not None
                                     and 'Content-Length' not in request.headers)
        if content_length_is_unknown:
            # it seems that requests's HTTPAdapter does not perform
            # retries in such a case, even though they were requested
            # (see the source code of HTTPAdapter.send() in conjunction
            # with urllib3.connectionpool.HTTPConnectionPool.urlopen()
            # and urllib3.util.retry.Retry.increment()...) -- so here
            # we raise an exception to prevent such a silent omission
            # [we analyzed this for requests==2.21.0 and urllib3==1.24.1]
            raise ValueError('non-zero `retries` has been specified and, '
                             'at the same time, Content-Length of the request '
                             'could not be determined (suggested solutions: '
                             'specify `data` whose length is discoverable, '
                             'or specify `retries=0`)')

        return super(_HTTPAdapterForRetries, self).send(request, *args, **kwargs)
