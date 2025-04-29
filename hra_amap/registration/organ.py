import yaml
import trimesh
import numpy as np
from pathlib import Path

from hra_amap.registration.dataclass import Transform
from hra_amap.utils.io import load
from hra_amap.utils.metrics import get_translations, scaling, rotation
from hra_amap.utils.conversions import to_array, to_pointcloud

class Organ(trimesh.Trimesh):
    
    def __init__(self, path: str, target_name : str, metadata: dict = None) -> None:
        super(Organ, self).__init__()
        self.metadata = metadata
        self.path = Path(path) 
        self.target_name = target_name
        self.name = self.path.stem
        self.file_type = self.path.suffix if self.path.suffix else '.glb'

        self.faces, self.vertices = load(self.path, self.file_type)
        self.target_transform = None

    @property
    def pointcloud(self):
        return to_pointcloud(self)

    @property
    def array(self):
        return to_array(self)

    def _get_transform(self):
        """Get the necessary transform shift the target HRA organ (it's back-bottom-left) to the world origin (0, 0, 0)"""
        translation_list = get_translations(self.target_name)

        target_transform = Transform(scaling, 
                                     rotation, 
                                     np.array(translation_list))
        return target_transform
    