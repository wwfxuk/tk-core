
import os
from .template import Template


__all__ = ('TemplateString',)


class TemplateString(Template):
    """
    :class:`Template` class for templates representing strings.

    Template strings are useful if you want to write code where you can configure
    the formatting of strings, for example how a name or other string field should
    be configured in Shotgun, given a series of key values.
    """
    def __init__(self, definition, keys, name=None, validate_with=None):
        """
        TemplatePath objects are typically created automatically by toolkit reading
        the template configuration.

        :param definition: Template definition string.
        :param keys: Mapping of key names to keys (dict)
        :param name: Optional name for this template.
        :param validate_with: Optional :class:`Template` to use for validation
        """
        super(TemplateString, self).__init__(definition, keys, name=name, prefix="@")
        self.validate_with = validate_with

    @property
    def parent(self):
        """
        Strings don't have a concept of parent so this always returns ``None``.
        """
        return None

    def get_fields(self, input_path, skip_keys=None):
        """
        Extracts key name, value pairs from a string. Example::

            >>> input_name = 'filename.v003.ma'
            >>> template_string.get_fields(input_name)

            {'name': 'henry',
             'version': 3}

        :param input_path: Source path for values
        :type input_path: String
        :param skip_keys: Optional keys to skip
        :type skip_keys: List

        :returns: Values found in the path based on keys in template
        :rtype: Dictionary
        """
        # add path prefix as original design was to require project root
        adj_path = os.path.join(self._prefix, input_path)
        return super(TemplateString, self).get_fields(adj_path, skip_keys=skip_keys)
