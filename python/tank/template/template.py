# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Management of file and directory templates.

"""

import re

from .variation import Variation
from .parsed_path import ParsedPath
from ..errors import TankError
from ..constants import TEMPLATE_KEY_NAME_REGEX


class Template(object):
    """
    Represents an expression containing several dynamic tokens
    in the form of :class:`TemplateKey` objects.
    """

    def __init__(self, definition, keys, name=None, prefix=''):
        """
        This class is not designed to be used directly but
        should be subclassed by any Template implementations.

        Current implementations can be found in
        the :class:`TemplatePath` and :class:`TemplateString` classes.

        :param definition: Template definition.
        :type definition: String
        :param keys: Mapping of key names to keys
        :type keys: Dictionary
        :param name: (Optional) name for this template.
        :type name: String
        :param prefix: (Optional) Internal use: prefix for calculating static
                       tokens and root paths.
        :type prefix: String
        """
        self.name = name
        self._prefix = prefix

        # version for __repr__
        self._repr_def = self._fix_key_names(definition, keys)

        self._variations = [
            Variation(var_def, keys, template_name=name, prefix=prefix)
            for var_def in self._definition_variations(definition)
        ]

    def __repr__(self):
        class_name = self.__class__.__name__
        if self.name:
            return "<Sgtk %s %s: %s>" % (class_name, self.name, self._repr_def)
        else:
            return "<Sgtk %s %s>" % (class_name, self._repr_def)

    @property
    def definition(self):
        """
        The template as a string, e.g ``shots/{Shot}/{Step}/pub/{name}.v{version}.ma``
        """
        # Use first definition as it should be most inclusive in case of variations
        return self._variations[0].fixed

    @property
    def _static_tokens(self):
        """
        All static tokens in a nested list of lists.

        Not sure why test_templatepath cares about this but here it is for
        legacy/fallback sake.

        :return: List of static tokens lists from all variations.
        :rtype: list[list[str]]
        """
        return [variation.static_tokens for variation in self._variations]

    @property
    def _keys(self):
        """
        All keys in a nested list of lists.

        Not sure why test_templatepath cares about this but here it is for
        legacy/fallback sake.

        :return: List of keys lists from all variations.
        :rtype: list[dict[str]]
        """
        return [variation.named_keys for variation in self._variations]

    @property
    def keys(self):
        """
        The keys that this template is using. For a template
        ``shots/{Shot}/{Step}/pub/{name}.v{version}.ma``, the keys are ``{Shot}``,
        ``{Step}`` and ``{name}``.

        :returns: a dictionary of class:`TemplateKey` objects, keyed by token name.
        """
        # First keys should be most inclusive
        return self._keys[0].copy()

    def is_optional(self, key_name):
        """
        Returns true if the given key name is optional for this template.

        For the template ``{Shot}[_{name}]``,
        ``is_optional("Shot")`` would return ``False`` and ``is_optional("name")``
        would return ``True``

        :param key_name: Name of template key for which the check should be carried out
        :returns: True if key is optional, False if not.
        """
        # the key is required if it's in the
        # minimum set of keys for this template
        if key_name in min(self._keys):
            # this key is required
            return False
        else:
            return True

    def missing_keys(self, fields, skip_defaults=False):
        """
        Determines keys required for use of template which do not exist
        in a given fields.

        Example::

            >>> tk.templates["max_asset_work"].missing_keys({})
            ['Step', 'sg_asset_type', 'Asset', 'version', 'name']

            >>> tk.templates["max_asset_work"].missing_keys({"name": "foo"})
            ['Step', 'sg_asset_type', 'Asset', 'version']


        :param fields: fields to test
        :type fields: mapping (dictionary or other)
        :param skip_defaults: If true, do not treat keys with default values as missing.
        :type skip_defaults: Bool

        :returns: Fields needed by template which are not in inputs keys or which have
                  values of None.
        :rtype: list
        """
        # find shortest keys dictionary
        keys = min(self._keys)
        return self._missing_keys(fields, keys, skip_defaults)

    def _missing_keys(self, fields, keys, skip_defaults):
        """
        Compares two dictionaries to determine keys in second missing in first.

        :param fields: fields to test
        :param keys: Dictionary of template keys to test
        :param skip_defaults: If true, do not treat keys with default values as missing.
        :returns: Fields needed by template which are not in inputs keys or which have
                  values of None.
        """
        if skip_defaults:
            required_keys = [key.name for key in keys.values() if key.default is None]
        else:
            required_keys = keys

        return [key for key in required_keys if fields.get(key) is None]

    def apply_fields(self, fields, platform=None):
        """
        Creates path using fields. Certain fields may be processed in special ways, for
        example :class:`SequenceKey` fields, which can take a `FORMAT` string which will intelligently
        format a image sequence specifier based on the type of data is being handled. Example::

            # get a template object from the API
            >>> template_obj = sgtk.templates["maya_shot_publish"]
            <Sgtk Template maya_asset_project: shots/{Shot}/{Step}/pub/{name}.v{version}.ma>

            >>> fields = {'Shot': '001_002',
                          'Step': 'comp',
                          'name': 'main_scene',
                          'version': 3
                          }

            >>> template_obj.apply_fields(fields)
            '/projects/bbb/shots/001_002/comp/pub/main_scene.v003.ma'

        .. note:: For formatting of special values, see :class:`SequenceKey` and :class:`TimestampKey`.

        Example::

            >>> fields = {"Sequence":"seq_1", "Shot":"shot_2", "Step":"comp", "name":"henry", "version":3}

            >>> template_path.apply_fields(fields)
            '/studio_root/sgtk/demo_project_1/sequences/seq_1/shot_2/comp/publish/henry.v003.ma'

            >>> template_path.apply_fields(fields, platform='win32')
            'z:\studio_root\sgtk\demo_project_1\sequences\seq_1\shot_2\comp\publish\henry.v003.ma'

            >>> template_str.apply_fields(fields)
            'Maya Scene henry, v003'


        :param fields: Mapping of keys to fields. Keys must match those in template
                       definition.
        :param platform: Optional operating system platform. If you leave it at the
                         default value of None, paths will be created to match the
                         current operating system. If you pass in a sys.platform-style string
                         (e.g. ``win32``, ``linux2`` or ``darwin``), paths will be generated to
                         match that platform.

        :returns: Full path, matching the template with the given fields inserted.
        """
        return self._apply_fields(fields, platform=platform)

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
        ignore_types = ignore_types or []

        # find largest key mapping without missing values
        keys = None
        missing_keys = []
        # index of matching keys will be used to find cleaned_definition
        index = -1
        for index, cur_keys in enumerate(self._keys):
            missing_keys = self._missing_keys(fields, cur_keys, skip_defaults=True)
            if not missing_keys:
                keys = cur_keys
                break

        if keys is None:
            raise TankError("Tried to resolve a path from the template %s and a set "
                            "of input fields '%s' but the following required fields were missing "
                            "from the input: %s" % (self, fields, missing_keys))

        # Process all field values through template keys
        processed_fields = {}
        for key_name, key in keys.items():
            value = fields.get(key_name)
            ignore_type = key_name in ignore_types
            processed_fields[key_name] = key.str_from_value(value, ignore_type=ignore_type)

        return self._variations[index].cleaned % processed_fields

    def _definition_variations(self, definition):
        """
        Determines all possible definition based on combinations of optional sectionals.

        "{foo}"               ==> ['{foo}']
        "{foo}_{bar}"         ==> ['{foo}_{bar}']
        "{foo}[_{bar}]"       ==> ['{foo}', '{foo}_{bar}']
        "{foo}_[{bar}_{baz}]" ==> ['{foo}_', '{foo}_{bar}_{baz}']

        """
        # split definition by optional sections
        tokens = re.split(r"(\[[^]]*\])", definition)

        # seed with empty string
        definitions = ['']
        for token in tokens:
            temp_definitions = []
            # regex return some blank strings, skip them
            if token == '':
                continue
            if token.startswith('['):
                # check that optional contains a key
                if not re.search("{*%s}" % TEMPLATE_KEY_NAME_REGEX, token):
                    raise TankError("Optional sections must include a key definition.")

                # Add definitions skipping this optional value
                temp_definitions = definitions[:]
                # strip brackets from token
                token = re.sub(r'[\[\]]', '', token)

            # check non-optional contains no dangling brackets
            if re.search(r"[\[\]]", token):
                raise TankError("Square brackets are not allowed outside of optional section definitions.")

            # make definitions with token appended
            for definition in definitions:
                temp_definitions.append(definition + token)

            definitions = temp_definitions

        # We want them most inclusive(longest) version first
        return sorted(definitions, key=lambda x: len(x), reverse=True)

    def _fix_key_names(self, definition, keys):
        """
        Substitutes key name for name used in definition
        """
        # Substitute key names for original key input names(key aliasing)
        for old_name, key in keys.items():
            if old_name != key.name:
                old_def = r"{%s}" % old_name
                new_def = r"{%s}" % key.name
                definition = re.sub(old_def, new_def, definition)
        return definition

    @property
    def parent(self):
        """
        Returns Template representing the parent of this object.

        :returns: :class:`Template`
        """
        raise NotImplementedError

    def validate_and_get_fields(self, path, required_fields=None, skip_keys=None):
        """
        Takes an input string and determines whether it can be mapped to the template pattern.
        If it can then the list of matching fields is returned. Example::

            >>> good_path = '/studio_root/sgtk/demo_project_1/sequences/seq_1/shot_2/comp/publish/henry.v003.ma'
            >>> template_path.validate_and_get_fields(good_path)
            {'Sequence': 'seq_1',
             'Shot': 'shot_2',
             'Step': 'comp',
             'name': 'henry',
             'version': 3}

            >>> bad_path = '/studio_root/sgtk/demo_project_1/shot_2/comp/publish/henry.v003.ma'
            >>> template_path.validate_and_get_fields(bad_path)
            None


        :param path:            Path to validate
        :param required_fields: An optional dictionary of key names to key
                                values. If supplied these values must be
                                present in the input path and found by the
                                template.
        :param skip_keys:       List of field names whose values should be
                                ignored

        :returns:               Dictionary of fields found from the path or
                                None if path fails to validate
        """
        required_fields = required_fields or {}
        skip_keys = skip_keys or []

        # Path should split into keys as per template
        path_fields = {}
        try:
            path_fields = self.get_fields(path, skip_keys=skip_keys)
        except TankError:
            return None

        # Check that all required fields were found in the path:
        for key, value in required_fields.items():
            if (key not in skip_keys) and (path_fields.get(key) != value):
                return None

        return path_fields

    def validate(self, path, fields=None, skip_keys=None):
        """
        Validates that a path can be mapped to the pattern given by the template. Example::

            >>> good_path = '/studio_root/sgtk/demo_project_1/sequences/seq_1/shot_2/comp/publish/henry.v003.ma'
            >>> template_path.validate(good_path)
            True

            >>> bad_path = '/studio_root/sgtk/demo_project_1/shot_2/comp/publish/henry.v003.ma'
            >>> template_path.validate(bad_path)
            False

        :param path:        Path to validate
        :type path:         String
        :param fields:      An optional dictionary of key names to key values. If supplied these values must
                            be present in the input path and found by the template.
        :type fields:       Dictionary
        :param skip_keys:   Field names whose values should be ignored
        :type skip_keys:    List
        :returns:           True if the path is valid for this template
        :rtype:             Bool
        """
        return self.validate_and_get_fields(path, fields, skip_keys) is not None

    def get_fields(self, input_path, skip_keys=None):
        """
        Extracts key name, value pairs from a string. Example::

            >>> input_path = '/studio_root/sgtk/demo_project_1/sequences/seq_1/shot_2/comp/publish/henry.v003.ma'
            >>> template_path.get_fields(input_path)

            {'Sequence': 'seq_1',
             'Shot': 'shot_2',
             'Step': 'comp',
             'name': 'henry',
             'version': 3}

        :param input_path: Source path for values
        :type input_path: String
        :param skip_keys: Optional keys to skip
        :type skip_keys: List

        :returns: Values found in the path based on keys in template
        :rtype: Dictionary
        """
        parsed = None

        for variation in self._variations:
            parsed = ParsedPath(input_path, variation.parts, skip_keys=skip_keys)
            if parsed:
                return parsed.fields

        if parsed is not None:
            raise TankError("Template %s: %s" % (str(self), parsed.last_error))
