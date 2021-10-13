# Copyright (c) 2015-2021 NASK. All rights reserved.

from __future__ import print_function                                     #3--
import datetime


class Report(object):
    '''
    Class for reporting issues from API test. It's a primitive templating
    system to report information to the user.
    '''
    _summary = None
    _sections = {}

    def __init__(self):
        self._summary = ''
        self._errors = False

    def section(self, title, key):
        self._sections[key] = {
            'title': title,
            'info': [],
            'error': [],
        }

    def info(self, msg, section_no):
        self._sections[section_no]['info'].append("INFO\t{}".format(msg))

    def error(self, msg, section_no):
        self._sections[section_no]['error'].append("ERROR\t{}".format(msg))

    def has_errors(self):
        return True if self._errors else False

    def section_summary(self, section_no, errors=False):
        if errors:
            self._summary += (
                "Problem in section {} ({}). Please refer to n6sdk docs: "
                "http://n6sdk.readthedocs.org\n".format(
                    section_no, self._sections[section_no].get('title')))
        else:
            self._summary += (
                "Validation successful for section {} ({}).\n".format(
                    section_no, self._sections[section_no].get('title')))

    def show(self):
        '''
        Print formatted report.
        '''
        print("\n\nAPI Testing report (date {}Z)".format(datetime.datetime.utcnow()))
        for section_no in self._sections:
            print('\n\nSection no. {}: {}\n'.format(
                section_no, self._sections[section_no].get('title')))
            info = self._sections[section_no].get('info')
            print('\n'.join(info))
            errors = self._sections[section_no].get('error')
            if errors:
                self._errors = True
                print('\n'.join(errors))
            self.section_summary(section_no, errors)
        print("\n\n\n")
        print("--------------------")
        print(" SUMMARY:")
        print("--------------------")
        print(self._summary)
        if not self.has_errors():
            print("API validated successfully!\n\n")
