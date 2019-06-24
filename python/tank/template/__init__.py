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
import sys

from .template import Template
from .template_path import TemplatePath, split_path
from .template_string import TemplateString
from .. import templatekey
from ..errors import TankError


__all__ = (
    '_conform_template_data',
    '_process_templates_data',
    'make_template_paths',
    'make_template_strings',
    'read_templates',
    'split_path',
    'Template',
    'TemplatePath',
    'TemplateString',
)


def read_templates(pipeline_configuration):
    """
    Creates templates and keys based on contents of templates file.

    :param pipeline_configuration: pipeline config object

    :returns: Dictionary of form {template name: template object}
    """
    per_platform_roots = pipeline_configuration.get_all_platform_data_roots()
    data = pipeline_configuration.get_templates_config()

    # get dictionaries from the templates config file:
    def get_data_section(section_name):
        # support both the case where the section
        # name exists and is set to None and the case where it doesn't exist
        d = data.get(section_name)
        if d is None:
            d = {}
        return d

    keys = templatekey.make_keys(get_data_section("keys"))

    template_paths = make_template_paths(
        get_data_section("paths"),
        keys,
        per_platform_roots,
        default_root=pipeline_configuration.get_primary_data_root_name()
    )

    template_strings = make_template_strings(get_data_section("strings"), keys, template_paths)

    # Detect duplicate names across paths and strings
    dup_names =  set(template_paths).intersection(set(template_strings))
    if dup_names:
        raise TankError("Detected paths and strings with the same name: %s" % str(list(dup_names)))

    # Put path and strings together
    templates = template_paths
    templates.update(template_strings)
    return templates

def make_template_paths(data, keys, all_per_platform_roots, default_root=None):
    """
    Factory function which creates TemplatePaths.

    :param data: Data from which to construct the template paths.
                 Dictionary of form: {<template name>: {<option>: <option value>}}
    :param keys: Available keys. Dictionary of form: {<key name> : <TemplateKey object>}
    :param all_per_platform_roots: Root paths for all platforms. nested dictionary first keyed by
                                   storage root name and then by sys.platform-style os name.
    :param default_root: Value for "root_name" when  missing from template data.

    :returns: Dictionary of form {<template name> : <TemplatePath object>}
    """

    if data and not all_per_platform_roots:
        raise TankError(
            "At least one root must be defined when using 'path' templates."
        )

    template_paths = {}
    templates_data = _process_templates_data(data, "path")

    for template_name, template_data in templates_data.items():
        definition = template_data["definition"]
        root_name = template_data.get("root_name")
        if not root_name:
            # If the root name is not explicitly set we use the default arg
            # provided
            if default_root:
                root_name = default_root
            else:
                raise TankError(
                    "The template %s (%s) can not be evaluated. No root_name "
                    "is specified, and no root name can be determined from "
                    "the configuration. Update the template definition to "
                    "include a root_name or update your configuration's "
                    "roots.yml file to mark one of the storage roots as the "
                    "default: `default: true`." % (template_name, definition)
                )
        # to avoid confusion between strings and paths, validate to check
        # that each item contains at least a "/" (#19098)
        if "/" not in definition:
            raise TankError("The template %s (%s) does not seem to be a valid path. A valid "
                            "path needs to contain at least one '/' character. Perhaps this "
                            "template should be in the strings section "
                            "instead?" % (template_name, definition))

        root_path = all_per_platform_roots.get(root_name, {}).get(sys.platform)
        if root_path is None:
            raise TankError("Undefined Shotgun storage! The local file storage '%s' is not defined for this "
                            "operating system." % root_name)

        template_paths[template_name] = TemplatePath(
            definition,
            keys,
            root_path,
            template_name,
            all_per_platform_roots[root_name]
        )

    return template_paths

def make_template_strings(data, keys, template_paths):
    """
    Factory function which creates TemplateStrings.

    :param data: Data from which to construct the template strings.
    :type data:  Dictionary of form: {<template name>: {<option>: <option value>}}
    :param keys: Available keys.
    :type keys:  Dictionary of form: {<key name> : <TemplateKey object>}
    :param template_paths: TemplatePaths available for optional validation.
    :type template_paths: Dictionary of form: {<template name>: <TemplatePath object>}

    :returns: Dictionary of form {<template name> : <TemplateString object>}
    """
    template_strings = {}
    templates_data = _process_templates_data(data, "path")

    for template_name, template_data in templates_data.items():
        definition = template_data["definition"]

        validator_name = template_data.get("validate_with")
        validator = template_paths.get(validator_name)
        if validator_name and not validator:
            msg = "Template %s validate_with is set to undefined template %s."
            raise TankError(msg %(template_name, validator_name))

        template_strings[template_name] = TemplateString(
            definition,
            keys,
            template_name,
            validate_with=validator,
        )

    return template_strings

def _conform_template_data(template_data, template_name):
    """
    Takes data for single template and conforms it expected data structure.
    """
    if isinstance(template_data, basestring):
        template_data = {"definition": template_data}
    elif not isinstance(template_data, dict):
        raise TankError("template %s has data which is not a string or dictionary." % template_name)

    if "definition" not in template_data:
        raise TankError("Template %s missing definition." % template_name)

    return template_data

def _process_templates_data(data, template_type):
    """
    Conforms templates data and checks for duplicate definitions.

    :param data: Dictionary in form { <template name> : <data> }
    :param template_type: path or string

    :returns: Processed data.
    """
    templates_data = {}
    # Track definition to detect duplicates
    definitions = {}

    for template_name, template_data in data.items():
        cur_data = _conform_template_data(template_data, template_name)
        definition = cur_data["definition"]
        if template_type == "path":
            root_name = cur_data.get("root_name")
        else:
            root_name = None

        # Record this templates definition
        cur_key = (root_name, definition)
        definitions[cur_key] = definitions.get(cur_key, []) + [template_name]

        templates_data[template_name] = cur_data

    dups_msg = ""
    for (root_name, definition), template_names in definitions.items():
        if len(template_names) > 1:
            # We have a duplicate
            dups_msg += "%s: %s\n" % (", ".join(template_names), definition)

    if dups_msg:
        raise TankError("It looks like you have one or more "
                        "duplicate entries in your templates.yml file. Each template path that you "
                        "define in the templates.yml file needs to be unique, otherwise toolkit "
                        "will not be able to resolve which template a particular path on disk "
                        "corresponds to. The following duplicate "
                        "templates were detected:\n %s" % dups_msg)

    return templates_data
