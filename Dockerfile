# scitran-apps/parrec-mr-classifier
#
# Use nibabel to classify raw PARREC data from Philips.
#
# Example usage:
#   docker run --rm -ti \
#        -v /path/to/dicom/data:/data \
#        scitran/parrec-mr-classifier \
#        /data/input.zip \
#        /data/outprefix
#

FROM ubuntu:xenial
MAINTAINER Michael Perry <lmperry@stanford.edu>

# Install dependencies
RUN apt-get update && apt-get -y install \
    python \
    python-pip \
    python-numpy \
    python-nibabel \
    tzdata \
    wget \
    jq

# Install Pip libs
RUN pip install \
  python-dateutil==2.6.0 \
  pytz==2017.2 \
  tzlocal==1.4

# Make directory for flywheel spec (v0)
ENV FLYWHEEL /flywheel/v0
RUN mkdir -p ${FLYWHEEL}
COPY run ${FLYWHEEL}/run
COPY manifest.json ${FLYWHEEL}/manifest.json

# Add code to determine classification from acquisitions descrip (label)
ENV COMMIT 3f202ef731918e10c5c1da2dcfd8726edda3f010
ADD https://raw.githubusercontent.com/scitran-apps/dicom-mr-classifier/${COMMIT}/classification_from_label.py ${FLYWHEEL}/classification_from_label.py

# Copy classifier code into place
COPY parrec-mr-classifier.py ${FLYWHEEL}/parrec-mr-classifier.py

# Set the entrypoint
ENTRYPOINT ["/flywheel/v0/run"]
