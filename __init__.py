bl_info = {
    "name": "Export boolean modifiers to OpenSCAD",
    "author": "gandalf3",
    "location": "File > Export > OpenSCAD",
    "version": (0, 0, 4),
    "blender": (2, 80, 0),
    "description": "Export an object and its boolean modifiers to OpenSCAD",
    "doc_url": "https://github.com/gandalf3/io_export_openscad/blob/master/README.md",
    "tracker_url": "https://github.com/gandalf3/io_export_openscad/issues",
    "category": "Import-Export",
}

from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
from pathlib import Path
from typing import Callable
import bpy
import os

from textwrap import indent

indent_str = ' ' * 1

import logging
logger = logging.getLogger('export_openscad')
logging.basicConfig(level=logging.DEBUG)

def scad_filename(ob):
    # Seems openscad won't load files with more than one `.` in their name
    # but will load `sadf.fdas.stl` when given a name with underscores like `sadf_fdas.stl`.
    return ob.name.replace('.', '_') + ".stl"
    
def scad_for_object(ob, get_filename:Callable = lambda x: scad_filename(x)):
    
    scad = 'import("' + get_filename(ob) + '");'
    
    for mod in ob.modifiers:
        if mod.type == 'BOOLEAN':
            if not mod.object:
                continue
            if not mod.show_viewport:
                continue
            
            if mod.operation == 'DIFFERENCE':
                scad_op_str = "difference"
            elif mod.operation == 'UNION':
                scad_op_str = "union"
            elif mod.operation == 'INTERSECT':
                scad_op_str = "intersection"
            else:
                raise ValueError("Unknown boolean operation type: " + mod.operation)
            
            scad = scad_op_str + "() {\n" + indent(scad, indent_str) + "\n"
            scad += indent(scad_for_object(mod.object, get_filename), indent_str) + "\n"
            scad += "}"
    
    return scad

def bool_deps_for_object(ob):
    deps = set()
    deps.add(ob)
    
    for mod in ob.modifiers:
        if mod.type == 'BOOLEAN':
            if not mod.object or not mod.show_viewport:
                continue

            deps.update(bool_deps_for_object(mod.object))
            
    return deps
    
def print_scad_for_active_object():
    ob = bpy.context.active_object
    print(scad_for_object(ob))


def find_viewlayer_collection(collection_name):
    def _recurse(collection_name, cur_layer_col):
        if collection_name in cur_layer_col.children:
            return cur_layer_col.children[collection_name]

        for child_collection in cur_layer_col.children:
            return _recurse(collection_name, child_collection)

        return None

    return _recurse(collection_name, bpy.context.view_layer.layer_collection)
    

class ExportOpenSCAD(Operator, ExportHelper):
    """Export the active object (and its boolean modifiers) to OpenSCAD"""
    
    bl_idname = "export_scene.openscad"
    bl_label = "Export OpenSCAD"

    # ExportHelper mixin class uses this
    filename_ext = ""
    # We leave it set to an empty string as we want user to give name a directory, not a file.
    # e.g. if user says "bool_to_scad_compiler", we should generate the following file structure:
    #
    # bool_to_scad_compiler/
    # ├── bool_to_scad_compiler.scad
    # └── objects
    #     ├── Cube_001.stl
    #     ├── Cube_002.stl
    #     └── Cube.stl
    #

    def execute(self, context):
        ob = bpy.context.active_object
        
        if not ob:
            raise ValueError("No active object, abort")
            return {'CANCELLED'}
                
        old_selection = bpy.context.selected_objects
        
        export_dir = Path(self.filepath)
        obj_export_dir = export_dir / "objects"
        scad_export_path = export_dir / (str(export_dir.name) + ".scad")
        
        dep_objs = bool_deps_for_object(ob)
        
        # awkwardly append a trailing newline
        scad = scad_for_object(ob,
                               get_filename = lambda o: "objects" + os.sep + scad_filename(o)
                               ) + '\n'
        
        try:

            for obj in old_selection:
                obj.select_set(False)
                
            orig_modifiers = {}
            orig_layercollections = {}
            for obj in dep_objs:

                # If the object is only present in an excluded collection, we are
                # not allowed to select it and must un-exclude the collection first
                selectable = False
                for col in obj.users_collection:
                    laycol = find_viewlayer_collection(col.name)

                    if (laycol is not None):
                        if laycol.exclude:
                            orig_layercollections[laycol] = laycol.exclude
                            laycol.exclude = False
                            logger.debug("unexcluded collection '%s' in view layer '%s'" % (col.name, bpy.context.view_layer.name))

                        selectable = True
                        break

                if not selectable:
                    msg = "Required object '%s' is not selectable; perhaps it is not in any collection in the current view layer (%s)?" % (obj.name, bpy.context.view_layer.name)
                    logger.error(msg)
                    raise RuntimeError(msg)

                obj.select_set(True)

                disable_count = 0
                for mod in obj.modifiers:
                    if mod.type == 'BOOLEAN':
                        if mod.show_viewport:
                            orig_modifiers[mod] = True
                            mod.show_viewport = False
                            disable_count += 1

                logger.debug("object %s: disabled %s booleans" % (obj.name, disable_count))
                
                # create target directories at the last minute avoid altering
                # filesystem except in case of success
                export_dir.mkdir(exist_ok=True)
                obj_export_dir.mkdir(exist_ok=True)

                # stl export behavior depends on the presence of a trailing separator 
                bpy.ops.export_mesh.stl(filepath=str(obj_export_dir) + os.sep,
                                        batch_mode='OBJECT',
                                        use_selection=True,
                                        use_mesh_modifiers=True,
                                        check_existing=False)
                                    
                scad_export_path.write_text(scad)
            
        finally:
            for obj in dep_objs:
                obj.select_set(False)
            for obj in old_selection:
                obj.select_set(True)
            for laycol, orig_exclude in orig_layercollections.items():
                laycol.exclude = orig_exclude
            for mod, orig_visibility in orig_modifiers.items():
                mod.show_viewport = orig_visibility

        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportOpenSCAD.bl_idname, text="OpenSCAD (.scad)")


def register():
    bpy.utils.register_class(ExportOpenSCAD)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportOpenSCAD)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
    # test call
    bpy.ops.export_scene.openscad('INVOKE_DEFAULT')

