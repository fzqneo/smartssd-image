.PHONY: docker

docker:
	nvidia-docker build -t smartssd .

install:
	python setup.py install && rm -rf build dist s3dexp.egg-info .eggs
	