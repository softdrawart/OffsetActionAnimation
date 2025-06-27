bl_info = {
    "name": "Action Animation",
    "author": "Egor Ilyin",
    "version": (1, 0, 0),
    "blender": (3, 4, 1),
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
    print(point1, point2) 
    return (point2 - point1).length


class CopyAction(bpy.types.Operator):
    bl_idname = 'object.offset_action'
    bl_label = 'Copy keyframes'
    bl_description = 'Copy keyframes'
        
    @classmethod
    def poll(cls, context):
        props = context.object.param
        if props.Loc == False and props.Rot == False and props.Sc == False:
            return False
        if(bpy.context.mode == 'OBJECT'):
            if len(context.selected_objects) <= 1:
                return False 
        if(bpy.context.mode == 'POSE'):
            if len(context.selected_pose_bones) <= 1:
                return False
        return True
        
    def action(self,context):     
        props = context.object.param
        CurObj = None           
        if(bpy.context.mode == 'OBJECT'):
            CurObj = bpy.context.active_object
        if(bpy.context.mode == 'POSE'):
            CurArmat = bpy.context.active_object
            activBone = bpy.context.active_bone
            CurObj = bpy.context.active_object.pose.bones[activBone.name]
            GlobalCurPos = CurArmat.matrix_world @ CurObj.matrix @ CurObj.location      
        RangeLRS =[0]*3
        LRS = [props.Loc, props.Rot, props.Sc ]
        match LRS:
            case [True,False,False]:
                RangeLRS = [0,1,1]
            case [False,True,False]:
                RangeLRS = [1,2,1]
            case [False,False,True]:
                RangeLRS = [2,3,1]
            case [True,True,True]:
                RangeLRS = [0,3,1]
            case [True,True,False]:
                RangeLRS = [0,2,1]
            case [False,True,True]:
                RangeLRS = [1,3,1]
            case [True,False,True]:
                RangeLRS = [0,3,2]
            case _:
                print("loh")

        SelectedObj = []
        if(bpy.context.mode == 'OBJECT'):
            SelectedObj = [o for o in bpy.context.selected_objects if not (o == CurObj)]
        if(bpy.context.mode == 'POSE'):
            SelectedObj = [b for b in bpy.context.selected_pose_bones if not (b.name == bpy.context.active_bone.name)]
        DistObj = []
        for obj in SelectedObj:
            if(bpy.context.mode == 'OBJECT'):
                dist = distance_vec(obj.location, CurObj.location) #тут
            if(bpy.context.mode == 'POSE'):
                globalObj = CurArmat.matrix_world @ obj.matrix @ obj.location
                dist = distance_vec(globalObj, GlobalCurPos) 
            DistObj.append(dist)

        ObjDistData = dict(zip(SelectedObj, DistObj))
        sortedByDist = sorted(ObjDistData.items(), key=lambda item: item[1])
        SortObj = {i[0]: i[1] for i in sortedByDist}

        LocalOffset = 0
        Path: str
        for obj in SortObj.keys():  
            LocalOffset += props.OffsetFrame
            OtherObj = obj
            for a in range(RangeLRS[0],RangeLRS[1],RangeLRS[2]):
                rangeLoop = 3
                
                if a == 0:
                    Path = "location"
                if a == 1:
                    if(bpy.context.mode == 'OBJECT'):
                        Path = "rotation_euler"
                    if(bpy.context.mode == 'POSE'):
                        rangeLoop = 4
                        Path = "rotation_quaternion"
                if a == 2:
                        Path = "scale"

                # вставка первого кадра для получения каналов
                if(bpy.context.mode == 'OBJECT'):
                    if OtherObj.animation_data is None or OtherObj.animation_data.action is None:
                        OtherObj.animation_data_create()
                        newAction = bpy.data.actions.new(f"{OtherObj.name}_OffsetAction")
                        OtherObj.animation_data.action = newAction               
                OtherObj.keyframe_insert(data_path = Path, frame = 0, group= f"{OtherObj.name}")
                
                for i in range(rangeLoop): # XYZ or WXYZ
                    
                    CurFcurve = None
                    OtherFcurve = None 
                    if(bpy.context.mode == 'OBJECT'):
                        CurFcurve = CurObj.animation_data.action.fcurves.find(data_path = Path, index = i)       
                        OtherFcurve = OtherObj.animation_data.action.fcurves.find(data_path = Path, index = i)                        
                    if(bpy.context.mode == 'POSE'):
                        CurFcurve = CurArmat.animation_data.action.fcurves.find(data_path = f'pose.bones["{CurObj.name}"].{Path}', index = i)
                        OtherFcurve = CurArmat.animation_data.action.fcurves.find(data_path = f'pose.bones["{OtherObj.name}"].{Path}', index = i) 
                    if CurFcurve == None:
                        continue
                    OtherFValue = OtherFcurve.evaluate(0)       
                    CurFValue = CurFcurve.evaluate(0)

                    # удаление кейфрэймов
                    for p in range(len(OtherFcurve.keyframe_points) ):  
                        OtherFcurve.keyframe_points.remove(OtherFcurve.keyframe_points[0])

                    # вставка кейфрэймов 
                    for k in CurFcurve.keyframe_points : 
                        if props.Current:
                            OtherFcurve.keyframe_points.insert(k.co[0] + LocalOffset,  k.co[1] - ( CurFValue - OtherFValue) )
                        else:
                            OtherFcurve.keyframe_points.insert(k.co[0] + LocalOffset,  k.co[1] ) 
                        
                    # перенос хэндлеров                    
                    for k in range(len(OtherFcurve.keyframe_points) ):
                        OtherFcurve.keyframe_points[k].handle_left_type = CurFcurve.keyframe_points[k].handle_left_type
                        OtherFcurve.keyframe_points[k].handle_left[0] =  CurFcurve.keyframe_points[k].handle_left[0] + LocalOffset 
                        OtherFcurve.keyframe_points[k].handle_left[1] =  CurFcurve.keyframe_points[k].handle_left[1] - (CurFcurve.keyframe_points[k].co[1]- OtherFcurve.keyframe_points[k].co[1])
                        OtherFcurve.keyframe_points[k].handle_right_type =  CurFcurve.keyframe_points[k].handle_right_type
                        OtherFcurve.keyframe_points[k].handle_right[0] =  CurFcurve.keyframe_points[k].handle_right[0] + LocalOffset
                        OtherFcurve.keyframe_points[k].handle_right[1] =  CurFcurve.keyframe_points[k].handle_right[1] - (CurFcurve.keyframe_points[k].co[1]- OtherFcurve.keyframe_points[k].co[1]) 
                        

                    # вставка кадра в конец цикла если нужен цикл
                    if props.Loop == True: 
                        endTL = bpy.context.scene.frame_end+1 
                        startTL = bpy.context.scene.frame_start 
                        curTL = bpy.context.scene.frame_current
                        
                        OtherFcurve.modifiers.new(type='CYCLES')
                        bpy.context.scene.frame_set(endTL)
                        if Path == "location":
                            OtherFcurve.keyframe_points.insert(endTL, obj.location[i])
                        if Path == "rotation_euler":
                            OtherFcurve.keyframe_points.insert(endTL, obj.rotation_euler[i])
                        if Path == "rotation_quaternion":
                            OtherFcurve.keyframe_points.insert(endTL, obj.rotation_quaternion[i])
                        if Path == "scale":
                            OtherFcurve.keyframe_points.insert(endTL, obj.scale[i])
                        
                        curIndex = -1
                        for c in range(len(OtherFcurve.keyframe_points) ): 
                            if OtherFcurve.keyframe_points[c].co[0] == endTL:
                                curIndex = c
                        bpy.context.scene.frame_set(curTL)  
                        
                        # перенос кадров на начало таймлайна
                        lenKey = len(OtherFcurve.keyframe_points)
                        tempFrame = []
                        for x in range(curIndex, lenKey ): 
                           tempFrame.append(OtherFcurve.keyframe_points[x])

                        for x in range(0,len(tempFrame)) :
                            OtherFcurve.keyframe_points.insert(tempFrame[x].co[0]- endTL + startTL, tempFrame[x].co[1]) 
                            
                        for x in range(0,len(tempFrame)) :   
                            OtherFcurve.keyframe_points[x].handle_left_type = tempFrame[x].handle_left_type
                            OtherFcurve.keyframe_points[x].handle_left[0] =  tempFrame[x].handle_left[0]- endTL + startTL 
                            OtherFcurve.keyframe_points[x].handle_left[1] =  tempFrame[x].handle_left[1] 
                            
                            if x > 0:
                                OtherFcurve.keyframe_points[x].handle_right_type =  tempFrame[x].handle_right_type
                                OtherFcurve.keyframe_points[x].handle_right[0] =  tempFrame[x].handle_right[0]- endTL + startTL 
                                OtherFcurve.keyframe_points[x].handle_right[1] =  tempFrame[x].handle_right[1] 

                        # удаление кадров после конца цикла    
                        countFcut = lenKey-curIndex
                        newEndF = len(OtherFcurve.keyframe_points) - countFcut + 1
                        for y in range(countFcut -1):  
                            OtherFcurve.keyframe_points.remove(OtherFcurve.keyframe_points[newEndF])

                    else:
                        for m in OtherFcurve.modifiers:
                            if (m.type == 'CYCLES'): 
                                OtherFcurve.modifiers.remove(m)
                    
                    # Симметрия анимации по иксу если нужно
                    if props.Mirror == True: 
                        if(bpy.context.mode == 'POSE'):
                            if OtherFcurve.data_path.endswith("location") and i == 0 :
                                for c in range(len(OtherFcurve.keyframe_points)):
                                    OtherFcurve.keyframe_points[c].co[1] *= -1
                                    OtherFcurve.keyframe_points[c].handle_left[1] *=-1
                                    OtherFcurve.keyframe_points[c].handle_right[1]*=-1
                                        
                            if OtherFcurve.data_path.endswith("rotation_quaternion"):
                                if i == 2 or i == 3:
                                    for c in range(len(OtherFcurve.keyframe_points)):
                                        OtherFcurve.keyframe_points[c].co[1] *= -1 
                                        OtherFcurve.keyframe_points[c].handle_left[1] *=-1
                                        OtherFcurve.keyframe_points[c].handle_right[1]*=-1
    
    def execute(self,context)-> set:
        self.action(context)
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
        props = context.object.param
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
    bpy.types.Object.param = bpy.props.PointerProperty(type = MyParam)
    
def unregister():
    bpy.utils.unregister_class(UIPanel)
    bpy.utils.unregister_class(CopyAction)
    bpy.utils.unregister_class(MyParam)
    del bpy.types.Object.param


if __name__ == "__main__":
    register()        