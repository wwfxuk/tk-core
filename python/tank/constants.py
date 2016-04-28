# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

# the name of the file that contains the storage root definitions
STORAGE_ROOTS_FILE = "roots.yml"

# hook that is executed when a tank instance initializes.
TANK_INIT_HOOK_NAME = "tank_init"

# hook to be executed after bundle install
BUNDLE_POST_INSTALL_HOOK = "post_install.py"

# metrics logging custom hooks blacklist
TANK_LOG_METRICS_CUSTOM_HOOK_BLACKLIST = [
    "pick_environment",
]

# hook that is executed whenever a PipelineConfiguration instance initializes.
PIPELINE_CONFIGURATION_INIT_HOOK_NAME = "pipeline_configuration_init"

# hook that is executed whenever a cache location should be determined
CACHE_LOCATION_HOOK_NAME = "cache_location"

# Configuration file containing setup and path details
PIPELINECONFIG_FILE = "pipeline_configuration.yml"

# Shotgun: The entity that represents Pipeline Configurations in Shotgun
PIPELINE_CONFIGURATION_ENTITY = "PipelineConfiguration"

# the storage name that is treated to be the primary storage for tank
PRIMARY_STORAGE_NAME = "primary"

# special dev descriptor token that can be used
# as a replacement for the path to a pipeline configuration
PIPELINE_CONFIG_DEV_DESCRIPTOR_TOKEN = "{PIPELINE_CONFIG}"

# the name of the file that holds the templates.yml config
CONTENT_TEMPLATES_FILE = "templates.yml"

# the name of the primary pipeline configuration
PRIMARY_PIPELINE_CONFIG_NAME = "Primary"

# valid characters for a template key name
TEMPLATE_KEY_NAME_REGEX = "[a-zA-Z_ 0-9\.]+"

# the name of the include section in env and template files
SINGLE_INCLUDE_SECTION = "include"

# the name of the includes section in env and template files
MULTI_INCLUDE_SECTION = "includes"

# the key sections in a template file
TEMPLATE_SECTIONS = ["keys", "paths", "strings"]

# the path section in a templates file
TEMPLATE_PATH_SECTION = "paths"

# the string section in a templates file
TEMPLATE_STRING_SECTION = "strings"

# a human readable explanation of the above. For error messages.
VALID_TEMPLATE_KEY_NAME_DESC = "letters, numbers, underscore, space and period"

