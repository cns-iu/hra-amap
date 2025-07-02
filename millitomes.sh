#!/bin/bash

echo "# Available millitomes"
echo

for f in `find output-data -name index.html | sort`; do
  name=$(echo $f | cut -d '/' -f 3)
  version=$(echo $f | cut -d '/' -f 4)
  glb=$(ls `dirname $f`/*.glb)
  echo " * $name $version ([EUI](https://cns-iu.github.io/hra-amap/$f)) ([3d view](https://sandbox.babylonjs.com/?assetUrl=https://cns-iu.github.io/hra-amap/$glb))"
done
