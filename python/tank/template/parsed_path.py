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


class ParsedPath(object):
    """
    Class for parsing a path for a known set of keys, and known set of static
    tokens which should appear between the key values.
    """

    def __init__(self, input_path, var_info, skip_keys=None):
        """
        Construction

        :param ordered_keys:    Template key objects in order that they appear in the
                                template definition.
        :param static_tokens:   Pieces of the definition that don't represent Template Keys.
        """
        self.input_path = os.path.normpath(input_path)
        self.named_keys = var_info['named_keys']
        # self.ordered_keys = var_info['ordered_keys']
        self.definition = var_info['expanded']
        self.static_tokens = [token.lower() for token in var_info['static_tokens']]
        self.skip_keys = skip_keys or []

        # all token comparisons are done case insensitively.
        self.lower_path = self.input_path.lower()
        self.fields = None
        self.last_error = None

        self.logger = LogManager.get_logger(self.__class__.__name__)
        file_handler = logging.FileHandler('/home/joseph/repos/tk-core/var/parser.log')
        file_handler.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)

        self.parts = self._create_definition_parts()
        self.full_resolve_length = len(self.ordered_keys)

        # static_tokens = [
        #     part.lower()
        #     for part in self.parts
        #     if part and not isinstance(part, TemplateKey)
        # ]
        # static_tokens = [
        #     part.lower()
        #     for part in re.split(r"{%s}" % TEMPLATE_KEY_NAME_REGEX, self.definition.lower())
        #     if part and not isinstance(part, TemplateKey)
        # ]
        # assert len(static_tokens) == len(self.static_tokens)
        # for index, (our_token, self_token) in enumerate(zip(static_tokens, self.static_tokens)):
        #     assert our_token == self_token, '[{}] "{}" != "{}"\n  Expanded: {}\nDefinition: {}\nours: {}\nself: {}'.format(
        #         index, our_token, self_token, self.definition,
        #         variation.fixed, static_tokens, self.static_tokens)

        # self.logger.info('        key: %s\n        exp: %s\n'
        #                  '        ork: %s\n        tok: %s',
        #                  self.named_keys,
        #                  self.definition,
        #                  self.ordered_keys,
        #                  self.static_tokens,
        #                  )
        parts_title = ['Parts found for: "%s"' % self.definition]
        self.logger.info(
            '---------------- "%s"\n%s',
            self.input_path,
            '\n- '.join(parts_title + map(str, self.parts))
        )

        # if self.parts:
        #     resolve = self._resolve_path(self.lower_path)
        #     for token in static_tokens:
        self.fields = self.parse_path()

    @property
    def ordered_keys(self):
        return [part for part in self.parts if isinstance(part, TemplateKey)]

    # @property
    # def static_tokens(self):
    #     return [
    #         part.lower()
    #         for part in self.parts
    #         if not isinstance(part, TemplateKey)
    #     ]

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
                parts.append(token)

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
                token_pos = found.start()
                if token_pos >= previous_start:
                    if not positions:
                        # this is the first instance of this token we found so it
                        # will be the start position to look for the next token
                        # as it will be the first possible location available!
                        start_pos = found.end()
                    positions.append(token_pos)

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
                    position
                    for position in token_positions[index]
                    if position < max_index
                ]
                token_positions[index] = new_positions
                max_index = max(new_positions) if new_positions else 0

        return token_positions

    def parse_path(self):
        """
        Parses a path against the set of keys and static tokens to extract
        valid values for the keys.  This will make use of as much information
        as it can within all keys to correctly determine the value for a field
        and will detect if a key resolves to ambiguous values where there is
        not enough information to resolve correctly!

        e.g. with the template:

            {shot}_{name}_v{version}.ma

        and a path:

            shot_010_name_v001.ma

        The algorithm would correctly determine that the value for the shot key
        is 'shot_010' assuming that the name key is restricted to be
        alphanumeric. If name allowed underscores then the shot key would be
        ambiguous and would resolve to either 'shot' or 'shot_010'
        which would error.

        :returns:           If successful, a dictionary of field names mapped
                            to their values. None if fields can't be resolved.
        """
        # if no keys, nothing to discover
        if not self.ordered_keys:
            self.fields = self._empty_ordered_keys_fields()
            return self.fields

        token_positions = self._get_token_positions()
        if not(token_positions and token_positions[-1]):
            # didn't find all tokens!
            return None

        # ------------------------------>8-------------------------------------

        # find all possible values for keys based on token positions - this will
        # return a list of lists including all potential variations:
        num_keys = len(self.ordered_keys)
        num_tokens = len(self.static_tokens)
        possible_values = []
        if not isinstance(self.parts[0], TemplateKey):
            # path may start with the first static token - possible scenarios:
            #    t-k-t
            #    t-k-t-k
            #    t-k-t-k-k
            if (num_keys >= num_tokens - 1):
                possible_values.extend(
                    self.__find_possible_key_values_recursive(
                        self.input_path, len(self.static_tokens[0]),
                        self.static_tokens[1:], token_positions[1:],
                        self.ordered_keys))

            # we've handled this case so remove the first position:
            token_positions[0] = token_positions[0][1:]

        if len(token_positions[0]) > 0:
            # we still have non-zero positions for the first token so the
            # path may actually start with a key - possible scenarios:
            #    k-t-k
            #    k-t-k-t
            #    k-t-k-k
            if (num_keys >= num_tokens):
                possible_values.extend(
                    self.__find_possible_key_values_recursive(
                        self.input_path, 0, self.static_tokens, token_positions,
                        self.ordered_keys))

        if not possible_values:
            # failed to find anything!
            if not self.last_error:
                self.last_error = ("Tried to extract fields from path '%s', "
                                   "but the path does not fit the template." %
                                   self.input_path)
            return None

        # ensure that we only have a single set of valid values for all keys.  If we don't
        # then attempt to report the best error we can
        from pprint import pformat
        self.logger.debug(pformat(possible_values))
        self.fields = {}
        for key in self.ordered_keys:
            key_value = None
            if not possible_values:
                # we didn't find any possible values for this key!
                break
            elif len(possible_values) == 1:
                if not possible_values[0].fully_resolved:
                    # failed to fully resolve the path!
                    self.last_error = possible_values[0].last_error
                    return None

                # only found one possible value!
                key_value = possible_values[0].value
                possible_values = possible_values[0].downstream_values
            else:
                # found more than one possible value so check to see how many are fully resolved:
                resolved_possible_values = [
                    v for v in possible_values if v.fully_resolved
                ]
                num_resolved = len(resolved_possible_values)

                if num_resolved == 1:
                    # only found one resolved value - awesome!
                    key_value = resolved_possible_values[0].value
                    possible_values = resolved_possible_values[
                        0].downstream_values
                else:
                    if num_resolved > 1:
                        # found more than one valid value so value is ambiguous!
                        ambiguous_results = resolved_possible_values
                    else:
                        # didn't find any fully resolved values so we have multiple
                        # non-fully resolved values which also means the value is ambiguous!
                        ambiguous_results = possible_values

                    # Try get a solution from previously found result, if any
                    ambiguous_values = [v.value for v in ambiguous_results]
                    key_value = self.fields.get(key.name)
                    if key_value is not None and key_value in ambiguous_values:
                        possible_values = ambiguous_results[
                            ambiguous_values.index(
                                key_value)].downstream_values
                    else:
                        self.logger.debug('key_value: %s', key_value)
                        self.logger.debug('ambiguous_values: %s', ambiguous_values)
                        self.logger.debug('self.fields: %s', self.fields)
                        self.last_error = (
                            "Ambiguous values found for key '%s' could be any of: '%s'"
                            % (key.name, "', '".join(ambiguous_values)))
                        return None

            # if key isn't a skip key then add it to the self.fields dictionary:
            if key_value is not None and key.name not in self.skip_keys:
                self.fields[key.name] = key_value

        # ------------------------------>8-------------------------------------

        # return the single unique set of self.fields:
        return self.fields

    def __find_possible_key_values_recursive(self,
                                             path,
                                             key_position,
                                             tokens,
                                             token_positions,
                                             keys,
                                             key_values=None):
        """
        Recursively traverse through the tokens & keys to find all possible values for the keys
        given the available token positions im the path.

        :param path:            The path to find possible key values from
        :param key_position:    The starting point in the path where we should look for a value
                                for the next key
        :param tokens:          A list of the remaining static tokens to look for
        :param token_positions: A list of lists containing all the valid positions where each static token
                                can be found in the path
        :param keys:            A list of the remaining keys to find values for
        :param key_values:      A dictionary of all values that were previously found for any keys

        :returns:               A list of ResolvedValue instances representing the hierarchy of possible
                                values for all keys being parsed.
        """
        key_values = key_values or {}
        key = keys[0]
        keys = keys[1:]
        token = tokens[0] if tokens else ""
        tokens = tokens[1:]
        positions = token_positions[0] if token_positions else [len(path)]
        token_positions = token_positions[1:]

        key_value = key_values.get(key.name)

        # using the token positions, find all possible values for the key
        possible_values = []
        for token_position in positions:

            # make sure that the length of the possible value substring will be valid:
            if token_position <= key_position:
                continue
            if key.length is not None and token_position - key_position < key.length:
                continue

            # get the possible value substring:
            possible_value_str = path[key_position:token_position]

            # from this, find the possible value:
            possible_value = None
            last_error = None
            if key.name in self.skip_keys:
                # don't bother doing validation/conversion for this value as it's being skipped!
                possible_value = possible_value_str
            else:
                # validate the value for this key:

                # slashes are not allowed in key values!  Note, the possible value is a section
                # of the input path so the OS specific path separator needs to be checked for:
                if os.path.sep in possible_value_str:
                    last_error = ("%s: Invalid value found for key %s: %s" %
                                  (self, key.name, possible_value_str))
                    continue

                # can't have two different values for the same key:
                if key_value and possible_value_str != key_value:
                    last_error = (
                        "%s: Conflicting values found for key %s: %s and %s" %
                        (self, key.name, key_value, possible_value_str))
                    continue

                # get the actual value for this key - this will also validate the value:
                try:
                    self.logger.debug('Resolving "%s" using "%s"', key.name,
                                      possible_value_str)
                    possible_value = key.value_from_str(possible_value_str)
                except TankError as e:
                    # it appears some locales are not able to correctly encode
                    # the error message to str here, so use the %r form for the error
                    # (ticket 24810)
                    last_error = ("%s: Failed to get value for key '%s' - %r" %
                                  (self, key.name, e))
                    continue

            self.logger.debug('--> "%s"', possible_value)
            downstream_values = []
            fully_resolved = False
            if keys:
                # still have keys to process:
                if token_position + len(token) >= len(path):
                    # but we've run out of path!  This is ok
                    # though - we just stop processing keys...
                    fully_resolved = True
                else:
                    # have keys remaining and some path left to process so recurse to next position for next key:
                    downstream_values = self.__find_possible_key_values_recursive(
                        path, token_position + len(token), tokens,
                        token_positions, keys,
                        dict(key_values.items() +
                             [(key.name, possible_value_str)]))

                    # check that at least one of the returned values is fully
                    # resolved and find the last error found if any
                    fully_resolved = False
                    for v in downstream_values:
                        self.logger.debug('Checking downstream: %s', v)
                        if v.fully_resolved:
                            fully_resolved = True
                        if v.last_error:
                            last_error = v.last_error
                            self.logger.debug('x Found error: %s', last_error)

            elif tokens:
                # we don't have keys but we still have remaining tokens - this is bad!
                fully_resolved = False
                self.logger.debug('x Tokens remain')
            elif token_position + len(token) != len(path):
                # no keys or tokens left but we haven't fully consumed the path either!
                fully_resolved = False
                self.logger.debug('x Path not fully consumed')
            else:
                # processed all keys and tokens and fully consumed the path
                fully_resolved = True

            # keep track of the possible values:
            self.logger.debug('{:-^80}'.format(fully_resolved))
            possible_values.append(
                ResolvedValue(possible_value, downstream_values,
                              fully_resolved, last_error))

        return possible_values
