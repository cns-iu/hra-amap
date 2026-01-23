# Hra to Non Hra Mapping (SPARC HEART)
This notebook contains workflow to map Human Reference Atlas (HRA) annotated spatial data to a non-HRA coordinate system for the SPARC Heart (Female) dataset. It processes spatial data from tissue samples annotated in the HRA and transforms them spatial format.

---

## 🔍 What This Notebook Does

At a high level, the notebook:

1. Loads a reference organ model and normalizes it into a working coordinate space  
2. Reads configuration describing donor, organ, and spatial metadata  
3. Processes HRA-annotated samples containing RUI (Registration User Interface) location information  
4. Converts HRA placements into non-HRA spatial mappings  
5. Generates JSON-LD outputs that preserve spatial, donor, and sample relationships  
6. Visualizes the resulting spatial mappings in 3D

---

## 📤 Outputs

**Projected Heart (Female):** [SPARC Heart Female](https://sandbox.babylonjs.com/?assetUrl=https://cns-iu.github.io/hra-amap/notebooks/use-cases/sparc-heart-female/output-data/spar-heart-female.glb)

The notebook typically produces:

- **Extraction site JSON-LD**
  - Spatial entities derived from HRA sample placements

- **Dataset graph JSON-LD**
  - Donor → sample → spatial entity relationships