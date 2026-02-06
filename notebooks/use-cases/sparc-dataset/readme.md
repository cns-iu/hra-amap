## 🧬 SPARC Dataset

SPARC provides curated anatomical models and datasets that serve as external reference atlases for spatial mapping workflows.  
In this project, SPARC datasets are used as **external (non-HRA) atlases** to support backward projection and Non-HRA mapping of Human Reference Atlas (HRA)–annotated spatial data.

### 🫀 SPARC Human Heart

The SPARC Human Heart dataset provides a generic anatomical heart scaffold that is used as the external atlas for Non-HRA mapping workflows.  
This scaffold serves as the external reference model and is mapped to **both HRA Female and HRA Male heart reference organs** during backward projection and Non-HRA mapping.

  - Direct download link: [Generic human heart scaffold](https://sparc.science/datasets/file/100/7?path=files/derivative/heartHuman_zinc_graphics.stl)

---

## 📥 SPARC Dataset Access
1. Navigate to the SPARC Science portal:  [Sparc.Science](https://sparc.science)
2. Locate the desired atlas dataset using the following navigation path:
  `Data & Models → <External Atlas Dataset> → Files`
3. Download the available **STL mesh file** associated with the selected atlas  
(for example, `heartHuman_zinc_graphics.stl`).
4. Convert the downloaded STL file to **GLB format**.  
  (The Non-HRA mapping pipeline requires external atlas meshes to be provided in GLB format.)
5. Place the converted GLB file in the external atlas input directory:
  ```
    input-data/external_atlas/<atlas_name>_<sex>/
  ├── <atlas_mesh>.glb
  └── config.yaml```

---

## Non-HRA Mapping Notebook

This notebook implements a workflow to map **Human Reference Atlas (HRA)**–annotated spatial data into a **non-HRA coordinate system** defined by an external atlas.

The workflow applies **backward projection** to transform tissue sample locations that were originally annotated in an HRA reference organ into the coordinate space of a non-HRA reference model.

---

### 🎯 Objective

The objective of this notebook is to:

- Transform HRA-annotated spatial data into a non-HRA coordinate system  
- Map tissue blocks from HRA reference organs into an external atlas  
- Generate interoperable 3D and semantic outputs suitable for visualization and downstream analysis  

---

### 🧭 Workflow Overview

At a high level, this notebook performs the following steps:

1. Loads an external atlas and normalizes it into a working coordinate space  
2. Reads configuration describing donor, organ, and spatial metadata  
3. Fetches and filters HRA-annotated tissue samples using ontology-based criteria  
4. Applies **backward projection** from the HRA reference organ to the external atlas  
5. Maps donor tissue blocks into the external atlas coordinate system  
6. Generates outputs that preserve spatial, donor, and sample relationships  