###############################
Importing sgtk
###############################

When importing the sgtk api, you have a few options. You can import a standalone version of sgtk
(ie not from an initialized toolkit configuration), but if you do this you are very limited by what you can do with it,
the main reason to do this would to be use the bootstrap methods. The more common use is to import the sgtk module
from a specific toolkit project configuration. The path to the sgtk api relative to your config is
`{config}/install/core/python`, so you can append your sys.path to include this location, and then you will be able
to import sgtk::

    import sys
    # append the folder location of the sgtk module for specific project configuration
    sys.path.append("/software/shotgun/my_project_config/install/core/python")
    import sgtk

Remember that if you import the api from project a, but then want to perform some operations on project b, you must
switch out the sgtk module for the project b one, by inserting the path to the project b config before the project a
config and reloading sgtk.