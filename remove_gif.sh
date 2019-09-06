#!/bin/bash

set -e

[  $# -eq 1 ] || (echo "Usage: $0 base_dir"; exit 1)
echo "Removing GIF files in $1"

for f in `find $1 -type f -name "*.jpg"`; do
    [ -z "`file $f | grep GIF`" ] || (echo "Seems $f is GIF. Remove."; rm -f $f;)
done