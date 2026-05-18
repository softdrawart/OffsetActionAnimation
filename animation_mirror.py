import bpy

bl_info = {
    "name": "Mirror Loop (Clean & Offset)",
    "author": "AI Assistant",
    "version": (1, 4),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Animation",
    "description": "Mirrors animation, clears old keys, and handles 0-15 style loops",
    "category": "Animation",
}

def get_mirror_name(name):
    if name.endswith(".L"): return name[:-2] + ".R"
    if name.endswith(".R"): return name[:-2] + ".L"
    if name.endswith("_L"): return name[:-2] + "_R"
    if name.endswith("_R"): return name[:-2] + "_L"
    return None

class ANIM_OT_MirrorLoopFinal(bpy.types.Operator):
    """Mirror animation: Clears target, handles offset, and syncs loop boundaries"""
    bl_idname = "anim.mirror_loop_final"
    bl_label = "Mirror & Sync Loop"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.animation_data or not obj.animation_data.action:
            self.report({'ERROR'}, "Active object must have an Animation Action")
            return {'CANCELLED'}

        scene = context.scene
        start_f = scene.frame_start
        end_f = scene.frame_end
        # Duration for a 0-15 playback is 16 frames. 
        # Loop wrap point is end_f + 1
        duration = (end_f - start_f) + 1
        loop_end_f = end_f + 1
        
        offset = context.window_manager.mirror_anim_offset
        selected_bones = context.selected_pose_bones
        original_frame = scene.frame_current
        action = obj.animation_data.action

        # 1. Identify Pairs
        bone_pairs = []
        for s_bone in selected_bones:
            m_name = get_mirror_name(s_bone.name)
            if m_name and m_name in obj.pose.bones:
                bone_pairs.append((s_bone, obj.pose.bones[m_name]))

        if not bone_pairs:
            self.report({'ERROR'}, "No mirrored counterparts found")
            return {'CANCELLED'}

        # 2. CLEAR EXISTING KEYS on target bones
        for _, target in bone_pairs:
            target_prefix = f'pose.bones["{target.name}"]'
            fcurves_to_remove = [fc for fc in action.fcurves if fc.data_path.startswith(target_prefix)]
            for fc in fcurves_to_remove:
                action.fcurves.remove(fc)

        # 3. Process Animation
        for source, target in bone_pairs:
            source_prefix = f'pose.bones["{source.name}"]'
            key_data = {}

            # Find all source keyframes within the range (and check loop-end frame)
            source_fcurves = [fc for fc in action.fcurves if fc.data_path.startswith(source_prefix)]
            for fc in source_fcurves:
                for kp in fc.keyframe_points:
                    f = int(kp.co.x)
                    # We look at start to loop_end (e.g., 0 to 16)
                    if start_f <= f <= loop_end_f:
                        if f not in key_data:
                            key_data[f] = {}
                        key_data[f][fc.data_path + str(fc.array_index)] = {
                            'interp': kp.interpolation,
                            'h_left': kp.handle_left_type,
                            'h_right': kp.handle_right_type
                        }

            # 4. Mirror and Apply
            mirrored_frames = [] # Store what we created to fix handles later

            # Also ensure we sample the start/loop_end if not already keyed
            check_frames = sorted(list(key_data.keys()))
            if start_f not in check_frames: check_frames.append(start_f)
            if loop_end_f not in check_frames: check_frames.append(loop_end_f)

            for f in check_frames:
                scene.frame_set(f)
                
                # Mirroring logic
                loc = source.location.copy()
                loc.x *= -1
                
                rot_q = source.rotation_quaternion.copy() if source.rotation_mode == 'QUATERNION' else None
                if rot_q:
                    rot_q.y *= -1
                    rot_q.z *= -1
                
                rot_e = source.rotation_euler.copy() if source.rotation_mode != 'QUATERNION' else None
                if rot_e:
                    rot_e.y *= -1
                    rot_e.z *= -1
                
                scale = source.scale.copy()

                # Offset math: ((f - start + offset) % 16) + 0
                target_f = ((f - start_f + offset) % duration) + start_f
                
                def set_keys(frame):
                    scene.frame_set(frame)
                    target.location = loc
                    if rot_q: target.rotation_quaternion = rot_q
                    if rot_e: target.rotation_euler = rot_e
                    target.scale = scale
                    target.keyframe_insert(data_path="location")
                    if rot_q: target.keyframe_insert(data_path="rotation_quaternion")
                    if rot_e: target.keyframe_insert(data_path="rotation_euler")
                    target.keyframe_insert(data_path="scale")
                    mirrored_frames.append((frame, f))

                set_keys(target_f)

                # SYNC BOUNDARIES: If it lands on 0, also key 16. If it lands on 16, also key 0.
                if int(target_f) == start_f:
                    set_keys(loop_end_f)
                elif int(target_f) == loop_end_f:
                    set_keys(start_f)

            # 5. Restore Handles/Interpolation
            target_fcurves = [fc for fc in action.fcurves if fc.data_path.startswith(f'pose.bones["{target.name}"]')]
            for fc in target_fcurves:
                source_path = fc.data_path.replace(target.name, source.name) + str(fc.array_index)
                for kp in fc.keyframe_points:
                    t_f = int(kp.co.x)
                    # Find which source frame this target frame originated from
                    orig_f = ((t_f - start_f - offset) % duration) + start_f
                    
                    if orig_f in key_data and source_path in key_data[orig_f]:
                        meta = key_data[orig_f][source_path]
                        kp.interpolation = meta['interp']
                        kp.handle_left_type = meta['h_left']
                        kp.handle_right_type = meta['h_right']

        scene.frame_set(original_frame)
        self.report({'INFO'}, f"Mirrored {len(bone_pairs)} bones. Target animation cleared.")
        return {'FINISHED'}

class VIEW3D_PT_MirrorAnimationPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'
    bl_label = "Loop Mirror Pro"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column(align=True)
        
        # Displaying real-time info
        col.label(text=f"Playback: {scene.frame_start} to {scene.frame_end}")
        col.label(text=f"Loop Wrap: {scene.frame_end + 1}")
        
        col.separator()
        col.prop(context.window_manager, "mirror_anim_offset", text="Frame Offset")
        col.operator("anim.mirror_loop_final", text="Mirror Selected (Clear Old)")

def register():
    bpy.utils.register_class(ANIM_OT_MirrorLoopFinal)
    bpy.utils.register_class(VIEW3D_PT_MirrorAnimationPanel)
    bpy.types.WindowManager.mirror_anim_offset = bpy.props.IntProperty(name="Offset", default=0)

def unregister():
    bpy.utils.unregister_class(ANIM_OT_MirrorLoopFinal)
    bpy.utils.unregister_class(VIEW3D_PT_MirrorAnimationPanel)
    del bpy.types.WindowManager.mirror_anim_offset

if __name__ == "__main__":
    register()