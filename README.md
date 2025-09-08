# HRA-AMAP
HRA-AMAP (Human Reference Atlas – Automated Mapping and Projection) enables automated projection of tissue blocks from a source organ to a new reference organ—typically aligned with the Human Reference Atlas (HRA)—as part of the HuBMAP initiative.

**🧬 List of available millitomes:** https://cns-iu.github.io/hra-amap/millitomes.html 

📦 HRA Registrations repository: https://github.com/hubmapconsortium/hra-registrations

## 🚀 User Setup Instructions

1. Clone and install the repository directly from GitHub:
```bash
pip install git+https://github.com/cns-iu/hra-amap.git@main
```
2. Make sure you have a working C++ build environment (e.g., g++, make) available on your system.
3. Install [BCPD](https://github.com/ohirose/bcpd) (an essential component of this project)

   Please follow the [BCPD Installation Instructions](https://github.com/cns-iu/hra-amap/blob/main/BCPD_INSTALLATION.md) if it is not already set up on your machine.
4. You are now ready to run the millitome registration commands (stage-1, stage-2, or run). See Usage Instructions for details below.

## 🧑‍💻 Developer Setup Instructions
To contribute or develop this project locally, follow the steps below:
1. Clone the repository:
```bash
git clone https://github.com/cns-iu/hra-amap.git
cd hra-amap
```
2. Install BCPD by following [BCPD Installation Instructions](https://github.com/cns-iu/hra-amap/blob/main/BCPD_INSTALLATION.md).
3. Install [Node.js] (https://nodejs.org/en/download/) and run the command (required create RUI JSONs for Millitomes):
```bash
npx github:hubmapconsortium/hra-rui-locations-processor help
```
4. Install [Hatch](https://hatch.pypa.io/) (used to build and install hra-amap package locally):
```bash
pip install hatch
```
3. Install dependencies for development:
```bash
pip install -e .
```
5. Build the package (compiles the BCPD binary and packages everything)
```bash
hatch build
```
6. Install the built wheel (adjust version if needed)
```bash
pip install dist/hra_amap-0.5.0-py3-none-any.whl
```
7. (Optional) Uninstall to reset or clean up
```bash
pip uninstall hra-amap
```
8. You are now ready to run the millitome registration commands (stage-1, stage-2, or run). See Usage Instructions for details below.

## 🧬 Adding a New Millitome Dataset

To register a new millitome organ, organize the necessary configuration and input files as described below.

### 📁 Directory Structure
Each millitome dataset should be placed in its own subdirectory under:
```bash
input-data/millitome/<organ-name>-<sex>-<source>/<version>/
```

### 📦 Required Files

Place the following files inside the <version> directory:
| Filename              | Description                                                      |
|-----------------------|------------------------------------------------------------------|
| `config.yaml`         | Configuration file with metadata and registration parameters.    |
| `source.glb`          | The `.glb` version of the source mesh for visualization in RUI.  |

## ⚙️ Millitome Registration Usage Instructions

🔹 Stage 1: Generates the projected 3D model data

It takes a configuration file with RUI locations and donor metadata, and generates projection data that serves as input for Stage 2.
```bash
hra-amap-stage-1 \
    --config <path_to_config.yaml> \
    --output_path <path_to_output_directory> \
    --point_cloud_output_path <path_to_point_cloud_tranformation_glb>
```

🔹 Stage 2: Produces the final registered organ model

It takes the output from Stage 1 (a projection file), a configuration file, and produces the final registered organ models.
```bash
hra-amap-stage-2 \
    --stage1_projection_path <path_to_projections.pickle.gz> \
    --output_path <path_to_output_directory> \
    --config <path_to_config.yaml>
```

🔹 Run All: Register All Available Millitome Organs
This command automates both Stage 1 and Stage 2 for all available millitome configurations found in the input-data/millitome/ directory.
```bash
hra-amap-run
```
