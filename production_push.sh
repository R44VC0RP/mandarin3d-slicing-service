#!/bin/sh
cd /home/ryan/docker_build/mandarin3d_slicing

# Define the version number
VERSION=$(cat version)


echo "Creating Mandarin3D Slicer Docker Image"
docker image build -t mandarin3d .

# Tagging with version and latest
docker tag mandarin3d:latest mandarin3d/mandarin3d-slicer:$VERSION
docker tag mandarin3d:latest mandarin3d/mandarin3d-slicer:latest

# Pushing both tags
docker push mandarin3d/mandarin3d-slicer:$VERSION
docker push mandarin3d/mandarin3d-slicer:latest

echo "Docker Images Uploaded: latest and $VERSION."

# increment version number
VERSION=$(echo "$VERSION + 0.1" | bc)
echo $VERSION > version