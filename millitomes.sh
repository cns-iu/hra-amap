#!/bin/bash

echo "# Available millitomes"
echo

for f in `find output-data -name index.html | sort`; do
  name=$(echo $f | cut -d '/' -f 3)
  version=$(echo $f | cut -d '/' -f 4)
  echo " * [$name $version](https://cns-iu.github.io/hra-amap/$f)"
done
