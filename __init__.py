# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
import os

from bpy.utils import previews
from bpy.types import Operator, Panel, PropertyGroup, WindowManager
from bpy.props import CollectionProperty, StringProperty, IntProperty

bl_info = {
    "name": "CodeMap",
    "blender": (2, 80, 0),
    "version": (1, 0, 0),
    "author": "Jithu",
    "location": "Text Editor > Sidebar",
    "description": "Provides a visual overview of your Python code structure in the Text Editor sidebar",
    "category": "Text Editor",
}

# ------------------------------


custom_icons = None


def load_icons():
    global custom_icons
    if custom_icons is None:
        custom_icons = previews.new()

    addon_dir = os.path.dirname(os.path.realpath(__file__))

    icons = {
        "class": os.path.join(addon_dir, "icons", "class.png"),
        "function": os.path.join(addon_dir, "icons", "function.png"),
        "property": os.path.join(addon_dir, "icons", "property.png"),
        "variable": os.path.join(addon_dir, "icons", "variable.png")
    }

    for icon_name, icon_path in icons.items():
        if icon_name not in custom_icons:
            custom_icons.load(icon_name, icon_path, 'IMAGE')


def unload_icons():
    global custom_icons
    if custom_icons:
        previews.remove(custom_icons)
        custom_icons = None


# ------------------------------


class CODE_MAP_OT_jump(Operator):
    bl_idname = "outliner.jump"
    bl_label = "Jump to Line"

    line_number: IntProperty()

    @classmethod
    def description(cls, context, properties):
        return "Jump to line {}".format(properties.line_number)

    def execute(self, context):
        bpy.ops.text.jump(line=self.line_number)
        return {'FINISHED'}


class CODE_MAP_OT_dynamic_toggle(Operator):
    bl_idname = "outliner.toggle_string"
    bl_label = "Show Functions"
    bl_description = "Toggle the display of the function"

    data_path: StringProperty()
    value: StringProperty()

    def execute(self, context):
        data_path = self.data_path.split(".")
        attr = data_path.pop()
        data = context

        for path in data_path:
            data = getattr(data, path)
        prop_collection = getattr(data, attr)

        for index, item in enumerate(prop_collection):
            if item.value == self.value:
                prop_collection.remove(index)
                break
        else:
            new_item = prop_collection.add()
            new_item.value = self.value

        return {'FINISHED'}


# ------------------------------


class CODE_MAP_PG_properties(PropertyGroup):
    value: StringProperty()


# ------------------------------


class DrawHelper:
    def draw(self, layout, context, text, wm):
        load_icons()
        # Draw the search box
        layout.prop(wm, "search", text="", icon="VIEWZOOM")

        if text is not None:
            class_name = None
            is_class_name = False
            inside_class = False

            # Check if there is a class in the current text block
            has_class = any(line.body.startswith("class ") for line in text.lines)

            for i, line in enumerate(text.lines):
                # Check if the search term is in the line
                search_in_line = wm.search.lower() in line.body.lower()

                # Check for class and def lines
                if line.body.startswith("class "):
                    class_name, base_class = self.parse_class_line(line.body)
                    has_methods = self.has_methods(text.lines[i + 1:], class_name)
                    is_class_name = any(item.value == class_name for item in wm.show_def_lines)

                    if self.is_match(wm.search, class_name, line, has_methods):
                        self.draw_class_row(layout, context, text, class_name, base_class,
                                            has_methods, is_class_name, i, wm)
                        inside_class = True  # Set to True when inside a class

                # Check for functions inside a class
                elif line.body.startswith("    def ") and is_class_name and search_in_line:
                    self.draw_class_function_row(layout, text, line.body, i, wm)

                # Check for property lines
                elif ": " in line.body and is_class_name and not line.body[4].isspace() and search_in_line:
                    self.draw_property_row(layout, text, line.body, i, wm)

                # Check for constant lines
                elif " = " in line.body and not line.body.startswith(" ") and search_in_line:
                    self.draw_variable_row(layout, text, line.body, i, has_class, wm)

                # Check for function lines
                elif line.body.startswith("def ") and search_in_line:
                    self.draw_function_row(layout, text, line.body, i, has_class, wm)

                # Check for properties and functions inside a class for wm.search
                elif wm.search.strip():
                    if ": " in line.body and not line.body[4].isspace() and search_in_line:
                        self.draw_property_row(layout, text, line.body, i, wm)

                    elif line.body.startswith("    def ") and search_in_line:
                        self.draw_class_function_row(layout, text, line.body, i, wm)

                # Reset inside_class when encountering a new class or function
                elif line.body.startswith("class ") or line.body.startswith("def "):
                    inside_class = False
        else:
            layout.active = False

    def parse_class_line(self, line):
        class_name = line.split("(")[0].replace("class ", "").strip().replace(":", "").strip()

        # Check if there is a base class specified
        if "(" in line and ")" in line:
            base_class = line.split("(")[1].split(")")[0].replace("bpy.types.", "").strip()
        else:
            base_class = None

        return class_name, base_class

    def has_methods(self, lines, class_name):
        for l in lines:
            if l.body.startswith("class "):
                break
            if l.body.startswith("    def ") or (
                    ": " in l.body and l.body.startswith("    ")):
                return True
        return False

    def is_match(self, search, class_name, line, has_methods):
        return search.lower() in class_name.lower() or (
            has_methods and search.lower() in line.body.lower())

    def truncate_text(self, text, max_length=37):
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def get_indentation(self, version):
        if version >= (3, 0, 0):
            return "            "
        else:
            return "    "


    def draw_variable_row(self, layout, text, line, i, has_class, wm):
        row = layout.row(align=True)
        row.alignment = 'LEFT'
        if has_class and not wm.search.strip():
            row.label(text="", icon="BLANK1")

        constant = line.split()[0]
        constant = self.truncate_text(constant)

        row.operator("outliner.jump", text=constant, icon_value=custom_icons["variable"].icon_id,
                     emboss=False).line_number = i + 1


    def draw_function_row(self, layout, text, line, i, has_class, wm):
        row = layout.row(align=True)
        row.alignment = 'LEFT'
        if has_class:
            row.label(text="", icon="BLANK1")

        # Get the first word from the line
        function = line.split(' ', 1)[1].split('(')[0]
        function = self.truncate_text(function)

        row.operator("outliner.jump", text=function, icon_value=custom_icons["function"].icon_id,
                     emboss=False).line_number = i + 1


    def draw_class_row(self, layout, context, text, class_name, base_class, has_methods, is_class_name, i, wm):
        row = layout.row(align=True)
        row.alignment = 'LEFT'

        sub = row.row()
        icon = 'BLANK1' if not has_methods else 'DOWNARROW_HLT' if is_class_name else 'RIGHTARROW'

        prop = sub.operator("outliner.toggle_string", text= "", icon = icon, emboss = False)
        prop.data_path = "window_manager.show_def_lines"
        prop.value = class_name

        row.operator("outliner.jump", text=class_name, icon_value=custom_icons["class"].icon_id,
                     emboss=False).line_number = i + 1


    def draw_property_row(self, layout, text, line, i, wm):
        # Check if the line contains quotes
        properties = [
            "BoolProperty", "BoolVectorProperty", "CollectionProperty",
            "EnumProperty", "FloatProperty", "FloatVectorProperty",
            "IntProperty", "IntVectorProperty", "PointerProperty",
            "StringProperty"
        ]

        if any(keyword in line for keyword in properties):
            row = layout.row(align=True)
            row.alignment = 'LEFT'
            row.label(text=self.get_indentation(bpy.app.version))

            variable = line.split()[0].split(':')[0]
            variable = self.truncate_text(variable)

            row.operator("outliner.jump", text=variable, icon_value=custom_icons["property"].icon_id,
                         emboss=False).line_number = i + 1


    def draw_class_function_row(self, layout, text, line, i, wm):
        row = layout.row(align=True)
        row.alignment = 'LEFT'
        row.label(text=self.get_indentation(bpy.app.version))

        method = line.split(' ', 1)[1].split('(')[0].replace("def ", "").strip()
        method = self.truncate_text(method)

        row.operator("outliner.jump", text=method, icon_value=custom_icons["function"].icon_id,
                     emboss=False).line_number = i + 1


# ------------------------------


class CODE_MAP_OT_popup(Operator):
    bl_idname = "outliner.popup"
    bl_label = "CodeMap"

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="CodeMap", icon="WORDWRAP_ON")

        text = bpy.context.space_data.text
        wm = context.window_manager

        draw_helper = DrawHelper()
        draw_helper.draw(layout, context, text, wm)


class CODE_MAP_PT_panel(Panel):
    bl_idname = "CODE_MAP_PT_panel"
    bl_label = "CodeMap"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Outliner"

    def draw(self, context):
        layout = self.layout

        text = bpy.context.space_data.text
        wm = context.window_manager

        draw_helper = DrawHelper()
        draw_helper.draw(layout, context, text, wm)


# ------------------------------


classes = [
    CODE_MAP_OT_jump,
    CODE_MAP_OT_dynamic_toggle,
    CODE_MAP_PG_properties,
    CODE_MAP_OT_popup,
    CODE_MAP_PT_panel,
]


addon_keymaps = []


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    WindowManager.show_def_lines = CollectionProperty(type=CODE_MAP_PG_properties)

    WindowManager.search = StringProperty(
        name="Search", description="Search for class, funcion, variable amd method")

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Text', space_type='TEXT_EDITOR')

        kmi = km.keymap_items.new(CODE_MAP_OT_popup.bl_idname, 'ACCENT_GRAVE', 'PRESS')
        addon_keymaps.append((km, kmi))


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del WindowManager.show_def_lines

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    unload_icons()


if __name__ == "__main__":
    register()
