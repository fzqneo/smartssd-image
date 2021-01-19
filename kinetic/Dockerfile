# build pyzmq and Pillow
FROM arm64v8/ubuntu:18.04 AS builder

# libjpeg-turbo and zlib for Pillow
# https://pillow.readthedocs.io/en/stable/installation.html#external-libraries
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        libjpeg-turbo8-dev \
        python \
        python-dev \
        python-pip \
        zlib1g-dev \
    && pip install -U --no-cache-dir pip setuptools wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN pip wheel --wheel-dir=/root pyzmq Pillow 

# begin production
FROM arm64v8/ubuntu:18.04
COPY --from=builder /root/*.whl /root/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        iproute2 \
        libjpeg-turbo8 \
        python \
        python-pip \
        stress-ng \
        zlib1g \
    && python -m pip install -U --no-cache-dir pip setuptools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN python -m pip install --no-cache-dir \
    fire \
    logzero \
    pathlib2 \
    protobuf==3.8.0 \
    /root/pyzmq*.whl \
    /root/Pillow*.whl  \
    && rm -f /root/*.whl

COPY [".", "/root/kinetic"]
WORKDIR /root/kinetic

RUN (cd python-client; python setup.py develop && python setup.py clean)
CMD ["python", "proxy_server.py", "localhost"]
