# FROM registry.cmusatyalab.org/diamond/diamond-new-filters/image:20180409
FROM ubuntu:xenial

RUN apt-get update --fix-missing \
    && apt-get upgrade -y \
    && apt-get install -y \
        wget \
        bzip2 \
        ca-certificates \
        curl \
        git \
        build-essential \
        g++ \
        gcc \
        cmake \
        vim \
        python \
        python-dev \
        hdparm \
        libglib2.0-0 \
        # libgtk-3-dev \
        # libboost-all-dev \
        # libopenblas-dev \
        # liblapack-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN (wget -qO- "https://bootstrap.pypa.io/get-pip.py" | python)

# Install libjpeg-turbo and python bindings
# RUN wget https://sourceforge.net/projects/libjpeg-turbo/files/2.0.0/libjpeg-turbo-official_2.0.0_amd64.deb/download -O libjpeg-turbo-official_2.0.0_amd64.deb \
#     && dpkg -i libjpeg-turbo-official_2.0.0_amd64.deb \
#     && pip install -U git+git://github.com/lilohuang/PyTurboJPEG.git

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

COPY . /root/src
WORKDIR /root/src/script
