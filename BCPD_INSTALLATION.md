## BCPD INSTALLATION INSTRUCTIONS

Inside the cloned hra-amap repostisory, clone bcpd repository (https://github.com/ohirose/bcpd) with git clone https://github.com/ohirose/bcpd.git. This implements the Bayesian Coherent Point Drift algorithm based on the following paper A Bayesian Formulation of Coherent Point Drift. The repository is ~1GB in file size hence it is not shipped with our repository and requires additional setup:

For Windows

No setup required.

For MacOS and Linux

Install the OpenMP and the LAPACK libraries if not installed. For MacOS, make sure XCode is installed. OpenMP can then be installed with the homebrew package manager (https://brew.sh) followed by brew install libomp

Type make OPT=-DUSE_OPENMP ENV=<your-environment>. Substitute <uyour-environment> with LINUX for Linux, HOMEBREW_INTEL for Intel Macs and HOMEBREW for Macs with Apple Silicon. In case of a clang error during installation for MacOS, ensure to check if the makefile within the bcpd repository is pointing to the correct path for libomp.dylib. In newer Macs, the correct path should be /opt/homebrew/Cellar/libomp/19.1.7/lib/libomp.dylib. Note that current libomp version is 19.1.7, but the library version might different depending on the time of installation.

