import numpy as np
import open3d as o3d

from copy import deepcopy

def draw_registration_result(registered, target,  transformation=np.identity(4, 4)):
    source_temp = deepcopy(registered)
    target_temp = deepcopy(target)
    source_temp.paint_uniform_color([1, 0.706, 0])
    target_temp.paint_uniform_color([0, 0.651, 0.929])
    source_temp.transform(transformation)
    o3d.visualization.draw_geometries([source_temp, target_temp])

