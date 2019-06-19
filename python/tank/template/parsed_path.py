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

    def __init__(self, input_path, variation, skip_keys=None, resolved_fields=None):
        """
        Construction

        :param ordered_keys:    Template key objects in order that they appear in the
                                template definition.
        :param static_tokens:   Pieces of the definition that don't represent Template Keys.
        """
        self.input_path = os.path.normpath(input_path)
        self.variation = variation
        self.skip_keys = skip_keys or []
        self.downstream = []

        # all token comparisons are done case insensitively.
        self.lower_path = self.input_path.lower()
        self.fields = resolved_fields
        self.last_error = None

        self.logger = LogManager.get_logger(self.__class__.__name__)
        # file_handler = logging.FileHandler('/home/joseph/repos/tk-core/var/parser.log')
        # file_handler.setLevel(logging.DEBUG)
        # self.logger.addHandler(file_handler)

        self.full_resolve_length = len(self.ordered_keys)

        # self.logger.info('        key: %s\n        exp: %s\n'
        #                  '        ork: %s\n        tok: %s',
        #                  self.named_keys,
        #                  self.definition,
        #                  self.ordered_keys,
        #                  self.static_tokens,
        #                  )
        # parts_title = ['Parts found for: "%s"' % self.definition]
        # self.logger.info(
        #     '---------------- "%s"\n%s',
        #     self.input_path,
        #     '\n- '.join(parts_title + map(str, self.parts))
        # )

        if self.ordered_keys:
            token_positions = self._get_token_positions()
            if token_positions and token_positions[-1]:
                # find all possible values for keys based on token positions - this will
                # return a list of lists including all potential variations:
                num_keys = len(self.ordered_keys)
                num_tokens = len(self.static_tokens)

                first_token_positions = token_positions[0]
                if not isinstance(self.variation.parts[0], TemplateKey):
                    # we're handling this case so remove the first position:
                    position = first_token_positions.pop(0)

                    # path starts with the first static token - possible scenarios:
                    #    t-k-t
                    #    t-k-t-k
                    #    t-k-t-k-k
                    if num_keys >= (num_tokens - 1):


                        self.downstream = self._get_resolved_values(
                            self.input_path[position.end:],
                            self.static_tokens[1:],
                            trimmed_indices(token_positions[1:], position.end),
                            self.ordered_keys,
                        )

                if first_token_positions and num_keys >= num_tokens:
                    # we still have non-zero positions for the first token so the
                    # path may actually start with a key - possible scenarios:
                    #    k-t-k
                    #    k-t-k-t
                    #    k-t-k-k
                    self.downstream.extend(
                        self._get_resolved_values(
                            self.input_path,
                            self.static_tokens,
                            token_positions,
                            self.ordered_keys,
                        )
                    )

                if self.downstream:
                    # ensure that we only have a single set of valid values for all keys.  If we don't
                    # then attempt to report the best error we can
                    # self.logger.debug(pformat(self.downstream))
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

    def _get_resolved_values(self,
                             input_path,
                             static_tokens,
                             token_positions,
                             ordered_keys,
                             resolved_fields=None):
        """
        Recursively traverse through the tokens & keys to find all possible values for the keys
        given the available token positions im the path.

        :param input_path:      The starting point in the path where we should look for a value
                                for the next key
        :param static_tokens:   A list of the remaining static tokens to look for
        :param token_positions: A list of lists containing all the valid positions where each static token
                                can be found in the path
        :param ordered_keys:    A list of the remaining keys to find values for
        :param resolved_fields:      A dictionary of all values that were previously found for any keys

        :returns:               A list of ResolvedValue instances representing the hierarchy of possible
                                values for all keys being parsed.
        """
        input_length = len(input_path)
        resolved_fields = resolved_fields or {}
        current_key = ordered_keys[0]
        remaining_keys = ordered_keys[1:]
        remaining_tokens = static_tokens[1:]
        current_positions = [TokenPosition(input_length, input_length)]
        if token_positions:
            current_positions = token_positions[0]

        resolved_value = resolved_fields.get(current_key.name)

        # using the token positions, find all possible values for the key
        possible_values = []
        # self.logger.debug('%s\n        input_path: %s %s', '-' * 100, input_path, current_positions)
        for token_start, token_end in current_positions:

            # make sure that the length of the possible value substring will be valid:
            if token_start < 0:
                continue
            if current_key.length is not None and token_start < current_key.length:
                continue

            # get the possible value substring:
            possible_value_str = input_path[:token_start]
            # self.logger.debug('possible_value_str: %s [%d] <-- %s', possible_value_str, token_start, input_path)

            # from this, find the possible value:
            possible_value = None
            last_error = None
            if current_key.name in self.skip_keys:
                # don't bother doing validation/conversion for this value as it's being skipped!
                possible_value = possible_value_str
            else:
                # validate the value for this key:

                # slashes are not allowed in key values!  Note, the possible value is a section
                # of the input path so the OS specific path separator needs to be checked for:
                if os.path.sep in possible_value_str:
                    last_error = ("%s: Invalid value found for key %s: %s" %
                                  (self, current_key.name, possible_value_str))
                    continue

                # can't have two different values for the same key:
                if resolved_value and possible_value_str != resolved_value:
                    last_error = (
                            "%s: Conflicting values found for key %s: %s and %s" %
                            (self, current_key.name, resolved_value, possible_value_str))
                    continue

                # get the actual value for this key - this will also validate the value:
                try:
                    possible_value = current_key.value_from_str(possible_value_str)
                except TankError as e:
                    # it appears some locales are not able to correctly encode
                    # the error message to str here, so use the %r form for the error
                    # (ticket 24810)
                    last_error = ("%s: Failed to get value for key '%s' - %r" %
                                  (self, current_key.name, e))
                    continue

            downstream_values = []
            fully_resolved = False
            if remaining_keys:
                # still have keys to process:
                if token_end >= input_length:
                    # but we've run out of path!  This is ok
                    # though - we just stop processing keys...
                    fully_resolved = True
                else:
                    # have keys remaining and some path left to process so recurse to next position for next key:
                    results = list(resolved_fields.items())
                    results += [(current_key.name, possible_value_str)]

                    downstream_values = self._get_resolved_values(
                        input_path[token_end:],
                        remaining_tokens,
                        trimmed_indices(token_positions[1:], token_end),
                        remaining_keys,
                        resolved_fields={key: value for key, value in results},
                    )

                    # check that at least one of the returned values is fully
                    # resolved and find the last error found if any
                    fully_resolved = False
                    for v in downstream_values:
                        if v.fully_resolved:
                            fully_resolved = True
                        if v.last_error:
                            last_error = v.last_error

            elif remaining_tokens:
                # we don't have keys but we still have remaining tokens - this is bad!
                fully_resolved = False

            elif token_end != input_length:
                # no keys or tokens left but we haven't fully consumed the path either!
                fully_resolved = False

            else:
                # processed all keys and tokens and fully consumed the path
                fully_resolved = True

            # keep track of the possible values:
            possible_values.append(
                ResolvedValue(possible_value, downstream_values,
                              fully_resolved, last_error))

        return possible_values

    @property
    def ordered_keys(self):
        return [part for part in self.variation.parts if isinstance(part, TemplateKey)]

    @property
    def static_tokens(self):
        return [
            part.lower()
            for part in self.variation.parts
            if not isinstance(part, TemplateKey)
        ]

    def _resolve_path(self, input_path):
        """WIP and TESTING
        """
        self.logger.info('input_path: "%s"', input_path)
        part = self.variation.parts.pop(0)
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
                if trim_from_index < len(input_path) and self.variation.parts:
                    return self._resolve_path(input_path[trim_from_index:])
            else:  # Token not matched, ERROR
                self.last_error = part + 'Not matched'

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

        return token_positions
