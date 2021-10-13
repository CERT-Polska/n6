# Copyright (c) 2020-2021 NASK. All rights reserved.

import functools
from os.path import (
    expanduser,
    isabs,
)

from jinja2 import (
    ChoiceLoader,
    DictLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    TemplateError,
    select_autoescape,
)

from n6lib.common_helpers import ascii_str
from n6lib.config import Config
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


DEFAULT_AUTOESCAPE = select_autoescape(['html', 'htm', 'xml'])


def raise_template_error(message):
    raise TemplateError(message)


class JinjaTemplateBasedRenderer(object):

    """
    TODO: docs
    """

    config_spec = '''
        # Note: all this configuration stuff defined here is needed
        # *only* if the `JinjaTemplateBasedRenderer.from_predefined()`
        # constructor is used (in particular, this is the case when
        # `MailNoticesAPI` from the `n6lib.mail_notices_api` module
        # and/or `MailMessageBuilder` from the `n6lib.mail_sending_api`
        # module are in use). All other constructors provided by
        # `JinjaTemplateBasedRenderer` do not need any configuration
        # at all.

        [jinja_template_based_renderer]

        # The value of the following option should consist of (one or
        # more) comma-separated template locations that will be tried,
        # in the specified order, by Jinja's template loaders when
        # searching for templates.
        #
        # Each of these locations should be:
        #
        # * An *absolute* path of a directory (aka folder); if it makes
        #   use of a tilde-based home directory placeholder prefix, such
        #   as `~` or `~username`, the placeholder will be automatically
        #   expanded.
        #   Examples:
        #     /etc/n6/templates
        #     ~/my-own-n6-stuff/jinja-related
        #     ~dataman/.n6/our-custom-fancy-templates
        #
        # *OR*
        #
        # * A specification in the following format:
        #     @<package name>:<package subdirectory path>
        #   where:
        #      * <package name> is a Python package name
        #        (see also: the docs of the `jinja2.PackageLoader`'s
        #        parameter `package_name`);
        #      * <package subdirectory path> is a *relative* path of
        #        a directory (folder) in that package's source tree
        #        (see also: the docs of the `jinja2.PackageLoader`'s
        #        parameter `package_path`).
        #   Examples:
        #     @n6lib:data/templates
        #     @my.own.package:some-dir/sub-dir/sub-sub-dir
        template_locations = @n6lib:data/templates :: list_of_template_loc

        # The default value ("utf-8") of the following option, should be
        # OK in nearly all cases.
        template_encoding = utf-8 :: str

        # The following option is relevant *only* to template locations
        # specified as absolute paths of directories (*not* to those in
        # the `@<package name>:<package subdirectory path>` format).
        follow_symlinks = false :: bool

        # The value of the following option should consist of (zero or
        # more) comma-separated *import names* of Jinja extensions (see:
        # https://jinja.palletsprojects.com/extensions/). Typically, it
        # should contain, at the minimum, the "jinja2.ext.do" name -- at
        # least, as long as any of the default templates (those bundled
        # with *n6*) are in use.
        jinja_extensions = jinja2.ext.do :: list_of_str
    '''

    @classmethod
    def from_predefined(cls,
                        default_template_name=None,
                        autoescape=None,
                        settings=None,
                        **kwargs):
        config = Config.section(
            cls.config_spec,
            settings=settings,
            custom_converters={
                'list_of_template_loc': cls.__make_converter__list_of_template_loc(),
            })
        env = Environment(
            loader=PackageOrFileSystemLoader(
                locations=config['template_locations'],
                encoding=config['template_encoding'],
                fs_followlinks=config['follow_symlinks']),
            autoescape=(
                autoescape if autoescape is not None
                else DEFAULT_AUTOESCAPE))
        jinja_extensions = sorted(set(
            config['jinja_extensions']
            + list(kwargs.pop('jinja_extensions', []))))
        return cls(
            jinja_env=env,
            jinja_extensions=jinja_extensions,
            default_template_name=default_template_name,
            **kwargs)

    @staticmethod
    def __make_converter__list_of_template_loc():
        def convert_template_loc(loc):
            if loc.startswith('@'):
                try:
                    loc_parts = loc[1:].split(':', 1)
                    try:
                        package_name, package_subdir_path = loc_parts
                    except ValueError:
                        raise ValueError('the colon is missing')
                    if isabs(package_subdir_path):
                        raise ValueError('the subdirectory part is not a relative path')
                except ValueError as exc:
                    raise ValueError(
                        '{!r} is not a valid package-based template '
                        'location ({})'.format(loc, ascii_str(exc)))
                converted_loc = package_name, package_subdir_path
            else:
                converted_loc = expanduser(loc)
                if not isabs(converted_loc):
                    raise ValueError(
                        '{!r} is not a valid absolute-path-based template '
                        'location (is not an absolute path)'.format(loc))
            return converted_loc
        return Config.make_list_converter(convert_template_loc,
                                          name='list_of_template_loc')

    @classmethod
    def from_string(cls,
                    template_string,
                    template_name='anonymous_string_template',
                    **kwargs):
        return cls.from_dict(
            template_name_to_template_string={template_name: template_string},
            default_template_name=template_name,
            **kwargs)

    @classmethod
    def from_dict(cls,
                  template_name_to_template_string,
                  default_template_name=None,
                  autoescape=None,
                  **kwargs):
        template_name_to_template_string = {
            name: (tmpl.decode('utf-8') if isinstance(tmpl, (bytes, bytearray))
                   else tmpl)
            for name, tmpl in template_name_to_template_string.items()}
        env = Environment(
            loader=DictLoader(template_name_to_template_string),
            autoescape=(
                autoescape if autoescape is not None
                else DEFAULT_AUTOESCAPE))
        return cls(
            jinja_env=env,
            default_template_name=default_template_name,
            **kwargs)

    def __init__(self,
                 jinja_env,
                 jinja_extensions=('jinja2.ext.do',),
                 default_template_name=None,
                 render_context_base=None):
        self._env = self._prepare_env(jinja_env, jinja_extensions)
        self.default_template_name = default_template_name
        self.render_context_base = render_context_base

    def _prepare_env(self, jinja_env, jinja_extensions):
        for ext in jinja_extensions:
            jinja_env.add_extension(ext)
        jinja_env.globals['raise_template_error'] = raise_template_error
        return jinja_env

    def render(self, *args, **kwargs):
        (template_name,
         render_contexts) = self._pick_given_template_name_and_render_contexts(args, kwargs)
        template = self._get_template(template_name)
        actual_render_context = self._prepare_actual_render_context(render_contexts)
        return template.render(actual_render_context)

    def _pick_given_template_name_and_render_contexts(self, args, kwargs):
        str = basestring                                                         #3--
        if args and isinstance(args[0], str):
            template_name = args[0]
            render_contexts = args[1:]
        else:
            template_name = None
            render_contexts = args
        render_contexts += (kwargs,)
        return template_name, render_contexts

    def _get_template(self, template_name):
        if template_name is None:
            if self.default_template_name is None:
                raise ValueError('no template name specified')
            template_name = self.default_template_name
        self._verify_template_name_is_str(template_name)
        return self._env.get_template(template_name)

    def _verify_template_name_is_str(self, template_name):
        str = basestring                                                         #3--
        if not isinstance(template_name, str):
            raise TypeError('non-`str` template name: {!r} (of type: {!r})'.format(
                template_name,
                type(template_name).__name__))                                   #3: `__name__` -> `__qualname__`

    def _prepare_actual_render_context(self, render_contexts):
        actual_render_context = {}
        if self.render_context_base is not None:
            actual_render_context.update(self.render_context_base)
        for context in render_contexts:
            actual_render_context.update(context)
        return actual_render_context


class PackageOrFileSystemLoader(ChoiceLoader):

    """
    TODO: docs
    """

    def __init__(self,
                 # The `locations` argument should be a sequence (for
                 # example, a list). Each of its elements should specify
                 # a location of templates, in one of the following
                 # forms:
                 #
                 # * a `str` being an absolute path of a directory (folder);
                 #   example: '/home/dataman/.n6/templates';
                 #
                 # * a pair (2-tuple) that consists of:
                 #       1) a `str` being a Python package name,
                 #       2) a `str` being a relative path of a directory
                 #          (folder) in that package's source tree;
                 #   example: ('n6lib', 'data/templates').
                 locations,
                 encoding='utf-8',
                 fs_followlinks=False):
        loaders = [
            factory()
            for factory in self.__generate_loader_factories(locations, encoding, fs_followlinks)]
        super(PackageOrFileSystemLoader, self).__init__(loaders)

    def __generate_loader_factories(self, locations, encoding, fs_followlinks):
        for loc in locations:
            if isinstance(loc, tuple):
                package_name, package_subdir_path = loc
                yield functools.partial(
                        PackageLoader,
                        encoding=encoding,
                        package_name=package_name,
                        package_path=package_subdir_path)
            else:
                yield functools.partial(
                        FileSystemLoader,
                        encoding=encoding,
                        searchpath=[loc],
                        followlinks=fs_followlinks)
