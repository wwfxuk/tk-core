###############################
Registering a PublishedFile
###############################

At in its very simplest form this is all you need to do to register a publish file::

    import sgtk

    # get and instance of the sgtk api, we could also use sgtk.sgtk_from_path()
    tk = sgtk.sgtk_from_entity("Project",86)

    # generate a context object from the shotgun entity id that we want to publish to
    ctx = tk.context_from_entity('Task', 5785)

    # Get the path for the publish file. Normally we would use toolkit methods to generate this path
    # but for the sake of the simplicity of this example we have a hard coded path
    publish_path = "/projects/my_project/shots/seq_10/sh_020/editorial/publish/elements/image/v001/1920x1080/sh_020_image_main_v001.%04d.dpx"
    publish_name = "sh_020_image_main"
    version = 1

    # now register the publish
    sgtk.util.register_publish(tk, ctx, publish_path, publish_name, version)
