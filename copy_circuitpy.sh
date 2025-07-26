#! /bin/bash

# Check if --force flag is provided
FORCE_FLAG=""
if [[ "$1" == "--force" ]]; then
    FORCE_FLAG=""
else
    FORCE_FLAG="--size-only"
fi

if [ -d "/Volumes/CIRCUITPY/" ]
then
echo "Copying to CIRCUITPY"
rsync -av $FORCE_FLAG ./*.py /Volumes/CIRCUITPY/
fi

if [ -d "/Volumes/CIRCUITPY 1/" ]
then
echo "Copying to CIRCUITPY 1"
rsync -av $FORCE_FLAG ./*.py "/Volumes/CIRCUITPY 1/"
fi