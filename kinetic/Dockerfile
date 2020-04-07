# compile pyzmq
FROM arm64v8/ubuntu:18.04 AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        python \
        python-dev \
        python-pip \
    && pip install -U --no-cache-dir pip setuptools wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN pip wheel --wheel-dir=/root pyzmq

# begin production
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

COPY --from=builder /root/pyzmq*.whl /root/

RUN pip install --no-cache-dir \
    fire \
    flask \
    logzero \
    protobuf==3.8.0 \
    /root/pyzmq*.whl

COPY [".", "/root/kinetic"]
WORKDIR /root/kinetic

RUN (cd python-client; python setup.py develop && python setup.py clean)
CMD ["python", "proxy_server.py", "localhost"]





