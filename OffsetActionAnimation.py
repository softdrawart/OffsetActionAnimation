bl_info = {
    "name": "Action Animation",
    "author": "Egor Ilyin",
    "version": (1, 1, 0),
    "blender": (4, 2, 9),
    "location": "VIEW 3D > UI",
    "description": "copy animation to other objects",
    "doc_url": "",
    "category": "Animation",
}


import bpy
from mathutils import Vector
import mathutils

            
class MyParam(bpy.types.PropertyGroup):
    OffsetFrame : bpy.props.IntProperty(name = "Offset Frame", default = 1, description = "Offset of copied keyframes")
    Loc : bpy.props.BoolProperty(name = "Loc", default = True, description = "Location chanels")
    Rot : bpy.props.BoolProperty(name = "Rot", default = True, description = "Rotation chanels")
    Sc : bpy.props.BoolProperty(name = "Sc", default = True, description = "Scale chanels")
    Loop : bpy.props.BoolProperty(name = "Loop", default = False, description = "loop animation after end keyframe")
    Current : bpy.props.BoolProperty(name = "Current", default = False, description = "copy keyframes at current coordinates")
    Mirror : bpy.props.BoolProperty(name = "Mirror", default = False, description = "bone animation symmetry x")

def distance_vec(point1: Vector, point2: Vector) -> float:
    return (point2 - point1).length

class CopyAction(bpy.types.Operator):
    bl_idname = 'object.offset_action'
    bl_label = 'Copy keyframes'
    bl_description = 'Copy keyframes'
        
    @classmethod
    def poll(cls, context):
        mode = bpy.context.mode
        props = context.scene.param
        if props.Loc == False and props.Rot == False and props.Sc == False:
            return False
        if(mode == 'OBJECT'):
            if len(context.selected_objects) <= 1:
                return False 
        if(mode == 'POSE'):
            if len(context.selected_pose_bones) <= 1:
                return False
        return True
    def transfer_fcurve(self, source_fcurve: bpy.types.FCurve, target_fcurve: bpy.types.FCurve, current: bool = False, mirror: bool = False, offset: int = 0, loop: bool = False):
        """
        Copy all keyframes and their handles from one FCurve to another.

        Parameters:
            source_fcurve (FCurve): The curve to copy from.
            target_fcurve (FCurve): The curve to copy into.
            current (bool): If True, offset values based on the difference at frame 0.
            mirror (bool): If True, invert values (Y axis) and handles.
            offset (int): Frame offset for inserted keys.
            loop (bool): If True, inserts a loop frame at frame_end+1 and copies it to frame_start.
        """
        if source_fcurve is None or target_fcurve is None:
            print("One of the FCurves is None")
            return

        scene = bpy.context.scene
        frame_start = scene.frame_start
        frame_end = scene.frame_end
        loop_frame = frame_end + 1

        # Compute value offset if 'current' is enabled
        delta = 0.0
        if current:
            delta = source_fcurve.evaluate(0) - target_fcurve.evaluate(0)

        # Remove existing keyframes in target
        target_fcurve.keyframe_points.clear()

        # Transfer keyframes
        for k_src in source_fcurve.keyframe_points:
            # Compute frame and value
            frame = k_src.co[0] + offset
            value = k_src.co[1] - delta if current else k_src.co[1]
            if mirror:
                value *= -1

            # Insert keyframe
            k_new = target_fcurve.keyframe_points.insert(frame, value)

            # Copy handle types
            k_new.handle_left_type = k_src.handle_left_type
            k_new.handle_right_type = k_src.handle_right_type

            # Copy and adjust handles
            h_l_x = k_src.handle_left[0] + offset
            h_l_y = k_src.handle_left[1] - delta if current else k_src.handle_left[1]
            h_r_x = k_src.handle_right[0] + offset
            h_r_y = k_src.handle_right[1] - delta if current else k_src.handle_right[1]

            if mirror:
                h_l_y *= -1
                h_r_y *= -1

            k_new.handle_left = (h_l_x, h_l_y)
            k_new.handle_right = (h_r_x, h_r_y)

        # Handle looping
        if loop:
            # Add Cycles modifier if missing
            if not any(mod.type == 'CYCLES' for mod in target_fcurve.modifiers):
                target_fcurve.modifiers.new(type='CYCLES')

            # Insert loop keyframe at frame_end + 1
            #loop_val = source_fcurve.evaluate(loop_frame) - delta if current else source_fcurve.evaluate(loop_frame)
            #if mirror:
            #    loop_val *= -1
            #loop_k = target_fcurve.keyframe_points.insert(loop_frame, loop_val)
            loop_val = target_fcurve.evaluate(loop_frame)
            target_fcurve.keyframe_points.insert(loop_frame, loop_val)

            temp_keys = [
                {
                    "frame": kp.co[0],
                    "value": kp.co[1],
                    "interp": kp.interpolation,
                    "hl_type": kp.handle_left_type,
                    "hr_type": kp.handle_right_type,
                    "hl": kp.handle_left[:],
                    "hr": kp.handle_right[:]
                }
                for kp in target_fcurve.keyframe_points
                if kp.co[0] >= loop_frame
            ]
            for key in temp_keys:
                new_frame = key["frame"] - loop_frame + frame_start
                new_val = key["value"]

                copy_k = target_fcurve.keyframe_points.insert(new_frame, new_val)
                copy_k.interpolation = key["interp"]
                copy_k.handle_left_type = key["hl_type"]
                copy_k.handle_right_type = key["hr_type"]
                copy_k.handle_left = (key["hl"][0] - loop_frame + frame_start, key["hl"][1])
                copy_k.handle_right = (key["hr"][0] - loop_frame + frame_start, key["hr"][1])

            # Delete keyframes with frame > loop_frame
            to_remove_indices = [i for i, kp in enumerate(target_fcurve.keyframe_points) if kp.co[0] > loop_frame]

            # Remove from end to start to avoid shifting indices
            for i in reversed(to_remove_indices):
                target_fcurve.keyframe_points.remove(target_fcurve.keyframe_points[i])

        # Ensure the FCurve updates
        target_fcurve.update()
        bpy.context.view_layer.update()
        for area in bpy.context.screen.areas:
            if area.type in {'GRAPH_EDITOR', 'DOPESHEET_EDITOR'}:
                area.tag_redraw()

    def copyChannels(self, OtherObj, CurObj, Path: str, rangeLoop: int, LocalOffset: int, Mirror = '', Current = False, Loop = False):
        # copy fcurves of specified path from current to other object
        mode = self.mode

        if(mode == 'OBJECT'):
            if OtherObj.animation_data is None or OtherObj.animation_data.action is None:
                OtherObj.animation_data_create()
                newAction = bpy.data.actions.new(f"{OtherObj.name}_OffsetAction")
                OtherObj.animation_data.action = newAction               
        OtherObj.keyframe_insert(data_path = Path, frame = 0, group= f"{OtherObj.name}")
        
        for i in range(rangeLoop): # XYZ or WXYZ
            CurFcurve = None
            OtherFcurve = None 
            if(mode == 'OBJECT'):
                CurFcurve = CurObj.animation_data.action.fcurves.find(data_path = Path, index = i)       
                OtherFcurve = OtherObj.animation_data.action.fcurves.find(data_path = Path, index = i)                        
            if(mode == 'POSE'):
                CurArmat = CurObj.id_data #gets bone Armature object
                CurFcurve = CurArmat.animation_data.action.fcurves.find(data_path = f'pose.bones["{CurObj.name}"].{Path}', index = i)
                OtherFcurve = CurArmat.animation_data.action.fcurves.find(data_path = f'pose.bones["{OtherObj.name}"].{Path}', index = i) 
            if CurFcurve == None:
                continue
            OtherFValue = OtherFcurve.evaluate(0)       
            CurFValue = CurFcurve.evaluate(0)

            # remove all keyframes from otherFcurve
            for p in range(len(OtherFcurve.keyframe_points) ):  
                OtherFcurve.keyframe_points.remove(OtherFcurve.keyframe_points[0])

            # add all keyframes of current channel to other channel
            indices = []
            match rangeLoop:
                case 3:
                    indices = [i for i, c in enumerate('XYZ') if c in Mirror]
                case 4:
                    indices = [i for i, c in enumerate('WXYZ') if c in Mirror]
            self.transfer_fcurve(CurFcurve, OtherFcurve, current=Current, mirror=(Mirror if i in indices else False), offset=LocalOffset, loop=Loop)

    def execute(self, context):
        props = context.scene.param
        CurObj = None
        self.mode = mode = bpy.context.mode

        if(mode == 'OBJECT'):
            CurObj = bpy.context.active_object
            SelectedObj = [o for o in bpy.context.selected_objects if not (o == CurObj)]
        if(mode == 'POSE'):
            CurArmat = bpy.context.active_object
            CurObj = bpy.context.active_object.pose.bones[bpy.context.active_bone.name]
            GlobalCurPos = CurArmat.matrix_world @ CurObj.matrix @ CurObj.location
            SelectedObj = [b for b in bpy.context.selected_pose_bones if not (b.name == bpy.context.active_bone.name)]    
        
        #RangeLRS = self.findLRS(context)
        if not CurObj or not SelectedObj:
            print("error")
            return {'CANCELLED'}

        DistObj = []
        for obj in SelectedObj:
            if(mode == 'OBJECT'):
                dist = distance_vec(obj.location, CurObj.location)
            if(mode == 'POSE'):
                globalObj = CurArmat.matrix_world @ obj.matrix @ obj.location
                dist = distance_vec(globalObj, GlobalCurPos) 
            DistObj.append(dist)

        ObjDistData = dict(zip(SelectedObj, DistObj))
        sortedByDist = sorted(ObjDistData.items(), key=lambda item: item[1])
        SortObj = {i[0]: i[1] for i in sortedByDist}

        LocalOffset = 0
        Path: str
        #run through selected objects or bones copy keys 
        for obj in SortObj.keys():  
            LocalOffset += props.OffsetFrame
            OtherObj = obj
            rangeLoop = 3 #default 3 channels XYZ

            #define wich path to copy
            if props.Loc:
                rangeLoop = 3
                Path = "location"
                self.copyChannels(OtherObj, CurObj, Path, rangeLoop, LocalOffset, Mirror='X' if props.Mirror else '', Current=props.Current, Loop=props.Loop)
            if props.Rot:
                if CurObj.rotation_mode in ['XYZ', 'XZY', 'YXZ', 'ZXY', 'YZX']:
                    rangeLoop = 3
                    Path = "rotation_euler"
                else:
                    rangeLoop = 4
                    Path = "rotation_quaternion"
                self.copyChannels(OtherObj, CurObj, Path, rangeLoop, LocalOffset, Mirror='YZ' if props.Mirror else '', Current=props.Current, Loop=props.Loop)
            if props.Sc:
                rangeLoop = 3
                Path = "scale"
                self.copyChannels(OtherObj, CurObj, Path, rangeLoop, LocalOffset, Mirror='', Current=props.Current, Loop=props.Loop)
            
            return{'FINISHED'}                    

class UIPanel(bpy.types.Panel):
    bl_label = "Action Animation"
    bl_idname = "OBJECT_PT_TestPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
#    bl_context = "object"
    bl_category = "Animation"

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        props = context.scene.param
        col = layout.column(align=False)
        col.prop( props, "OffsetFrame")
        ro2 = col.row( align = True)
        ro2.prop( props, "Loop")
        ro2.prop(props, "Current")
        ro2.prop(props, "Mirror") 
        box1 = col.box()
        ro = box1.row ( align = True)
        
        ro.prop( props, "Loc")
        ro.prop( props, "Rot")
        ro.prop( props, "Sc")
        col1 = layout.row()
        col1.operator("object.offset_action")

def register():
    bpy.utils.register_class(MyParam)
    bpy.utils.register_class(UIPanel)
    bpy.utils.register_class(CopyAction)
    bpy.types.Scene.param = bpy.props.PointerProperty(type = MyParam)
    
def unregister():
    bpy.utils.unregister_class(UIPanel)
    bpy.utils.unregister_class(CopyAction)
    bpy.utils.unregister_class(MyParam)
    del bpy.types.Scene.param


if __name__ == "__main__":
    register()        