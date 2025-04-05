# Copyright (c) 2016-2025 NASK. All rights reserved.

import argparse
from jinja2 import (
    Environment,
    FileSystemLoader,
)

from n6datapipeline.notifier import (
    NotifierTemplateError,
    raise_helper,
)
from n6lib.config import ConfigMixin


class NotifierTemplatesRenderer(ConfigMixin):

    config_spec = '''
        [notifier_templates_renderer]
        templates_dir_path
        template_name
        last_send_time = 2016-10-01 15:56:08
        now = 2016-10-21 15:56:08
        modified_min = 2015-10-21 15:56:08
        modified_max = 2016-09-21 15:56:08
        time_min = 2016-10-21 12:00:00
        client_name ; client email
        client_org_name
        client_n6stream_api_enabled :: bool
        msg :: json ; {category: the number of occurrences}
    '''

    def __init__(self, notifications_language_list, template_name, templates_dir_path):
        self.notifications_language_list = notifications_language_list
        for name, value in self.get_config_section().items():
            setattr(self, name, value)
        if template_name is not None:
            self.template_name = template_name
        if templates_dir_path is not None:
            self.templates_dir_path = templates_dir_path
        env = Environment(
            loader=FileSystemLoader(self.templates_dir_path),
            extensions=['jinja2.ext.do'],
        )
        env.globals['template_raise'] = raise_helper
        self.template = env.get_template(self.template_name)

    def run(self):
        for notifications_language in self.notifications_language_list:
            try:
                html_message = self.template.render(
                    counter=self.msg,
                    last_send_time_dt=self.last_send_time,
                    now_dt=self.now,
                    modified_min=self.modified_min,
                    modified_max=self.modified_max,
                    time_min=self.time_min,
                    client_name=self.client_name,
                    client_org_name=self.client_org_name,
                    client_n6stream_api_enabled=self.client_n6stream_api_enabled,
                    notifications_language=notifications_language,
                )
                print("Notifications language: ", notifications_language)
                print(html_message)
            except NotifierTemplateError as exc:
                print(exc)
                continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', nargs='+', default=['EN'], help='One or more language versions (default: EN).')
    parser.add_argument('-t', help='Template name (default: value from the config file).')
    parser.add_argument('-d', help='Templates dir path (default: value from the config file).')
    args = parser.parse_args()
    notifications_language_list = args.l
    notifications_language_list = [x.lower() for x in notifications_language_list]
    template_name = args.t
    work_dir = args.d
    template_renderer = NotifierTemplatesRenderer(
        notifications_language_list,
        template_name,
        work_dir,
    )
    template_renderer.run()


if __name__ == "__main__":
    main()
