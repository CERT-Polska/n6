from pyramid.scaffolds import PyramidTemplate

class BasicN6SDKTemplate(PyramidTemplate):
    _template_dir = 'basic_n6sdk_scaffold'
    summary = '*n6sdk*-based REST API project'

    def pre(self, command, output_dir, vars):
        vars['capitalized_package'] = self._smart_capitalize(vars['package'])
        return PyramidTemplate.pre(self, command, output_dir, vars)

    def _smart_capitalize(self, s):
        return ''.join(s.capitalize() for s in s.replace('_', ' ').split())
