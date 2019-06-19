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
import logging
import os
import re

from ..errors import TankError
from ..log import LogManager
from ..constants import TEMPLATE_KEY_NAME_REGEX
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

class PathPart(object):
    def __init__(self, part, possible_values):
        self.part = part
        self.possible_values = possible_values


class ParsedPath(object):
    """
    Class for parsing a path for a known set of keys, and known set of static
    tokens which should appear between the key values.
    """

    def __init__(self, input_path, variation, skip_keys=None, resolved_fields=None):
        """
        Construction

        :param ordered_keys:    Template key objects in order that they appear in the
                                template definition.
        :param static_tokens:   Pieces of the definition that don't represent Template Keys.
        """
        self.input_path = input_path
        self.named_keys = variation.named_keys
        self.definition = variation.expanded
        self.skip_keys = skip_keys or []
        self.downstream = []

        # all token comparisons are done case insensitively.
        self.lower_path = self.input_path.lower()
        self.fields = resolved_fields
        self.last_error = None

        self.logger = LogManager.get_logger(self.__class__.__name__)
        # file_handler = logging.FileHandler('/home/joseph/repos/tk-core/var/parser.log')
        # file_handler.setLevel(logging.INFO)
        # self.logger.addHandler(file_handler)

        self.parts = self._create_definition_parts()
        self.full_resolve_length = len(self.ordered_keys)

        self.fields = self.parse_path()

        if self.ordered_keys:
            token_positions = self._get_token_positions()
            if token_positions and token_positions[-1]:
                # find all possible values for keys based on token positions - this will
                # return a list of lists including all potential variations:
                num_keys = len(self.ordered_keys)
                num_tokens = len(self.static_tokens)
                self.downstream = []
                first_token_positions = token_positions[0]
                if not isinstance(self.parts[0], TemplateKey):
                    # path may start with the first static token - possible scenarios:
                    #    t-k-t
                    #    t-k-t-k
                    #    t-k-t-k-k
                    if (num_keys >= num_tokens - 1):
                        self.downstream.extend(
                            self._get_resolved_values(
                                len(self.parts[0]),
                                self.static_tokens[1:],
                                token_positions[1:],
                                self.ordered_keys))

                    # we've handled this case so remove the first position:
                    first_token_positions = first_token_positions[1:]

                if len(first_token_positions) > 0:
                    # we still have non-zero positions for the first token so the
                    # path may actually start with a key - possible scenarios:
                    #    k-t-k
                    #    k-t-k-t
                    #    k-t-k-k
                    if (num_keys >= num_tokens):
                        self.downstream.extend(
                            self._get_resolved_values(
                                0,
                                self.static_tokens,
                                token_positions,
                                self.ordered_keys))

                if self.downstream:
                    # ensure that we only have a single set of valid values for all keys.  If we don't
                    # then attempt to report the best error we can
                    from pprint import pformat
                    self.logger.debug(pformat(self.downstream))
                    self.fields = {}
                    for key in self.ordered_keys:
                        key_value = None
                        if not self.downstream:
                            # we didn't find any possible values for this key!
                            break
                        elif len(self.downstream) == 1:
                            first_downstream = self.downstream[0]
                            if not first_downstream.fully_resolved:
                                # failed to fully resolve the path!
                                self.last_error = first_downstream.last_error
                                self.fields = None
                                break

                            # only found one possible value!
                            key_value = first_downstream.value
                            self.downstream = first_downstream.downstream_values
                        else:
                            # found more than one possible value so check to see how many are fully resolved:
                            resolves = [v for v in self.downstream if v.fully_resolved]
                            num_resolved = len(resolves)

                            if num_resolved == 1:
                                # only found one resolved value - awesome!
                                key_value = resolves[0].value
                                self.downstream = resolves[0].downstream_values
                            else:
                                if num_resolved > 1:
                                    # found more than one valid value so value is ambiguous!
                                    ambiguous_results = resolves
                                else:
                                    # didn't find any fully resolved values so we have multiple
                                    # non-fully resolved values which also means the value is ambiguous!
                                    ambiguous_results = self.downstream

                                # Try get a solution from previously found result, if any
                                ambiguous_values = [v.value for v in ambiguous_results]
                                key_value = self.fields.get(key.name)
                                if key_value is not None and key_value in ambiguous_values:
                                    existing_index = ambiguous_values.index(key_value)
                                    self.downstream = ambiguous_results[existing_index].downstream_values
                                else:
                                    self.logger.debug('key_value: %s', key_value)
                                    self.logger.debug('ambiguous_values: %s', ambiguous_values)
                                    self.logger.debug('self.fields: %s', self.fields)
                                    self._error("Ambiguous values found for key '%s' could be any of: '%s'",
                                                key.name, "', '".join(ambiguous_values))
                                    self.fields = None
                                    break

                        # if key isn't a skip key then add it to the self.fields dictionary:
                        if key_value is not None and key.name not in self.skip_keys:
                            self.fields[key.name] = key_value
                else:
                    # failed to find anything!
                    if not self.last_error:
                        self._error("Tried to extract fields from path '%s', "
                                    "but the path does not fit the template.",
                                    self.input_path)
                    self.fields = None

            else:  # not(token_positions and token_positions[-1])
                # didn't find all tokens!
                self.fields = None

        else:  # not(self.ordered_keys)
            # if no keys, nothing to discover
            self.fields = self._empty_ordered_keys_fields()

    @property
    def ordered_keys(self):
        return [part for part in self.parts if isinstance(part, TemplateKey)]

    @property
    def static_tokens(self):
        return [
            part.lower()
            for part in self.parts
            if not isinstance(part, TemplateKey)
        ]

    def _resolve_path(self, input_path):
        """WIP and TESTING
        """
        self.logger.info('input_path: "%s"', input_path)
        part = self.parts.pop(0)
        if isinstance(part, TemplateKey):
            key_name = part.name
            if key_name in self.skip_keys:
                pass
            else:
                # get the actual value for this key - this will also validate the value:
                try:
                    self.logger.debug('Resolving "%s" using "%s"',
                                      key_name, part)
                    # possible_value = part.value_from_str(part)
                except TankError as e:
                    # it appears some locales are not able to correctly encode
                    # the error message to str here, so use the %r form for the error
                    # (ticket 24810)
                    self._error("%s: Failed to get value for key '%s' - %r",
                                self, key_name, e)
                    # continue

        else:  # Token
            pattern = '^' + re.escape(part)
            token_matched = re.search(pattern, input_path)
            if token_matched:
                trim_from_index = token_matched.end()
                if trim_from_index < len(input_path) and self.parts:
                    return self._resolve_path(input_path[trim_from_index:])
            else:  # Token not matched, ERROR
                self.last_error = part + 'Not matched'

    def _create_definition_parts(self):
        """Create a list of tokens and keys for the expanded definition.

        :return: Tokens and keys for the expanded definition.
        :rtype: list
        """
        parts = []
        token_start = 0
        regex = re.compile(r"{(?P<key_name>%s)}" % TEMPLATE_KEY_NAME_REGEX)

        for found in regex.finditer(self.definition):
            token_end = found.start()
            token = found.string[token_start:token_end]
            if token:
                parts.append(token.lower())  # Match our lowercase static tokens

            key_name = found.group('key_name')
            template_key = self.named_keys.get(key_name)
            if template_key is not None:
                parts.append(template_key)

            token_start = found.end()

        if token_start < len(self.definition):
            parts.append(self.definition[token_start:])

        return parts

    def _error(self, message, *message_args):
        """Set ``last_error`` and record error on logger.

        :param message: Message with C-style formatting tokens
        :type message: str
        :param message_args: Values to format message with
        :type message_args: list
        """
        self.last_error = message % message_args
        self.logger.error(message, *message_args)

    def _empty_ordered_keys_fields(self):
        # if no keys, nothing to discover
        fields = None

        if self.static_tokens:
            if self.lower_path == self.static_tokens[0]:
                # this is a template where there are no keys
                # but where the static part of the template is matching
                # the input path
                # (e.g. template: foo/bar - input path foo/bar)
                fields = {}
            else:
                message = ("Template has no keys and first token (%s) "
                           "doesn't match the input path (%s)")
                self._error(message, self.static_tokens[0], self.lower_path)
                fields = None

        return fields

    def _get_token_positions(self):
        """Find all occurrences of all tokens in the path.


        Possible token positions are split into domains where the first
        occurrance of a token must be after the first occurrance of the
        preceding token and the last occurrance must be before the last
        occurrance of the following token.  e.g. The valid tokens for
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

        for token in self.static_tokens:
            positions = []
            previous_start = start_pos

            for found in re.finditer(re.escape(token), self.lower_path):
                token_start, token_end = found.span()
                if token_start >= previous_start:
                    if not positions:
                        # this is the first instance of this token we found so it
                        # will be the start position to look for the next token
                        # as it will be the first possible location available!
                        start_pos = token_end
                    positions.append((token_start, token_end))

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
                    (token_start, token_end)
                    for token_start, token_end in token_positions[index]
                    if token_start < max_index
                ]
                token_positions[index] = new_positions
                max_index = max(new_positions) if new_positions else 0

        return token_positions

