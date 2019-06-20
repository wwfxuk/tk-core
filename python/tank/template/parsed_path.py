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
Parsing of template paths into values for specified keys using a list of static tokens
"""
from collections import namedtuple
import os
import re

from ..errors import TankError
from ..log import LogManager
from ..templatekey import TemplateKey

"""
Container class used to store possible resolved values during template
parsing.  Stores the possible value as well as the downstream hierarchy
of possible values, the last error found whilst parsing and a flag
to specify if any of the branches in the downstream hierarchy are fully
resolved (a value was found for every remaining key)

:var value:                 The resolved value to keep track of
:var downstream_values:     ResolvedValue instances for all possible downstream branches of
                            possible resolved values
:var fully_resolved:        Flag to track if any of the downstream branches are fully resolved
                            or not
:var last_error:            The last error reported from the template parsing for the current
                            branch of possible values.

..code-block: python

    >>> var_def = 'shots/{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.ma'
    >>> re.split(r'\{[^\}]+\}', var_def)
    ['shots/', '/', '/', '/work/', '.', '.v', '.', '.ma']
    >>>
"""
ResolvedValue = namedtuple(
    'ResolvedValue',
    ['value', 'downstream_values', 'fully_resolved', 'last_error'],
)

TokenPosition = namedtuple('TokenPosition', ['start', 'end'])


def trimmed_indices(token_positions, amount):
    """Subtract all indices in given token positions by a certain amount.

    :param amount: Amount to subtract all indices by.
    :type amount: int
    :param token_positions: List of all token positions
    :type token_positions: list[list[(int, int)]]
    :return: New token positions with all indices trimmed.
    :rtype: list[list[(int, int)]]
    """
    return [
        [(start - amount, end - amount) for start, end in positions]
        for positions in token_positions
    ]


class ParsedPath(object):
    """
    Class for parsing a path for a known set of keys, and known set of static
    tokens which should appear between the key values.
    """

    def __init__(self, input_path, variation_parts, skip_keys=None, resolved_fields=None):
        """Parse a given input path with tokens and keys provided.

        :param input_path: Path to parse.
        :type input_path: str
        :param variation_parts: Tokens and keys used to help parse the path.
        :type variation_parts: list
        :param skip_keys: Key names to skip parsing.
        :type skip_keys: list[str]
        :param resolved_fields: Internal use: Resolved key names and values.
        :type resolved_fields: dict[str, str]
        """
        # self.fully_resolved = not(variation_parts) or not(input_path)
        self.input_path = input_path
        self.parts = variation_parts
        self.skip_keys = skip_keys or []
        self.fields = resolved_fields or {}
        self.downstream = []
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.unresolved_keys = []
        self.static_tokens = []

        # all token comparisons are done case insensitively.
        self.last_error = None
        self.fully_resolved = not self.input_path
        self.normal_path = os.path.normpath(self.input_path)
        self.lower_path = self.normal_path.lower()

        if self.input_path:
            if self.parts:
                path_part = self.parts[0]

                if isinstance(path_part, TemplateKey):
                    key_length = path_part.length
                    self._populate_keys_tokens()
                    token_positions = self._get_token_positions()
                    next_token_positions = token_positions[0]

                    for token_start, token_end in next_token_positions:
                        if key_length is not None and token_start < key_length:
                            continue

                        # get the possible value substring:
                        input_sub_str = self.normal_path[:token_start]

                        possible_value = self.resolve_key(path_part, input_sub_str)
                        if possible_value is None:
                            continue

                        possible_fields = self.fields.copy()
                        possible_fields[path_part.name] = possible_value
                        possible_path = ParsedPath(
                            self.normal_path[token_end:],
                            self.parts[2:],
                            skip_keys=self.skip_keys,
                            resolved_fields=possible_fields,
                        )
                        self.downstream.append(possible_path)
                elif self.lower_path.startswith(path_part.lower()):
                    possible_path = ParsedPath(
                        self.normal_path[len(path_part):],
                        self.parts[1:],
                        skip_keys=self.skip_keys,
                        resolved_fields=self.fields.copy(),
                    )
                    self.downstream.append(possible_path)
                else:
                    message = ("Template has no keys and first token (%s) "
                               "doesn't match the input path (%s)")
                    self._error(message, path_part, self.lower_path)

                resolved_paths = [path for path in self.downstream if path.fully_resolved]
                self.fully_resolved = bool(resolved_paths)
                if len(resolved_paths) == 1:
                    self.last_error = resolved_paths[0].last_error
                    self.fields = {
                        key_name: value
                        for key_name, value in resolved_paths[0].fields.items()
                        if key_name not in self.skip_keys
                    }
                elif resolved_paths:
                    error = 'Multiple possible solutions found for %s'
                    error_lines = ['"{0}"'.format(self.normal_path)]
                    error_lines += [str(path.fields) for path in resolved_paths]
                    self._error(error, '\n - '.join(error_lines))
                else:
                    error = 'No possible solutions found for %s'
                    error_lines = ['"{0}"'.format(self.normal_path)]
                    error_lines += [path.last_error for path in self.downstream]
                    self._error(error, '\n - '.join(error_lines))
            else:
                self._error('Input path still remains (after parsing): "%s"', self.input_path)

    def __nonzero__(self):
        return self.last_error is None and self.fully_resolved

    def __str__(self):
        return '{0} "{1}" {2}'.format(
            '*' if self else ' ',
            self.input_path,
            self.fields,
        )

    def resolve_key(self, template_key, text):
        """Resolve the template key value for a given input text.

        :param template_key: Template key to resolve value for.
        :type template_key: TemplateKey
        :param text: Input text used to resolve template key with
        :type text: str
        :return: Resolved template key value. None if failed/error.
        :rtype: str or None
        """
        previous_resolve = str(self.fields.get(template_key.name, ''))
        resolved_value = None

        if template_key.name in self.skip_keys:
            # don't bother doing validation/conversion for this value as it's being skipped!
            resolved_value = text
        elif os.path.sep in text:
            # validate the value for this key:

            # slashes are not allowed in key values!  Note, the possible value is a section
            # of the input path so the OS specific path separator needs to be checked for:
            self._error("%s: Invalid value found for key %s: %s",
                        self, template_key.name, text)
        elif previous_resolve and text != previous_resolve:
            # can't have two different values for the same key:
            self._error("%s: Conflicting values found for key %s: %s and %s",
                        self, template_key.name,
                        previous_resolve, text)
        else:
            # get the actual value for this key - this will also validate the value:
            try:
                resolved_value = template_key.value_from_str(text)
            except TankError as error:
                # it appears some locales are not able to correctly encode
                # the error message to str here, so use the %r form for the error
                # (ticket 24810)
                self._error("%s: Failed to get value for key '%s' - %r",
                            self, template_key.name, error)

        return resolved_value

    def _populate_keys_tokens(self):
        for part in self.parts:
            if isinstance(part, TemplateKey):
                self.unresolved_keys.append(part)
            else:
                self.static_tokens.append(part.lower())

    def _error(self, message, *message_args):
        """Set ``last_error`` and record error on logger.

        :param message: Message with C-style formatting tokens
        :type message: str
        :param message_args: Values to format message with
        :type message_args: object
        """
        self.last_error = message % message_args
        self.logger.error(message, *message_args)

    def _get_token_positions(self):
        """Find all occurrences of all tokens in the path.


        Possible token positions are split into domains where the first
        occurrence of a token must be after the first occurrence of the
        preceding token and the last occurrence must be before the last
        occurrence of the following token.  e.g. The valid tokens for
        the example path are shown below::

            Template : {shot}_{name}_v{version}.ma
            Path     : shot_010_name_v010.ma
            Token _  :    [_   _]
            Token _v :             [_v]
            Token .ma:                  [.ma]

        :yields list[int]: Positions of index the token is found at.
        """
        start_pos = 0
        max_index = len(self.lower_path)
        token_positions = []
        input_last_index = len(self.normal_path)

        for token in self.static_tokens:
            positions = []
            previous_start = start_pos

            for found in re.finditer(re.escape(token), self.lower_path):
                position = TokenPosition(*found.span())
                if position.start >= previous_start:
                    if not positions:
                        # this is the first instance of this token we found so it
                        # will be the start position to look for the next token
                        # as it will be the first possible location available!
                        start_pos = position.end
                    positions.append(position)

            if positions:
                token_positions.append(positions)
            else:
                self._error("Tried to extract fields but the path does not "
                            "fit the template:\n%s\n%s^--- Failed to find "
                            "token \"%s\" from here",
                            self.lower_path, " " * start_pos, token)
                break

        else:  # No break from: for token in self.static_tokens
            # Remove positions that can't be valid after for loop completed
            # i.e. Where the position is greater than the
            #      last possible position of any subsequent tokens
            for index in reversed(range(len(token_positions))):
                new_positions = [
                    token_position
                    for token_position in token_positions[index]
                    if token_position.start < max_index
                ]
                token_positions[index] = new_positions
                max_index = max(new_positions) if new_positions else 0

        return token_positions or [[(input_last_index, input_last_index)]]
