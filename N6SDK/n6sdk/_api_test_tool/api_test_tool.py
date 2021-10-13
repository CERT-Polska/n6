#!/usr/bin/env python

# Copyright (c) 2015-2021 NASK. All rights reserved.

"""
This tool is a part of *n6sdk*.  It can analyse and verify an
*n6*-like REST API, tell if that API meets the basic requirements,
and report any non-standard keys or "extra" result data.
"""

import argparse
import configparser
import json
import random
import sys
from collections import defaultdict
from urllib.parse import urlencode, urlparse

import requests
import requests.packages.urllib3
from pkg_resources import Requirement, resource_filename, cleanup_resources

from n6sdk._api_test_tool.client import APIClient
from n6sdk._api_test_tool.data_test import DataSpecTest
from n6sdk._api_test_tool.report import Report
from n6sdk._api_test_tool.validator_exceptions import (
    APIClientException,
    APIValidatorException,
)


def iter_config_base_lines():
    try:
        filename = resource_filename(Requirement.parse('n6sdk'),
                                     'n6sdk/_api_test_tool/config_base.ini')
        with open(filename, 'rb') as f:
            for line in f.read().splitlines():
                yield line.decode('utf-8')
    finally:
        cleanup_resources()

def get_config(path):
    config = configparser.RawConfigParser()
    config.read(path, encoding='utf-8')
    conf_dict = {}
    for section in config.sections():
        for key, value in config.items(section):
            conf_dict[key] = value
    return config, conf_dict

def get_base_url(url):
    obj = urlparse(url)
    return u"{}://{}{}".format(obj.scheme, obj.netloc, obj.path)

def make_url(url, constant_params, optional_params=None, renderer='sjson'):
    '''
    @param: url: base url
    @param: constant_params: mandatory search query parameters
    @param: optional_params: optional search query parameters
    @param: renderer (json, sjson)
    @return: full api url with query parameters
    '''
    query = urlencode(constant_params)
    if not optional_params:
        return u"{0}?{1}".format(url, query)
    else:
        options = urlencode(optional_params)
        return u"{0}?{1}&{2}".format(url, query, options)

def main():
    requests.packages.urllib3.disable_warnings()  # to turn off InsecureRequestWarning

    parser = argparse.ArgumentParser()
    excl_args = parser.add_mutually_exclusive_group(required=True)
    excl_args.add_argument(
        '--generate-config',
        action='store_true',
        help='generate the config file template, then exit')
    excl_args.add_argument(
        '-c', '--config',
        help='test an n6-like API using the specified config file')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='be more descriptive')
    args = parser.parse_args()

    if args.generate_config:
        for line in iter_config_base_lines():
            print(line)  # using OS-specific newlines
        sys.exit(0)

    config_handler, config = get_config(args.config)

    # Preparing stuff
    ca_cert = config.get('cert_path', None)
    ca_key = config.get('key_path', None)
    base_url = get_base_url(config.get('base_url'))
    constant_params_list = config_handler.options('constant_params')
    constant_params = dict((item, config.get(item)) for item in constant_params_list)

    report = Report()
    ds_test = DataSpecTest()
    client = APIClient(ca_cert, ca_key, verify=False)

    #
    # Testing basic search url response and data_spec compatibility
    #

    report.section("Testing basic search query. Getting representative data sample", 1)
    data_url = make_url(base_url, constant_params)

    # Prepare data range sets for each key of returned json objects
    data_range = defaultdict(set)
    composed_keys = {u'address', u'client', u'injects'}
    additional_attributes = set([])

    report.info('Inferring data structure model + testing basic compliance', 1)
    if args.verbose:
        report.info('Testing URL: "{}"'.format(data_url), 1)
    try:
        response = client.get_stream(data_url)
        for data in response:
            for key, val in data.items():
                if key in composed_keys:
                    val = json.dumps(val)
                try:
                    data_range[key].add(val)
                except TypeError:
                    report.info(
                        "Additional composed items detected in API response: {}".format(key), 1)

                ds_test.validate_data_format(data)
                if args.verbose:
                    report.info("OK, proper result item", 1)

            # test for n6-specific keys
            nonstandard_keys = ds_test.get_nonstandard_fields(data)
            for key in nonstandard_keys:
                additional_attributes.add(key)

        report.info("Non-standard keys found: {}".format(
            ", ".join(
                '"{}"'.format(k)
                for k in sorted(additional_attributes))), 1)
        report.info("Returned data seems to be properly formatted", 1)

    except APIClientException as e:
        sys.exit("FATAL ERROR: {}".format(e))
    except APIValidatorException as e:
        report.error("Data validation error: {}".format(e), 1)

    #
    # Make request with legal params
    #

    report.section("Testing a query with two random LEGAL params", 2)
    MAX_RETRY = 100
    something_processed = False
    test_legal_ok = True
    optional_params_keys = data_range.keys() - constant_params.keys()
    optional_params_keys = ds_test.all_param_keys.intersection(optional_params_keys)
    for _ in range(MAX_RETRY):
        rand_keys = random.sample(optional_params_keys, 2)
        rand_vals = (random.sample(data_range[val], 1)[0] for val in rand_keys)
        optional_params = dict(zip(rand_keys, rand_vals))
        legal_query_url = make_url(base_url, constant_params, optional_params)
        test_legal_ok = True
        try:
            filtered_legal = client.get_stream(legal_query_url)
            something_processed = False
            for record in filtered_legal:
                if not something_processed:
                    something_processed = True
                    if args.verbose:
                        report.info('Testing URL: "{}"'.format(legal_query_url), 2)
                for key, val in record.items():
                    if key in optional_params and val != optional_params[key]:
                        report.error('Wrong filtering result with query: {}'.format(
                            optional_params), 2)
                    else:
                        if args.verbose:
                            report.info('OK, proper result item', 2)
            if something_processed:
                break
        except APIClientException as e:
            test_legal_ok = False
            report.error("Connection exception: {}".format(e), 2)
            break
    if not something_processed:
        report.error("Could not pick any pair of random legal keys", 2)
    elif test_legal_ok:
        report.info("Filtering seems to work as expected", 2)

    #
    # Make request with illegal params
    #

    report.section("Testing queries with ILLEGAL params", 3)
    illegal_query_urls = []
    illegal_keys = data_range.keys() - ds_test.all_param_keys - composed_keys
    illegal_keys = illegal_keys.difference(additional_attributes)
    illegal_vals = (random.sample(data_range[val], 1)[0] for val in illegal_keys)
    illegal_params = dict(zip(illegal_keys, illegal_vals))

    for key, val in illegal_params.items():
        illegal_query_urls.append(make_url(base_url, constant_params, {key: val}))

    test_illegal_ok = True
    for illegal in illegal_query_urls:
        if args.verbose:
            report.info('Testing illegal URL: "{}"'.format(illegal), 3)
        try:
            filtered_illegal = client.get_stream(illegal)
            for record in filtered_illegal:
                pass
            code = client.status()
            exc_msg = '<no exception>'
        except APIClientException as e:
            code = getattr(e, 'code', None)
            exc_msg = str(e)
        if code == requests.codes.bad_request:
            if args.verbose:
                report.info("OK, proper behaviour: {}".format(exc_msg), 3)
        else:
            test_illegal_ok = False
            if code is None:
                report.error("Connection exception: {}".format(exc_msg), 3)
            else:
                report.error("Wrong response code: {}, should be: 400 (Bad Request).".format(
                    code), 3)
    if test_illegal_ok:
        report.info("Query validation seems to work as expected", 3)

    #
    # Make request with legal all single params
    #

    report.section("Testing queries with all single LEGAL params", 4)
    MINIMUM_VALUE_NUMBER = 3
    keys_list = []
    test_single_legal_ok = True
    for optional_key in optional_params_keys:
        if len(data_range[optional_key]) >= MINIMUM_VALUE_NUMBER:
            keys_list.append(optional_key)
        rand_val = random.sample(data_range[optional_key], 1)[0]
        opt_param = {optional_key: rand_val}
        legal_query_url = (make_url(base_url, constant_params, opt_param))
        if args.verbose:
            report.info('Testing URL: "{}"'.format(legal_query_url), 4)
        try:
            filtered_legal = client.get_stream(legal_query_url)
            for record in filtered_legal:
                for key, val in record.items():
                    if key in opt_param and val != opt_param[key]:
                        report.error('Wrong filtering result with query: {}'.format(
                            opt_param), 4)
                    else:
                        if args.verbose:
                            report.info('OK, proper result item', 4)
        except APIClientException as err:
            test_single_legal_ok = False
            report.error("Connection exception: {}".format(err), 4)
    if test_single_legal_ok:
        report.info("Filtering seems to work as expected", 4)

    #
    # Make request with legal list params
    #

    report.section("Testing queries with a LEGAL param, using different values", 5)
    test_key = random.choice(keys_list)
    random_val_list = random.sample(data_range[test_key], MINIMUM_VALUE_NUMBER)
    test_list_legal_ok = True
    for test_value in random_val_list:
        opt_param = {test_key: test_value}
        legal_query_url = (make_url(base_url, constant_params, opt_param))
        if args.verbose:
            report.info('Testing URL: "{}"'.format(legal_query_url), 5)
        try:
            filtered_legal = client.get_stream(legal_query_url)
            for record in filtered_legal:
                for key, val in record.items():
                    if key in opt_param and val != opt_param[key]:
                        report.error('Wrong filtering result with query: {}'.format(
                            opt_param), 5)
                    else:
                        if args.verbose:
                            report.info('OK, proper result item', 5)
        except APIClientException as err:
            test_list_legal_ok = False
            report.error("Connection exception: {}".format(err), 5)
    if test_list_legal_ok:
        report.info("Filtering seems to work as expected", 5)

    report.show()

    if report.has_errors():
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
