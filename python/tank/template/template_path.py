
import os

from .template import Template
from ..errors import TankError


__all__ = ('TemplatePath', 'split_path')


class TemplatePath(Template):
    """
    :class:`Template` representing a complete path on disk. The template definition is multi-platform
    and you can pass it per-os roots given by a separate :meth:`root_path`.
    """
    def __init__(self, definition, keys, root_path, name=None, per_platform_roots=None):
        """
        TemplatePath objects are typically created automatically by toolkit reading
        the template configuration.

        :param definition: Template definition string.
        :param keys: Mapping of key names to keys (dict)
        :param root_path: Path to project root for this template.
        :param name: Optional name for this template.
        :param per_platform_roots: Root paths for all supported operating systems.
                                   This is a dictionary with sys.platform-style keys
        """
        super(TemplatePath, self).__init__(definition, keys, name=name, prefix=root_path)
        self._per_platform_roots = per_platform_roots

        # Make definition use platform separator, re-calculate other attributes
        for var_info in self._variations.values():
            definition = os.path.join(*split_path(var_info['definition']))
            var_info['definition'] = definition
            var_info['cleaned_definition'] = self._clean_definition(definition)
            var_info['static_tokens'] = self._calc_static_tokens(definition)

    @property
    def root_path(self):
        """
        Returns the root path associated with this template.
        """
        return self._prefix

    @property
    def parent(self):
        """
        Returns Template representing the parent of this object.

        For paths, this means the parent folder.

        :returns: :class:`Template`
        """
        parent_definition = os.path.dirname(self.definition)
        if parent_definition:
            return TemplatePath(parent_definition, self.keys, self.root_path, None, self._per_platform_roots)
        return None

    def _apply_fields(self, fields, ignore_types=None, platform=None):
        """
        Creates path using fields.

        :param fields: Mapping of keys to fields. Keys must match those in template
                       definition.
        :param ignore_types: Keys for whom the defined type is ignored as list of strings.
                            This allows setting a Key whose type is int with a string value.
        :param platform: Optional operating system platform. If you leave it at the
                         default value of None, paths will be created to match the
                         current operating system. If you pass in a sys.platform-style string
                         (e.g. 'win32', 'linux2' or 'darwin'), paths will be generated to
                         match that platform.

        :returns: Full path, matching the template with the given fields inserted.
        """
        relative_path = super(TemplatePath, self)._apply_fields(fields, ignore_types, platform)

        if platform is None:
            # return the current OS platform's path
            return os.path.join(self.root_path, relative_path) if relative_path else self.root_path

        else:
            # caller has requested a path for another OS
            if self._per_platform_roots is None:
                # it's possible that the additional os paths are not set for a template
                # object (mainly because of backwards compatibility reasons) and in this case
                # we cannot compute the path.
                raise TankError("Template %s cannot resolve path for operating system '%s' - "
                                "it was instantiated in a mode which only supports the resolving "
                                "of current operating system paths." % (self, platform))

            platform_root_path = self._per_platform_roots.get(platform)

            if platform_root_path is None:
                # either the platform is undefined or unknown
                raise TankError("Cannot resolve path for operating system '%s'! Please ensure "
                                "that you have a valid storage set up for this platform." % platform)

            elif platform == "win32":
                # use backslashes for windows
                if relative_path:
                    return "%s\\%s" % (platform_root_path, relative_path.replace(os.sep, "\\"))
                else:
                    # not path generated - just return the root path
                    return platform_root_path

            elif platform == "darwin" or "linux" in platform:
                # unix-like platforms - use slashes
                if relative_path:
                    return "%s/%s" % (platform_root_path, relative_path.replace(os.sep, "/"))
                else:
                    # not path generated - just return the root path
                    return platform_root_path

            else:
                raise TankError("Cannot evaluate path. Unsupported platform '%s'." % platform)


def split_path(input_path):
    """
    Split a path into tokens.

    :param input_path: path to split
    :type input_path: string

    :returns: tokenized path
    :rtype: list of tokens
    """
    cur_path = os.path.normpath(input_path)
    cur_path = cur_path.replace("\\", "/")
    return cur_path.split("/")
