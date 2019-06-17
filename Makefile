.PHONY: docker

docker:
	nvidia-docker build -t smartssd .
