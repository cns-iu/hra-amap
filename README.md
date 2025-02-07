# HRA-AMap - Bidirectional Projections Between Human Atlas Systems for Data and Code Interoperability

Code for AMap project. 

This repository aims to enable projection of tissue blocks registrered to a source organ to a new reference organ (usually the Human Reference Atlas, part of HuBMAP). 

### Setup instructions:

1. Clone the repository with ```git clone https://github.com/cns-iu/hra-amap.git```

2. Clone the repository (```https://github.com/ohirose/bcpd```) with ```git clone https://github.com/ohirose/bcpd.git```. This implements the Bayesian Coherent Point Drift algorithm based on the following paper [A Bayesian Formulation of Coherent Point Drift](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=8985307). The repository is ~1GB in file size hence it is not shipped with our repository and requires additional setup: 

    * For Windows

       1. No setup required.  

    * For MacOS and Linux

        1. Install the OpenMP and the LAPACK libraries if not installed. For MacOS, make sure XCode is installed. OpenMP can then be installed with the ```homebrew``` package manager (```https://brew.sh```) followed by ```brew install libomp```

        2. Type ```make OPT=-DUSE_OPENMP ENV=<your-environment>```. Substitute ```<uyour-environment>``` with ```LINUX``` for Linux, ```HOMEBREW_INTEL``` for Intel Macs and ```HOMEBREW``` for Macs with Apple Silicon. In case of a ```clang``` error during installation for MacOS, ensure to check if the ```makefile``` within the ```bcpd``` repository is pointing to the correct path for ```libomp.dylib```. In newer Macs, the correct path should be ```/opt/homebrew/Cellar/libomp/19.1.7/lib/libomp.dylib```

3. Ensure that the two repositories (hra-amap and bcpd) are at the **same root level**.

4. We recommend creating a virtual environment using ```miniconda``` or ```anaconda``` since the code requires the Python version to be <= 3.12. After activating the environment, install the following libraries:

```
pip install trimesh
pip install pyyaml
pip install open3d
pip install pyvista
pip install point-cloud-utils
pip install rtree
pip install seaborn
```

6. To run a quick registration using the provided pipeline, please see ```notebooks/Usage.ipynb```. Make sure to set appropriate parts in the code on your local system. 

7. Additionally, to create RUI JSONs for Millitomes (as shown in `Millitome.ipynb`), one needs to install [Node.js] (https://nodejs.org/en/download/) and run ```npx github:hubmapconsortium/hra-rui-locations-processor help```