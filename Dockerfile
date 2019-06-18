FROM ubuntu:xenial

# https://hub.docker.com/r/conda/miniconda2/dockerfile
RUN apt-get -qq update && apt-get -qq -y install curl bzip2 \
    && curl -sSL https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -o /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -bfp /usr/local \
    && rm -rf /tmp/miniconda.sh \
    && conda install -y python=2 \
    && conda update conda \
    && apt-get -qq -y remove curl bzip2 \
    && apt-get -qq -y autoremove \
    && apt-get autoclean \
    && rm -rf /var/lib/apt/lists/* /var/log/dpkg.log \
    && conda clean --all --yes

ENV PATH /opt/conda/bin:$PATH

# TODO consolidate apt install
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
        libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY environment.yml /tmp/
RUN conda env update -n base --file /tmp/environment.yml

COPY . /root/src
WORKDIR /root/src/script
