#!/bin/bash

# The YFCC100M dataset have some GIF and PNG files even if they have extension .jpg.

set -e

[  $# -eq 1 ] || (echo "Usage: $0 base_dir"; exit 1)
echo "Removing GIF files in $1"

for f in `find $1 -type f -name "*.jpg"`; do
    [ -z "`file $f | grep -e GIF -e PNG`" ] || (echo "Seems $f is GIF or PNG. Remove."; rm -f $f;)
done