bl_info = {
    "name": "Export boolean modifiers to OpenSCAD",
    "author": "gandalf3",
    "location": "File > Export > OpenSCAD",
    "version": (0, 0, 2),
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

indent_str = ' ' * 3

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
        
        export_dir.mkdir(exist_ok=True)
        obj_export_dir.mkdir(exist_ok=True)
        
        dep_objs = bool_deps_for_object(ob)
        
        # awkwardly append a trailing newline
        scad = scad_for_object(ob,
                               get_filename = lambda o: "objects" + os.sep + scad_filename(o)) + '\n'
        
        for obj in old_selection:
            obj.select_set(False)
            
        orig_modifiers = {}
        for obj in dep_objs:
            obj.select_set(True)

        try:
            
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

