
restart: build push dsh-pull dsh-rm dsh-run

build:
	docker build -t registry.cmusatyalab.org/zf/diamond-public-registry/kinetic:arm .

push:
	docker push registry.cmusatyalab.org/zf/diamond-public-registry/kinetic:arm

pull:
	docker pull registry.cmusatyalab.org/zf/diamond-public-registry/kinetic:arm

dsh-pull:
	dsh -M -g kinetic docker pull registry.cmusatyalab.org/zf/diamond-public-registry/kinetic:arm

dsh-rm:
	dsh -M -g kinetic docker rm -f s3dexp-kinetic

dsh-run:
	dsh -M -g kinetic docker run  --net=host -d --name s3dexp-kinetic registry.cmusatyalab.org/zf/diamond-public-registry/kinetic:arm