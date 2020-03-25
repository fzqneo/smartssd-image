FROM ubuntu:bionic

RUN apt update \
    && apt-get install -y --no-install-recommends \
        python \
        python-pip \
        unzip \
    && pip install -U --no-cache-dir pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN pip install --no-cache-dir \
    protobuf==3.1.0 \
    flask

COPY ["Kinetic-Tools.zip", "/root/"]

WORKDIR /root
RUN unzip Kinetic-Tools.zip \
    && (cd python-client; python setup.py develop) \
    && rm -rf Kinetic-Tools.zip python-client/.git





