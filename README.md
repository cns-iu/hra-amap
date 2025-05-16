# HRA-AMap - Bidirectional Projections Between Human Atlas Systems for Data and Code Interoperability

Code for AMap project. 

This repository aims to enable projection of tissue blocks registrered to a source organ to a new reference organ (usually the Human Reference Atlas, part of HuBMAP). 

### Setup instructions:

1. Clone the repository with ```git clone https://github.com/cns-iu/hra-amap.git```

2. Inside the cloned ```hra-amap``` repostisory, clone ``bcpd`` repository (```https://github.com/ohirose/bcpd```) with ```git clone https://github.com/ohirose/bcpd.git```. This implements the Bayesian Coherent Point Drift algorithm based on the following paper [A Bayesian Formulation of Coherent Point Drift](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=8985307). The repository is ~1GB in file size hence it is not shipped with our repository and requires additional setup: 

    * For Windows

       1. No setup required.  

    * For MacOS and Linux

        1. Install the OpenMP and the LAPACK libraries if not installed. For MacOS, make sure XCode is installed. OpenMP can then be installed with the ```homebrew``` package manager (```https://brew.sh```) followed by ```brew install libomp```

        2. Type ```make OPT=-DUSE_OPENMP ENV=<your-environment>```. Substitute ```<uyour-environment>``` with ```LINUX``` for Linux, ```HOMEBREW_INTEL``` for Intel Macs and ```HOMEBREW``` for Macs with Apple Silicon. In case of a ```clang``` error during installation for MacOS, ensure to check if the ```makefile``` within the ```bcpd``` repository is pointing to the correct path for ```libomp.dylib```. In newer Macs, the correct path should be ```/opt/homebrew/Cellar/libomp/19.1.7/lib/libomp.dylib```. Note that current libomp version is 19.1.7, but the library version might different depending on the time of installation. 

3. We recommend creating a virtual environment using [```miniconda```] (https://docs.anaconda.com/miniconda/install/) or [```anaconda``` ](https://docs.anaconda.com/anaconda/install/). The recommended Python version is 3.12.x. Create and activate environment using the following commands on a shell:

```
# create
conda create -n amap python=3.12

# activate
conda activate amap
```

4. After activating the environment, install the following libraries:

```
pip install trimesh
pip install pyyaml
pip install open3d
pip install pyvista
pip install point-cloud-utils
pip install rtree
pip install seaborn
pip install scikit-learn
```

5. To run a quick registration using the provided pipeline, please see ```notebooks/Usage.ipynb```. Make sure to set appropriate parts in the code on your local system. 

6. Additionally, to create RUI JSONs for Millitomes (as shown in `Millitome.ipynb`), one needs to install [Node.js] (https://nodejs.org/en/download/) and run ```npx github:hubmapconsortium/hra-rui-locations-processor help```

## List of Millitome Based Registrations

| Millitomes                                      | Data Provider                                       | Institution | Link To Resources                                                                 |
|-------------------------------------------------|----------------------------------------------------|-------------|----------------------------------------------------------------------------------|
| hubmap-kidney_millitome-spraggins-2024           | Jamie Allen                                        | VU          | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-kidney_millitome-spraggins-2024) |
| hubmap-pancreas_millitome-saunders-2024          | Angela Kruse and Diane Saunders                    | VU          | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-pancreas_millitome-saunders-2024) |
| hubmap-pancreas_millitome-thompson-2024          | Jing Chen, James Carson, Martha Campbell Thompson  | UF          | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-pancreas_millitome-thompson-2024) |
| hubmap-ovary_millitome-fisher-2024               | Stephen Fisher, Erik Nogden                        | UPenn       | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-ovary_millitome-fisher-2024) |
| hubmap-uterus_millitome-fisher-2024              | Stephen Fisher, Erik Nogden                        | UPenn       | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-uterus_millitome-fisher-2024) |
| hubmap-fallopian_tube_millitome-fisher-2024      | Stephen Fisher, Erik Nogden                        | UPenn       | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/hubmap-fallopian_tube_millitome-fisher-2024) |
| allen-brain_millitome-linnarsson-2023            | Jeremy Miller, Ashwin Bhandiwad, Lydia Ng          | Allen       | [Link](https://github.com/hubmapconsortium/hra-registrations/tree/main/staging/allen-brain_millitome-linnarsson-2022) |

## 🛠️ Build with Hatch
To build and install the project locally using [Hatch](https://hatch.pypa.io/):
Make sure you have a working C++ build environment (e.g., `g++`, `make`) available on your system.

1. Install Hatch (if not already installed)
```bash
pip install hatch
```
2. Build the package (compiles the BCPD binary and packages everything)
```bash
hatch build
```
3. Install the built wheel (adjust version if needed)
```bash
pip install dist/hra_amap-0.5.0-py3-none-any.whl
```
4. (Optional) Uninstall to reset or clean up
```bash
pip uninstall hra-amap
```
## Millitome Registration: Stage 1

This command executes the **first stage** of the millitome registration process. It takes a configuration file containing RUI location and donor data, then generates the projected 3D model data needed for Stage 2 of the registration pipeline.

### Usage

```bash
python -m hra_amap.cli.registration_stage_1 \
    --config <path_to_config.yaml> \
    --output_path <path_to_output_directory>
```

or if installed via pip:

```bash
hra-amap-stage-1 \
    --config <path_to_config.yaml> \
    --output_path <path_to_output_directory>
```

##  Millitome Registration: Stage 2

This command executes the **second stage** of the millitome registration process. It takes the output from Stage 1 (a projection file), a configuration file, and produces the final registered organ models.

### Usage

```bash
python -m hra_amap.cli.registration_stage_2 \ 
    --stage1_projection_path <path_to_projections.pickle.gz> \
    --output_path <path_to_output_directory> \
    --config <path_to_config.yaml>
```

or if installed via pip:

```bash
hra-amap-stage-2 \
    --stage1_projection_path <path_to_projections.pickle.gz> \
    --output_path <path_to_output_directory> \
    --config <path_to_config.yaml>
```

## Build All Millitomes

This command runs both **Stage 1** and **Stage 2** of the registration pipeline across all available millitome datasets by convention.  
It automatically discovers all valid organ configurations in the `input-data/millitome/` directory and processes each accordingly.

### Usage

```bash
python hra_amap.cli.run
```

or if installed via pip:

```bash
hra-amap-run
```
