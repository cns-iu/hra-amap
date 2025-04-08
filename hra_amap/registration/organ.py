import yaml
import trimesh
import numpy as np

from pathlib import Path

from hra_amap.registration.dataclass import Transform
from hra_amap.utils.io import load, read_yaml
from hra_amap.utils.conversions import to_array, to_pointcloud

class Organ(trimesh.Trimesh):
    def __init__(self, path: str, mapping_path, transform_path, metadata: dict = None) -> None:
        super(Organ, self).__init__()
        self.path = Path(path)
        self.name = self.path.stem
        self.file_type = self.path.suffix if self.path.suffix else '.glb'
        self.mappings = read_yaml(mapping_path)
        self.hra_transforms = read_yaml(transform_path)
        if metadata:
            self.metadata = metadata
        if self.name in self.mappings['RUI']:
            self.faces, self.vertices = load(self.mappings['RUI'][self.name], self.file_type)
            self.target_transform = self._get_transform()
        else:
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
        hra_transform = self.hra_transforms[self.name]
        target_transform = Transform(hra_transform['scaling'], 
                                     hra_transform['rotation'], 
                                     np.array(hra_transform['translation']) / 1e3)
        return target_transform
    

    


        