import yaml
import uuid

from copy import deepcopy
from tqdm.auto import tqdm

from hra_amap.registration.organ import Organ
from hra_amap.registration.dataclass import Projection
from hra_amap.registration.steps import *
from hra_amap.utils.conversions import to_mesh
from hra_amap.utils.metrics import sinkhorn, chamfer, hausdorff


class Pipeline:
    """
    A registration pipeline for aligning source and target 3D organ meshes using
    rigid and non-rigid transformations.
    """

    def __init__(self, name: str, description: str, params: str) -> None:
        """
        Initialize the pipeline.

        Args:
            name (str): Pipeline name.
            description (str): Description of the pipeline.
            params (str): Path to the YAML configuration file with registration parameters.
        """
        self.__id = uuid.uuid4()
        self.name = name
        self.description = description
        self.steps = {}
        if isinstance(params, dict):
            self.params = params
        else:
            with open(params) as f:
                self.params = yaml.safe_load(f)

    def _prepare_organs(self, source, target):
        progress = bool(self.params.get("progress", False))
        volumetric = bool(self.params.get("volumetric", False))

        for organ in (source, target):
            organ.volumetric = volumetric
            organ.progress = progress

    def run(self, source: Organ, target: Organ):
        """
        Execute the full registration pipeline and return the resulting Projection.

        Args:
            source (Organ): The source organ to register.
            target (Organ): The target organ to register to.

        Returns:
            Projection: Contains the aligned geometry and transformation history.
        """
        self._prepare_organs(source, target)

        progress = bool(self.params.get("progress", False))
        steps = tqdm(total=7, desc="Registration", unit="step") if progress else None

        # Step 1: Normalize (ICP)
        if progress:
            steps.set_description("Normalize rigid")
        self.steps["normalize_rigid"] = normalize_rigid(
            source=deepcopy(source.pointcloud), target=deepcopy(target.pointcloud)
        )
        if progress:
            steps.update()

        # Step 2: Global (Fast) Registration
        if progress:
            steps.set_description("Global registration")
        self.steps["global_registration"] = global_registration(
            source=deepcopy(self.steps["normalize_rigid"].output["Source"]),
            target=deepcopy(self.steps["normalize_rigid"].output["Target"]),
            params=self.params["rigid_registration"],
        )
        if progress:
            steps.update()

        # Step 3: Rigid Registration
        if progress:
            steps.set_description("Refine rigid")
        self.steps["refine_registration"] = refine_registration(
            source=deepcopy(self.steps["normalize_rigid"].output["Source"]),
            target=deepcopy(self.steps["normalize_rigid"].output["Target"]),
            transform=self.steps["global_registration"].transform,
            params=self.params["rigid_registration"],
        )
        if progress:
            steps.update()

        # Step 4: Normalize (BCPD)
        if progress:
            steps.set_description("Normalize nonrigid")
        self.steps["normalize_nonrigid"] = normalize_nonrigid(
            source=deepcopy(self.steps["refine_registration"].output["Source"]),
            target=deepcopy(self.steps["normalize_rigid"].output["Target"]),
        )
        if progress:
            steps.update()

        # Step 5: Non-rigid Registration (BCPD)
        if progress:
            steps.set_description("BCPD nonrigid")
        self.steps["nonrigid_registration"] = nonrigid_registration(
            source=deepcopy(self.steps["normalize_nonrigid"].output["Source"]),
            target=deepcopy(self.steps["normalize_nonrigid"].output["Target"]),
            params={
                **self.params["nonrigid_registration"],
                "progress": progress,
            },
        )
        if progress:
            steps.update()

        # Step 6: Denormalization (BCPD)
        if progress:
            steps.set_description("Denormalize nonrigid")
        self.steps["denormalize_nonrigid"] = denormalize_nonrigid(
            source=deepcopy(self.steps["nonrigid_registration"].output["Source"]),
            target=deepcopy(self.steps["nonrigid_registration"].output["Source"]),
            transforms=self.steps["normalize_nonrigid"].transform,
        )
        if progress:
            steps.update()

        # Step 7: Denormalization (ICP)
        if progress:
            steps.set_description("Denormalize rigid")
        self.steps["denormalize_rigid"] = denormalize_rigid(
            source=deepcopy(self.steps["denormalize_nonrigid"].output["Source"]),
            target=deepcopy(self.steps["denormalize_nonrigid"].output["Source"]),
            transforms=self.steps["normalize_rigid"].transform,
        )
        if progress:
            steps.update()
            steps.close()

        # consolidate projections
        projections = Projection(
            id=self.__id,
            description=self.description,
            source=source,
            target=target,
            params=self.params,
            registration=to_mesh(
                self.steps["denormalize_rigid"].output["Source"],
                source.faces,
                process=False,
            ),
            transformations=[
                (name, step.transform["Source"])
                for name, step in self.steps.items()
                if step.transform
            ],
            metadata={
                "volumetric": bool(self.params.get("volumetric", False)),
                "source_surface_count": int(source.surface_count),
                "target_surface_count": int(target.surface_count),
                "source_visual_hull": source.visual_hull_stats
                if source.volumetric
                else None,
                "target_visual_hull": target.visual_hull_stats
                if target.volumetric
                else None,
            },
        )

        # return projections
        return projections

    def compute_metrics(self, metric: str):
        """
        Compute a similarity metric between source and registered output.

        Args:
            metric (str): One of "sinkhorn", "chamfer", "hausdorff".

        Returns:
            float: The computed metric value.
        """
        if metric not in ["sinkhorn, chamfer, hausdorff"]:
            raise ValueError(
                f"{metric} not recognized, must be one of sinkhorn, chamfer or hausdorff"
            )
        return metric(self.result)
