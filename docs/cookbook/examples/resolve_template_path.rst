###############################
Resolving a template path
###############################

Toolkit templates are abstract paths made up of static elements and keys, and its how toolkit apps
figure out where to save scenes, renders, cameras etc. Given a template, a context and any other required bit of
information you can resolve a template into a full path, that can be used to save new files to.
For example if you want figure out the path to save your Maya Asset scene in, then in a default configuration you would
use the `maya_asset_work` template to resolve the actual path. The key thing is to make sure you provide values for
all the required keys in the template. Depending on the keys in the template, this can sometimes be resolved with the
context alone (assuming you have the right context), but normally a template will include some keys that can't be
acquired from the context obj alone.
::

    # create an sgtk api instance
    tk = sgtk.sgtk_from_entity("Project",86)

    # make sure that the schema folders have been generated for the context we are in
    tk.create_filesystem_structure("Task",12344)

    # Create a context (or gather it in some other way)
    ctx = tk.context_from_entity("Task",12344)

    # get a template instance for for the template we want to resolve into a path
    template = tk.templates["maya_asset_work"]

    # now use the context to resolve as many of the template fields as possible
    # this will generate a dictionary with the template key as the dictionary keys and the values that have been
    # extracted from the context.
    fields = ctx.as_template_fields(template)

    # Not all template keys can be resolved from the context obj alone,
    # so we must now provide values for any of the remaining keys with out values.
    # The version is one of these keys, so we must add the value.
    # Ideally we should check what the next version is going to be
    # but for the sake of simplicity in this example we will assume its always version 1
    fields['version'] = 1

    # now resolve the template path using the field values.
    resolved_path = template.apply_fields(fields)
