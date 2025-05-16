import uuid
import trimesh
import numpy as np

from enum import Enum
from scipy.spatial.transform import Rotation

from pathlib import Path
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from hra_amap.registration.dataclass import Transform
from hra_amap.utils.io import read_yaml, write_json
from hra_amap.utils.conversions import to_pointcloud, to_array, split_transform
from hra_amap.utils.metrics import scaling, rotation
from hra_amap.utils.constants import ConfigKeys


class DivisionFactor(Enum):
    millimeter = 1e3
    centimeter = 1e2
    meter = 1


class TissueBlock(trimesh.Trimesh):
    """
    Represents a 3D tissue block mesh with associated donor and metadata information.

    Inherits from trimesh.Trimesh to utilize mesh functionalities.
    """

    def __init__(
        self, vertices, faces, donor: dict = None, metadata: dict = None
    ) -> None:
        """
        Initialize a TissueBlock instance.

        Args:
            vertices (array-like): Vertices of the mesh.
            faces (array-like): Faces of the mesh.
            donor (dict, optional): Donor information.
            metadata (dict, optional): Metadata associated with the tissue block.
        """
        super(TissueBlock, self).__init__()
        self.vertices, self.faces = (vertices, faces)
        if donor:
            self.donor = donor
        if metadata:
            self.metadata = metadata

    @property
    def pointcloud(self):
        """
        Convert the mesh to a point cloud representation.

        Returns:
            PointCloud: The point cloud representation of the mesh.
        """
        return to_pointcloud(self)

    @property
    def array(self):
        """
        Convert the mesh to a NumPy array representation.

        Returns:
            np.ndarray: The array representation of the mesh.
        """
        return to_array(self)

    @classmethod
    def from_sample(cls, sample: dict, donor: dict, target_name: str):
        """
        Create a TissueBlock instance from sample data.

        Args:
            sample (dict): Sample data containing RUI location and dimensions.
            donor (dict): Donor information.
            target_name (str): Name of the target organ.

        Returns:
            TissueBlock: A new TissueBlock instance.
        """
        dimension_units = sample["rui_location"]["dimension_units"]
        division_factor = getattr(DivisionFactor, dimension_units).value

        # size
        size = (
            sample["rui_location"]["x_dimension"] / division_factor,
            sample["rui_location"]["y_dimension"] / division_factor,
            sample["rui_location"]["z_dimension"] / division_factor,
        )
        # create block
        block = trimesh.creation.box(extents=size, origin=(0, 0, 0))
        block = cls(
            vertices=block.vertices,
            faces=block.faces,
            donor=donor,
            metadata=sample["rui_location"],
        )

        # add attributes
        block.division_factor = division_factor
        block.label = sample.get("label", None)
        block.target_name = target_name

        # get transforms
        block.target_transform = block._get_target_transform()
        block.transform = block._get_block_transform()

        # move the origin of the block from the box centre to its back-bottom-left (0, 0, 0)
        # block = block.apply_translation((block.extents[0] / 2, block.extents[1] / 2, block.extents[2] / 2))
        # put the block as intended on the HRA organ
        block = block.transform(block)
        block = block.target_transform.invert(block)

        return block

    @classmethod
    def from_millitome(
        cls, millitome, donor: dict, metadata: dict, translation_arr: list, label=None
    ):
        """
        Create a TissueBlock instance from a millitome mesh.

        Args:
            millitome: The millitome mesh.
            donor (dict): Donor information.
            metadata (dict): Metadata associated with the tissue block.
            translation_arr (list): Translation array for positioning.
            label (str, optional): Label for the tissue block.

        Returns:
            TissueBlock: A new TissueBlock instance.
        """
        block = cls(millitome.vertices, millitome.faces, donor, metadata)
        # add attributes
        block.label = label
        block.division_factor = 1e3

        # get transforms
        block.target_transform = block._get_target_transform(translation_arr)

        return block

    def _get_block_transform(self):
        """
        Compute the transformation to shift the target organ to the world origin.

        Args:
            translation_arr (list): Translation array for positioning.

        Returns:
            Transform: The transformation object for the target organ.
        """
        # scale
        scaling = (
            self.metadata["placement"]["x_scaling"],
            self.metadata["placement"]["y_scaling"],
            self.metadata["placement"]["z_scaling"],
        )

        # translation
        translation = (
            self.metadata["placement"]["x_translation"] / self.division_factor,
            self.metadata["placement"]["y_translation"] / self.division_factor,
            self.metadata["placement"]["z_translation"] / self.division_factor,
        )

        # rotation
        rotation = (
            self.metadata["placement"]["x_rotation"],
            self.metadata["placement"]["y_rotation"],
            self.metadata["placement"]["z_rotation"],
        )

        block_transform = Transform(
            scale=scaling, rotate=rotation, translate=translation
        )
        return block_transform

    def _get_target_transform(self, translation_arr: list):
        """Get the necessary transform shift the target HRA organ (it's back-bottom-left) to the world origin (0, 0, 0)"""
        # https://raw.githubusercontent.com/hubmapconsortium/hubmap-ontology/master/source_data/generated-reference-spatial-entities.jsonld
        if not hasattr(self, "target_name"):
            self.target_name = self.metadata["placement"]["target"].split("#")[-1]

        target_transform = Transform(scaling, rotation, translation_arr)
        return target_transform

    def to_sample(self, export_path: str):
        """
        Export the tissue block metadata to a JSON file.

        Args:
            export_path (str): Path to export the JSON file.
        """
        # split the transform matrix back to individual transforms
        scale, rotation, translation = split_transform(self.bounding_box.transform)

        # if metadata does not exist, insert default values
        # (this is for tissue blocks created using from_geometry method)
        if not self.metadata:
            self.metadata["@context"] = (
                "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld"
            )
            self.metadata["@type"] = "SpatialEntity"
            self.metadata["creator"] = "Bhargav Snehal Desai"
            self.metadata["creator_first_name"] = "Bhargav Snehal"
            self.metadata["creator_last_name"] = "Desai"
            self.metadata["creator_orcid"] = "https://orcid.org/0009-0008-6509-7698"
            self.metadata["creation_date"] = datetime.today().strftime("%Y-%m-%d")
            self.metadata["dimension_units"] = "millimeter"
            self.metadata["placement"] = dict()
            self.metadata["placement"][
                "@context"
            ] = "https://hubmapconsortium.github.io/ccf-ontology/ccf-context.jsonld"
            self.metadata["placement"]["@type"] = "SpatialPlacement"
            self.metadata["placement"][
                "target"
            ] = f"http://purl.org/ccf/latest/ccf.owl#{self.target_name}"
            self.metadata["placement"]["placement_date"] = self.metadata[
                "creation_date"
            ]
            self.metadata["placement"]["scaling_units"] = "ratio"
            self.metadata["placement"]["rotation_order"] = "XYZ"
            self.metadata["placement"]["rotation_units"] = "degree"
            self.metadata["placement"]["translation_units"] = "millimeter"

        # dimensions
        self.metadata["x_dimension"] = (
            self.bounding_box.extents[0].item() * self.division_factor
        )
        self.metadata["y_dimension"] = (
            self.bounding_box.extents[1].item() * self.division_factor
        )
        self.metadata["z_dimension"] = (
            self.bounding_box.extents[2].item() * self.division_factor
        )

        # update scaling
        self.metadata["placement"]["x_scaling"] = scale[0].item()
        self.metadata["placement"]["y_scaling"] = scale[1].item()
        self.metadata["placement"]["z_scaling"] = scale[2].item()

        # update rotation
        self.metadata["placement"]["x_rotation"] = rotation[0].item()
        self.metadata["placement"]["y_rotation"] = rotation[1].item()
        self.metadata["placement"]["z_rotation"] = rotation[2].item()

        # update translation
        self.metadata["placement"]["x_translation"] = (
            translation[0].item() * self.division_factor
        )
        self.metadata["placement"]["y_translation"] = (
            translation[1].item() * self.division_factor
        )
        self.metadata["placement"]["z_translation"] = (
            translation[2].item() * self.division_factor
        )

        # update id
        self.metadata["@id"] = f"{self.donor['id']}#{self.label}"
        self.metadata["label"] = self.label
        self.metadata["placement"]["@id"] = f"{self.metadata['@id']}_placement"

        # write to json
        write_json(f"{Path(export_path) / f'{self.label}'}.json", self.metadata)

    @lru_cache
    def show_on_target(self):
        """
        Visualize the tissue block on the target organ.

        Returns:
            Scene: A trimesh scene displaying the tissue block and target organ.
        """
        self.target = trimesh.load(
            Path(self.metadata[ConfigKeys.INPUT_FILES][ConfigKeys.TARGET]), force="mesh"
        )
        return trimesh.scene.Scene(
            geometry=[self, trimesh.creation.axis(), deepcopy(self.target)]
        ).show()
