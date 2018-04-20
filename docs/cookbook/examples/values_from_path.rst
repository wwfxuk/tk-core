###################################
Getting template values from a path
###################################

In the "Resolving a template path" example, we showed how to apply values to to a template in order to resolve a path.
It is also possible to do the reverse, which is to say, given a path and a template, we can get the values back.

.. code-block:: python

    import sgtk

    # We have a path that we would like to get back the values we put in to resolve it in the first place
    filePath = "projects/new_project/assets/Prop/Gear/model/work/maya/gear.v010.ma"

    # get an instance of sgtk based on our file path
    tk = sgtk.sgtk_from_path(filePath)

    # work out which template was used for the path
    template = tk.template_from_path(filePath)

    # Get all the values for the fields in the template, using the path
    fields = template.get_fields(filePath)

In this example the template was called "maya_asset_work" and looked like this
`'assets/{sg_asset_type}/{Asset}/{Step}/work/maya/{name}.v{version}.{maya_extension}'`
The resulting fields value would then look like this

.. code-block:: python

    {'Asset': 'Gear',
     'Step': 'model',
     'extension': 'ma',
     'name': 'gear',
     'sg_asset_type': 'Prop',
     'version': 10}



Practical Applications
----------------------

This can be useful if you have a bunch of files and you want to find the highest version,
amongst them, you could loop over the files and extract the version numbers from the path.
It also useful if you are looking to extract the {name} the artist gave to a render or scene file.