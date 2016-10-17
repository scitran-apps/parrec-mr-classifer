#!/bin/bash
# Exports the container in the cwd. The container can be exported once it's
# started.

version=0.0.2
repo=scitran
container=dicom-mr-classifier
outname=$container-$version.tar
image=$repo/$container

# Check if input was passed in to use as an output name
if [[ -n $1 ]]; then
    outname=$1
fi

docker run --name=$container --entrypoint=/bin/true $image
docker export -o $outname $container
docker rm $container
