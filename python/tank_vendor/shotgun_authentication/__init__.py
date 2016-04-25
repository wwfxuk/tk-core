# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This class is for backwards compatibility only!

Please use the authentication module found in sgtk.authentication for
new code. This compatibility wrapper will be removed at some point in the future.
"""

from .errors import ShotgunAuthenticationError, AuthenticationError, IncompleteCredentials, AuthenticationCancelled
from .shotgun_authenticator import ShotgunAuthenticator
from .defaults_manager import DefaultsManager
from .user import deserialize_user, serialize_user
