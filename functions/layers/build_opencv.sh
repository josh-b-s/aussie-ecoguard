#!/usr/bin/env bash
# Builds the OpenCV layer for Lambda (Linux x86_64, Python 3.12) from any machine.
# Result is about 205 MB unzipped, under Lambda's 250 MB limit for code plus layers.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf opencv/python
pip install \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target opencv/python \
  "opencv-python-headless<5" numpy
# Drop files Lambda never needs
find opencv/python -type d \( -name tests -o -name __pycache__ \) -prune -exec rm -rf {} +
rm -rf opencv/python/bin
