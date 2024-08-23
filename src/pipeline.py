import yaml
import uuid

from copy import deepcopy
from scipy.spatial import distance

from organ import Organ
from dataclass import Projection
from steps import *
from utils.conversions import to_mesh
from utils.metrics import sinkhorn, chamfer, hausdorff


class Pipeline():
    def __init__(self, name: str, description: str, params: str) -> None:
        self.__id = uuid.uuid4()
        self.name = name
        self.description = description
        self.steps = {}
        with open(params) as f:
            self.params = yaml.safe_load(f)

    def _hyperparamter_search():
        raise NotImplementedError
    
    def _autotune():
        raise NotImplementedError

    def run(self, source: Organ, target: Organ):
        # Step 1: Normalize (ICP)
        self.steps['normalize_rigid'] = normalize_rigid(source=deepcopy(source.pointcloud), 
                                                        target=deepcopy(target.pointcloud))

        # Step 2: Global (Fast) Registration
        self.steps['global_registration'] = global_registration(source=deepcopy(self.steps['normalize_rigid'].output['Source']), 
                                                                target=deepcopy(self.steps['normalize_rigid'].output['Target']), 
                                                                params=self.params['rigid_registration'])
        
        # Step 3: Rigid Registration
        self.steps['refine_registration'] = refine_registration(source=deepcopy(self.steps['normalize_rigid'].output['Source']), 
                                                                target=deepcopy(self.steps['normalize_rigid'].output['Target']),
                                                                transform=self.steps['global_registration'].transform, 
                                                                params=self.params['rigid_registration'])

        # Step 4: Normalize (BCPD)
        self.steps['normalize_nonrigid'] = normalize_nonrigid(source=deepcopy(self.steps['refine_registration'].output['Source']), 
                                                              target=deepcopy(self.steps['normalize_rigid'].output['Target']))

        # Step 5: Non-rigid Registration (BCPD)
        self.steps['nonrigid_registration'] = nonrigid_registration(source=deepcopy(self.steps['normalize_nonrigid'].output['Source']), 
                                                                    target=deepcopy(self.steps['normalize_nonrigid'].output['Target']),
                                                                    params=self.params['nonrigid_registration'])

        # Step 6: Denormalization (BCPD)
        self.steps['denormalize_nonrigid'] = denormalize_nonrigid(source=deepcopy(self.steps['nonrigid_registration'].output['Source']),
                                                                  target=deepcopy(self.steps['nonrigid_registration'].output['Source']),
                                                                  transforms=self.steps['normalize_nonrigid'].transform)
        
        # Step 7: Denormalization (ICP)
        self.steps['denormalize_rigid'] = denormalize_rigid(source=deepcopy(self.steps['denormalize_nonrigid'].output['Source']),
                                                            target=deepcopy(self.steps['denormalize_nonrigid'].output['Source']),
                                                            transforms=self.steps['normalize_rigid'].transform)
        
        # consolidate projections
        projections = Projection(id=self.__id, 
                                 description=self.description, 
                                 source=source, 
                                 target=target,
                                 params=self.params,
                                 registration=to_mesh(self.steps['denormalize_rigid'].output['Source'], source.faces, process=False),
                                 transformations=[(name, step.transform['Source']) for name, step in self.steps.items() if step.transform])

        # return projections
        return projections

    def compute_metrics(self, metric: str):
        if metric not in ['sinkhorn, chamfer, hausdorff']:
            raise ValueError(f"{metric} not recognized, must be one of sinkhorn, chamfer or hausdorff")
        return metric(self.result)