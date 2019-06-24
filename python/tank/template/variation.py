

import os
import re

from ..errors import TankError
from ..constants import TEMPLATE_KEY_NAME_REGEX


class Variation(object):
    """Variation for a particular Template."""

    def __init__(self, definition, keys, template_name=None, prefix=''):
        """Construct a variation for a particular definition and template keys.

        :param definition: Template definition variation.
        :type definition: str
        :param keys: Mapping of key names to keys.
        :type keys: dict[str, TemplateKey]
        :param template_name: (Optional) name for parent template.
        :type template_name: str
        :param prefix: (Optional) Internal use: prefix for calculating static
                       tokens and root paths.
        :type prefix: str
        """
        self._original = None
        self._cleaned = None
        self._expanded = None
        self._fixed = None
        self._named_keys = None
        self._ordered_keys = None
        self._static_tokens = None
        self._parts = []

        # Set up initial values first so downstream updates can trigger safely
        self._original = definition
        self._keys = keys
        self._name = template_name
        self._prefix = prefix

        # Trigger downstream updates
        self.original = definition

    def _repopulate_keys(self):
        """Extracts Template Keys from original definition and input keys."""
        self._named_keys = {}
        self._ordered_keys = []

        # regular expression to find key names
        regex = r"(?<={)%s(?=})" % TEMPLATE_KEY_NAME_REGEX
        for key_name in re.findall(regex, self.original):
            key = self.keys.get(key_name)
            if key is None:
                message = (
                    "Template definition for template \"{0}\" refers to key "
                    "{{1}}, which does not appear in supplied keys."
                )
                raise TankError(message.format(self.name, key_name))
            else:
                if self._named_keys.get(key.name, key) != key:
                    # Different keys using same name
                    message = (
                        "Template definition for template \"{0}\" uses two "
                        "keys which use the name \"{1}\"."
                    )
                    raise TankError(message.format(self.name, key.name))
                self._named_keys[key.name] = key
                self._ordered_keys.append(key)

        # Downstream updates
        if self.expanded:
            self._repopulate_parts()

    def _update_fixed_definition(self):
        """
        Substitutes key name for name used in definition (key aliasing)
        """
        self._fixed = self.original
        for old_name, key in self.keys.items():
            if old_name != key.name:
                old_def = re.escape(r"{%s}" % old_name)
                new_def = r"{%s}" % key.name
                self._fixed = re.sub(old_def, new_def, self._fixed)

        # Downstream updates
        self._update_expanded_definition()
        self._update_cleaned_definition()

    def _update_cleaned_definition(self):
        """
        Update cleaned definition.

        Has key names as strings and no format, enum or default values
        """
        regex = r"{(%s)}" % TEMPLATE_KEY_NAME_REGEX
        self._cleaned = re.sub(regex, "%(\g<1>)s", self._fixed)

    def _update_expanded_definition(self):
        """
        Update the full expanded definition with prefix (if any).
        """
        if self.fixed:
            self._expanded = os.path.join(self.prefix, self.fixed)
        else:
            self._expanded = self.prefix

        # Downstream updates
        self._update_static_tokens()
        self._repopulate_parts()

    def _update_static_tokens(self):
        """
        Finds tokens from expanded definition not involved in defining keys.

        Expand the definition to include the prefix unless the definition is
        empty in which case we just want to parse the prefix.

        For example, in the case of a path template, having an empty definition
        would result in expanding to the project/storage root.
        """
        regex = r"{%s}" % TEMPLATE_KEY_NAME_REGEX
        tokens = re.split(regex, self.expanded.lower())

        # Remove empty strings
        self._static_tokens = [token for token in tokens if token]

    def _repopulate_parts(self):
        """Create a list of tokens and keys for the expanded definition."""
        self._parts = []
        token_start = 0
        regex = re.compile(r"{(?P<key_name>%s)}" % TEMPLATE_KEY_NAME_REGEX)

        for found in regex.finditer(self.expanded):
            token_end = found.start()
            token = found.string[token_start:token_end]
            if token:
                self._parts.append(token)  # Match our lowercase static tokens

            key_name = found.group('key_name')
            template_key = self.named_keys.get(key_name)
            if template_key is not None:
                self._parts.append(template_key)

            token_start = found.end()

        if token_start < len(self.expanded):
            self._parts.append(self.expanded[token_start:])

    @property
    def parts(self):
        """Tokens and keys for the expanded definition.

        :return: Tokens and keys for the expanded definition.
        :rtype: list
        """
        return self._parts

    @property
    def named_keys(self):
        return self._named_keys

    @property
    def ordered_keys(self):
        return self._ordered_keys

    @property
    def static_tokens(self):
        return self._static_tokens

    @property
    def cleaned(self):
        return self._cleaned

    @property
    def fixed(self):
        return self._fixed

    @fixed.setter
    def fixed(self, fixed_definition):
        self._fixed = fixed_definition

        # Downstream updates
        self._update_expanded_definition()
        self._update_cleaned_definition()

    @property
    def original(self):
        return self._original

    @original.setter
    def original(self, definition):
        self._original = definition

        # Downstream updates
        self._repopulate_keys()
        self._update_fixed_definition()

    @property
    def expanded(self):
        return self._expanded

    @property
    def keys(self):
        return self._keys

    @keys.setter
    def keys(self, input_keys):
        self._keys = input_keys

        # Downstream updates
        self._repopulate_keys()
        self._update_fixed_definition()

    @property
    def name(self):
        return self._name

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, prefix):
        self._prefix = prefix

        # Downstream updates
        self._update_expanded_definition()

