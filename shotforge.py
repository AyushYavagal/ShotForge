bl_info = {
    "name": "ShotForge",
    "author": "Ayush Yavagal",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > ShotForge",
    "description": "Turns a shot list into cameras and timeline markers.",
    "category": "Animation",
}

import bpy
from mathutils import Vector


class ShotForgeShot(bpy.types.PropertyGroup):
    shot_name: bpy.props.StringProperty(
        name="Shot Name",
        default="Shot"
    )

    shot_type: bpy.props.EnumProperty(
        name="Shot Type",
        items=[
            ("WIDE", "Wide", ""),
            ("MEDIUM", "Medium", ""),
            ("CLOSEUP", "Close-Up", ""),
            ("OTS", "Over Shoulder", ""),
        ],
        default="MEDIUM"
    )

    duration: bpy.props.IntProperty(
        name="Duration",
        default=60,
        min=1
    )

    subject: bpy.props.PointerProperty(
        name="Subject",
        type=bpy.types.Object
    )


class SHOTFORGE_OT_add_shot(bpy.types.Operator):
    bl_idname = "shotforge.add_shot"
    bl_label = "Add Shot"

    def execute(self, context):
        scene = context.scene

        shot = scene.shotforge_shots.add()

        shot.shot_name = f"Shot_{len(scene.shotforge_shots):02d}"
        shot.shot_type = scene.shotforge_new_shot_type
        shot.duration = scene.shotforge_new_duration
        shot.subject = scene.shotforge_new_subject

        scene.shotforge_active_index = len(scene.shotforge_shots) - 1

        return {"FINISHED"}


class SHOTFORGE_OT_remove_shot(bpy.types.Operator):
    bl_idname = "shotforge.remove_shot"
    bl_label = "Remove Shot"

    def execute(self, context):
        scene = context.scene
        index = scene.shotforge_active_index

        if len(scene.shotforge_shots) == 0:
            return {"CANCELLED"}

        scene.shotforge_shots.remove(index)

        if len(scene.shotforge_shots) == 0:
            scene.shotforge_active_index = 0
        else:
            scene.shotforge_active_index = min(index, len(scene.shotforge_shots) - 1)

        return {"FINISHED"}


class SHOTFORGE_OT_set_subject_from_selection(bpy.types.Operator):
    bl_idname = "shotforge.set_subject_from_selection"
    bl_label = "Set Subject From Selection"

    def execute(self, context):
        scene = context.scene
        obj = context.object

        if obj is None:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        scene.shotforge_new_subject = obj

        self.report({"INFO"}, f"New shot subject set to {obj.name}")
        return {"FINISHED"}


class SHOTFORGE_UL_shot_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        name_col = row.column()
        name_col.scale_x = 1.3
        name_col.prop(item, "shot_name", text="")

        type_col = row.column()
        type_col.scale_x = 1.2
        type_col.prop(item, "shot_type", text="")

        duration_col = row.column()
        duration_col.scale_x = 0.7
        duration_col.prop(item, "duration", text="")

        subject_col = row.column()
        subject_col.scale_x = 1.8
        subject_col.prop(item, "subject", text="")


def create_camera(name, location, target=None):
    camera_data = bpy.data.cameras.new(name + "_Data")
    camera_obj = bpy.data.objects.new(name, camera_data)

    camera_obj["shotforge_generated"] = True

    bpy.context.scene.collection.objects.link(camera_obj)

    camera_obj.location = location

    if target is not None:
        direction = target.location - camera_obj.location
        camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        camera_data.dof.use_dof = True
        camera_data.dof.focus_object = target

    else:
        target_location = Vector((0, 0, 1))
        direction = target_location - camera_obj.location
        camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    return camera_obj


def get_camera_location(shot_type):
    if shot_type == "WIDE":
        return (0, -8, 3)

    if shot_type == "MEDIUM":
        return (0, -5, 2)

    if shot_type == "CLOSEUP":
        return (0, -3, 1.7)

    if shot_type == "OTS":
        return (1.5, -4, 1.8)

    return (0, -5, 2)


def clear_generated_storyboard():
    scene = bpy.context.scene

    markers_to_remove = [
        marker for marker in scene.timeline_markers
        if marker.get("shotforge_generated") == True
    ]

    for marker in markers_to_remove:
        scene.timeline_markers.remove(marker)

    cameras_to_remove = [
        obj for obj in bpy.data.objects
        if obj.get("shotforge_generated") == True
    ]

    for obj in cameras_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)


class SHOTFORGE_OT_generate_storyboard(bpy.types.Operator):
    bl_idname = "shotforge.generate_storyboard"
    bl_label = "Update Storyboard"

    def execute(self, context):
        scene = context.scene

        if len(scene.shotforge_shots) == 0:
            self.report({"WARNING"}, "No shots added")
            return {"CANCELLED"}

        clear_generated_storyboard()

        current_frame = 1
        scene.frame_start = 1

        for shot in scene.shotforge_shots:
            safe_shot_name = shot.shot_name.replace(" ", "_")
            camera_name = "CAM_" + safe_shot_name + "_" + shot.shot_type
            location = get_camera_location(shot.shot_type)

            camera = create_camera(camera_name, location, shot.subject)

            marker = scene.timeline_markers.new(shot.shot_name, frame=current_frame)
            marker.camera = camera
            marker["shotforge_generated"] = True

            current_frame += shot.duration

        scene.frame_end = current_frame - 1

        self.report({"INFO"}, "Storyboard updated")
        return {"FINISHED"}


class SHOTFORGE_OT_clear_shots(bpy.types.Operator):
    bl_idname = "shotforge.clear_shots"
    bl_label = "Clear Shot List"

    def execute(self, context):
        scene = context.scene

        scene.shotforge_shots.clear()
        scene.shotforge_active_index = 0

        clear_generated_storyboard()

        return {"FINISHED"}


class SHOTFORGE_PT_main_panel(bpy.types.Panel):
    bl_label = "ShotForge"
    bl_idname = "SHOTFORGE_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ShotForge"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="New Shot")

        layout.prop(scene, "shotforge_new_shot_type")
        layout.prop(scene, "shotforge_new_duration")
        layout.prop(scene, "shotforge_new_subject")
        layout.operator("shotforge.set_subject_from_selection", text="Set Subject From Selection")

        layout.separator()

        layout.operator("shotforge.add_shot", text="Add Shot")
        layout.operator("shotforge.remove_shot", text="Remove Selected Shot")

        layout.separator()

        layout.label(text="Shot List")

        header = layout.row(align=True)

        name_col = header.column()
        name_col.scale_x = 1.3
        name_col.label(text="Shot")

        type_col = header.column()
        type_col.scale_x = 1.2
        type_col.label(text="Type")

        duration_col = header.column()
        duration_col.scale_x = 0.7
        duration_col.label(text="Len")

        subject_col = header.column()
        subject_col.scale_x = 1.8
        subject_col.label(text="Subject")

        layout.template_list(
            "SHOTFORGE_UL_shot_list",
            "",
            scene,
            "shotforge_shots",
            scene,
            "shotforge_active_index",
            rows=5
        )

        layout.separator()

        layout.operator("shotforge.generate_storyboard", text="Update Storyboard")
        layout.operator("shotforge.clear_shots", text="Clear Shot List")


classes = [
    ShotForgeShot,
    SHOTFORGE_OT_add_shot,
    SHOTFORGE_OT_remove_shot,
    SHOTFORGE_OT_set_subject_from_selection,
    SHOTFORGE_UL_shot_list,
    SHOTFORGE_OT_generate_storyboard,
    SHOTFORGE_OT_clear_shots,
    SHOTFORGE_PT_main_panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.shotforge_shots = bpy.props.CollectionProperty(
        type=ShotForgeShot
    )

    bpy.types.Scene.shotforge_active_index = bpy.props.IntProperty(
        default=0
    )

    bpy.types.Scene.shotforge_new_shot_type = bpy.props.EnumProperty(
        name="Shot Type",
        items=[
            ("WIDE", "Wide", ""),
            ("MEDIUM", "Medium", ""),
            ("CLOSEUP", "Close-Up", ""),
            ("OTS", "Over Shoulder", ""),
        ],
        default="MEDIUM"
    )

    bpy.types.Scene.shotforge_new_duration = bpy.props.IntProperty(
        name="Duration",
        default=60,
        min=1
    )

    bpy.types.Scene.shotforge_new_subject = bpy.props.PointerProperty(
        name="Subject",
        type=bpy.types.Object
    )


def unregister():
    del bpy.types.Scene.shotforge_shots
    del bpy.types.Scene.shotforge_active_index
    del bpy.types.Scene.shotforge_new_shot_type
    del bpy.types.Scene.shotforge_new_duration
    del bpy.types.Scene.shotforge_new_subject

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()