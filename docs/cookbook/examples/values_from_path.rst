###############################
Getting template values from a path
###############################

In the "Resolving a template path" example, we showed how to apply values to to a template in order to resolve a path.
It is also possible to do the reverse, which is to say, given a path and a template, we can get the values back::

    import sgtk

    # We have a path that we would like to get back the values we put in to resolve it in the first place
    filePath = "/projects/life_of_a_slug/assets/Character/Slug/model/maya/Slug_02_Model_slug_v002.mb"

    # get an instance of sgtk based on our file path
    tk = sgtk.sgtk_from_path(filePath)

    # work out which template was used for the path
    template = tk.template_from_path(filePath)

    # Get all the values for the fields in the template, using the path
    fields = template.get_fields(filePath)