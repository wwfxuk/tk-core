# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""Parsing of template paths into values for variant parts."""
from collections import namedtuple
import os
import re

from ..errors import TankError
from ..log import LogManager
from ..templatekey import TemplateKey


TokenPosition = namedtuple(
    'TokenPosition',
    ['start', 'end'],
)

KeySolution = namedtuple(
    'KeySolution',
    ['key_name', 'value', 'remaining_path'],
)


class ParsedPath(object):
    """Parse a path for a known set of template keys/static path tokens.

    Passed downstream during recursion:

    - ``skip_keys``
    - Current ``fields`` (with possible key value solution)

    Passed upstream after recursion:

    - Immediate child paths stored as ``self.child_possibilities``
    - Unique resolved fields from children as ``self.fully_resolved``
    - If only 1 children has error, inherit that as ``self.last_error``

    :ivar input_path: Path parsed.
    :type input_path: str
    :ivar parts: Ordered TemplateKeys and non-template key texts to parse path.
    :type parts: list[TemplateKey or str]
    :ivar skip_keys: Optional TemplateKey names to skip validation.
    :type skip_keys: list[str]
    :ivar fields: Resolved template key names and values.
    :type fields: dict[str, str]
    :ivar last_error: Error message from parsing this or child paths.
    :type last_error: str or None
    :ivar possibilities: Child parsed paths directly under current instance.
    :type possibilities: list[ParsedPath]
    :ivar fully_resolved: All possible fully resolved key value combinations.
    :type fully_resolved: list[dict[str, str]]
    :ivar logger: Internal Python logger used to log messages.
    :type logger: logging.Logger
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
        self.last_error = None
        self.possibilities = []
        self.fully_resolved = []
        self.logger = LogManager.get_logger(self.__class__.__name__)

        # all token comparisons are done case insensitively.
        self._normal_path = os.path.normpath(self.input_path)
        self._lower_path = self._normal_path.lower()

        if self.input_path:
            if self.parts:
                self.possibilities = self._generate_possibilities()
                self.fully_resolved = self._resolve_possibilities()
            else:
                self._error(
                    'Path still remains (after parsing): "%s"',
                    self.input_path,
                )
        else:
            self.fully_resolved = [self.fields]

    def __nonzero__(self):
        """Whether there is no errors and at least 1 fully resolved field.

        :return: No errors and at least 1 fully resolved field.
        :rtype: bool
        """
        return self.last_error is None and bool(self.fully_resolved)

    def __str__(self):
        """Pretty string formatting for current instance.

        - Class name
        - No errors and fully resolved (``[*]`` if true, else ``[ ]``)
        - Input path parsed
        - Fields parsed from path

        :rtype: bool
        """
        template = '{0.__class__.__name__}[{1}] "{0.input_path}" {0.fields}'
        return template.format(self, '*' if self else ' ')

    def __repr__(self):
        """Compute the "official" string representation of this ParsedPath.

        If at all possible, this should look like a valid Python expression
        that could be used to recreate an object with the same value.

        :return: Official string representation of this ParsedPath.
        :rtype: str
        """
        template = (
            '{0.__class__.__name__}('
            '"{0.input_path}", '
            '{0.parts}, '
            'skip_keys={0.skip_keys}, '
            'resolved_fields={0.fields})'
        )
        return template.format(self)

    def _resolve_possibilities(self):
        """Resolve current possibilities.

        - If there's only 1 resolved solution from children, unset any current
          errors and set that key value mapping as fields. Otherwise,
        - If there's only 1 error from children, set it as current error.
          This is so messages are relevant to the actual place it occurred,
          which may be from a few levels deep into the recursion. Otherwise,
        - If there's multiple fully resolved solutions, log error against
          current input path. Otherwise,
        - If there's multiple errors from children, log all children
          errors against current input path.

        :return: Fully resolved key value mappings, if any.
        :rtype: list[dict[str, str]]
        """
        resolved_fields = []
        child_errors = []

        # Collect errors, UNIQUE resolved template key/values from children.
        for child_path in self.possibilities:
            if child_path.last_error is not None:
                child_errors.append(child_path.last_error)

            # Can't use sets: dicts are un-hashable but comparable
            for fields in child_path.fully_resolved:
                if fields not in resolved_fields:
                    resolved_fields.append(fields)

        if len(resolved_fields) == 1:
            self.last_error = None
            self.fields = {
                key_name: value
                for key_name, value in resolved_fields[0].items()
                if key_name not in self.skip_keys
            }
        elif len(child_errors) == 1:
            self.last_error = child_errors[0]
        elif resolved_fields:
            error = 'Multiple possible solutions found for %s'
            error_lines = ['"{0}"'.format(self._normal_path)]
            error_lines += [str(fields) for fields in resolved_fields]
            self._error(error, '\n - '.join(error_lines))
        else:
            error = 'No possible solutions found for %s'
            error_lines = ['"{0}"'.format(self._normal_path), self.last_error]
            self._error(error, '\n * '.join(error_lines + child_errors))

        return resolved_fields

    def _generate_possibilities(self):
        """Generate a list of possible (template key) outcomes.

        :return: Possible outcomes for child path parts.
        :rtype: list[ParsedPath]
        """
        possibilities = []
        current_part = self.parts[0]

        if isinstance(current_part, TemplateKey):
            possibilities.extend(self._resolve_key(current_part))
        else:
            current_lowercase = current_part.lower()
            if self._lower_path.startswith(current_lowercase):
                possible_path = ParsedPath(
                    self._normal_path[len(current_part):],
                    self.parts[1:],  # Start from next template key
                    skip_keys=self.skip_keys,
                    resolved_fields=self.fields.copy(),
                )
                possibilities.append(possible_path)
            else:
                message = (
                    "Template has no keys and first token (%s) "
                    "doesn't match the input path (%s)"
                )
                self._error(message, current_lowercase, self._lower_path)

        return possibilities

    def _resolve_key(self, template_key):
        """Resolve the template key value for a given input text.

        These conditions are checked in the following order:

        1. If key is being skipped, don't bother doing validation/conversion
           for the substring's value.

        2. Slashes (path separators) are not allowed in key values!

           .. note::
                The possible value is a section of the input path, so
                the OS specific path separator needs to be checked for

        3. If key has already been resolved, i.e. previous value exists in
           :attr:`fields`:

           a) If substring matches (``str()`` of) previous value, then
              the substring will be used as the **only possible solution**
              for this key at this part of the input path.
           b) If it **does not match**, then log an error for values
              not matching previous resolve.

        4. Check if :func:`TemplateKey.value_from_str()` successfully
           parses the substring into a valid value.

           .. note::
                It appears some locales are not able to correctly encode
                the error message to ``str`` here, so ``%r`` form is used
                for formatting errors (see ticket 24810)

        :param template_key: Template key to resolve value for.
        :type template_key: TemplateKey
        :return: Resolved template key value. None if failed/error.
        :rtype: str or None
        """
        possibilities = []
        key_length = template_key.length
        key_name = template_key.name
        previous_resolve = self.fields.get(key_name)
        next_token_positions = self._get_all_token_positions()[0]

        for token_start, token_end in next_token_positions:
            if key_length is not None and token_start < key_length:
                continue

            path_sub_str = self._normal_path[:token_start]
            possible_value = None
            using_previous = previous_resolve is not None

            if key_name in self.skip_keys:  # 1. Skipping validation for key
                possible_value = path_sub_str
            elif os.path.sep in path_sub_str:  # 2. No path separators
                self._error(
                    "%s: Invalid value found for key %s: %s",
                    self, key_name, path_sub_str,
                )
            else:
                try:
                    possible_value = template_key.value_from_str(path_sub_str)

                    # 3. Check if already resolved
                    if using_previous and possible_value != previous_resolve:
                        self._error(
                            "%s: [%s] Current value (%s) doesn't match "
                            "previously resolved value (%s)",
                            self, key_name, possible_value, previous_resolve,
                        )
                except TankError as error:
                    # 4. Check resolved value from substring
                    self._error(
                        "%s: Failed to get value for key '%s' - %r",
                        self, key_name, error,
                    )

            # Store possible solutions' information into possibilities
            if possible_value is not None:
                possible_solution = KeySolution(
                    key_name=key_name,
                    value=possible_value,
                    remaining_path=self._normal_path[token_end:],
                )
                if using_previous:
                    possibilities = [possible_solution]
                    break
                else:
                    possibilities.append(possible_solution)

        # Performance: defer recursion until all possibilities found
        return [
            self._create_possible_path(solution)
            for solution in possibilities
        ]

    def _create_possible_path(self, solution):
        """Create parsed path for a key's possible solution.

        The solution is added into a copy of the resolved fields mapping
        before creating a parsed path using it.

        :param solution: Possible solution to a template key.
        :type solution: KeySolution
        :return: Parsed path for a key's possible solution.
        :rtype: ParsedPath
        """
        resolved_fields = self.fields.copy()
        resolved_fields[solution.key_name] = solution.value

        return ParsedPath(
            solution.remaining_path,
            self.parts[2:],  # Start from next template key
            skip_keys=self.skip_keys,
            resolved_fields=resolved_fields,
        )

    def _error(self, message, *message_args):
        """Set ``last_error`` and record error on logger.

        :param message: Message with C-style formatting tokens
        :type message: str
        :param message_args: Values to format message with
        :type message_args: object
        """
        if message_args:
            self.last_error = message % message_args
            self.logger.error(message, *message_args)
        else:
            self.last_error = message
            self.logger.error(message)

    def _get_all_token_positions(self):
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

        :return: Positions of start, end indices the token is found at.
        :rtype: list[list[(int, int)]]
        """
        start_pos = 0
        max_index = len(self._lower_path)
        token_positions = []
        input_last_index = len(self._normal_path)
        static_tokens = (
            part.lower()
            for part in self.parts
            if not isinstance(part, TemplateKey)
        )

        for token in static_tokens:
            positions = []
            previous_start = start_pos

            for found in re.finditer(re.escape(token), self._lower_path):
                # Short for: start=found.start(), end=found.end()
                position = TokenPosition(*found.span())
                if position.start >= previous_start:
                    if not positions:
                        # First instance of this token we found. It will become
                        # the start position to look for the next token
                        # as it will be the first possible location available!
                        start_pos = position.end
                    positions.append(position)

            if positions:
                token_positions.append(positions)
            else:
                message = (
                    "Path does not fit the template:\n"
                    "%s\n"
                    "%s^--- Failed to find token \"%s\" from here"
                )
                self._error(message, self._lower_path, " " * start_pos, token)
                break

        else:  # No break from: for token in static_tokens
            for index in reversed(range(len(token_positions))):
                # Remove positions that can't be valid after for loop completed
                # i.e. Where the position is greater than the
                #      last possible position of any subsequent tokens
                new_maxes = []
                new_positions = []

                for token_position in token_positions[index]:
                    if token_position.start < max_index:
                        new_maxes.append(token_position.start)
                        new_positions.append(token_position)

                token_positions[index] = new_positions
                max_index = max(new_maxes) if new_maxes else 0

        # Fall back to positions for the end of input string if empty
        return token_positions or [[(input_last_index, input_last_index)]]