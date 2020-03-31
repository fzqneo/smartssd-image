FROM ubuntu:bionic

RUN apt update \
    && apt-get install -y --no-install-recommends \
        python \
        python-pip \
        unzip \
    && pip install -U --no-cache-dir pip setuptools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN pip install --no-cache-dir \
    fire \
    flask \
    logzero \
    protobuf==3.1.0

COPY [".", "/root/kinetic"]
WORKDIR /root/kinetic

RUN unzip Kinetic-Tools.zip \
    && (cd python-client; python setup.py develop) \
    && rm -rf Kinetic-Tools.zip python-client/.git

ENTRYPOINT ["python", "app.py"]





