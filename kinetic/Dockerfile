FROM arm64v8/ubuntu:18.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iproute2 \
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

CMD ["python", "app.py", "localhost"]





