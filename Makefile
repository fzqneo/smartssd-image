
docker:
	nvidia-docker build -t smartssd .

install:
	python setup.py install && rm -rf build dist s3dexp.egg-info .eggs
	
db-up:
	docker-compose up -d

db-backup:
	docker exec s3dexp-db /usr/bin/mysqldump -u root --password=${DB_PASSWORD} --all-databases > /mnt/ssd2/fast20-mysql-bk/backup-$$(date +%Y%m%d).sql

detection-up:
	docker run --gpus all --cpuset-cpus="11-14" --name s3dexp-detection -p 5000:5000  -d registry.cmusatyalab.org/zf/diamond-public-registry/filter/service@sha256:2baa7250498fb06913ef9902ec54272b7a2a6a7244f01b015fb1d0a7ce801d0f ssd_mobilenet_coco

detection-down:
	docker rm -f s3dexp-detection

ramfs-up:
	@(if [ ! -z "$(shell mount | grep /mnt/ramfs )" ]; then \
		echo "ramfs already up: $(shell mount | grep /mnt/ramfs)" >&2; \
	else \
		sudo mount -t ramfs -o size=16g ramfs /mnt/ramfs && echo "Created ramfs"; \
		sudo rsync -a --stats /mnt/hdd/fast20/ppm /mnt/ramfs/fast20/; \
	fi)

ramfs-sync:
	sudo rsync -a --stats /mnt/hdd/fast20/ppm /mnt/ramfs/fast20/;

ramfs-down:
	sudo umount /mnt/ramfs


drop-cache:
	sync; echo 1 | sudo tee /proc/sys/vm/drop_caches
	
no-turbo:
	echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo

cgroup-recreate:
	sudo cgdelete -g cpuset,memory:/s3dexphost || true
	sudo cgcreate -t zf:fast20 -g cpuset,memory:/s3dexphost
	sudo cgset -r cpuset.mems=1 s3dexphost
	sudo cgset -r cpuset.cpus=18-35 s3dexphost
	sudo cgset -r memory.limit_in_bytes=62g s3dexphost
	# sudo cgdelete -g cpuset,memory:/s3dexpdisk || true
	# sudo cgcreate -t zf:fast20 -g cpuset,memory:/s3dexpdisk
	# sudo cgset -r cpuset.mems=1 s3dexpdisk
	# sudo cgset -r cpuset.cpus=18-35 s3dexpdisk
	# sudo cgset -r memory.limit_in_bytes=32g s3dexpdisk


# fuse-build:
# 	(cd fuse; make)

# fuse-up: fuse-build brd-up
# 	@(if [ ! -z "$(shell mount -t fuse.bbfs)" ]; then \
# 		echo "fuse.bbfs already up at $(shell mount -t fuse.bbfs) !" >&2; exit 1; \
# 	fi)
# 	fuse/src/bbfs /mnt/ramdisk/ $(FUSE_MOUNTDIR)
	
# fuse-down:
# 	fusermount -u $(FUSE_MOUNTDIR)


# brd-up:
# 	@(if [ ! -z "$(shell find /dev -type b -name 'ram*' )" ]; then \
# 		echo "ramdisk already up at $(shell find /dev -type b -name 'ram*' ) !" >&2; \
# 	else \
# 		sudo modprobe brd rd_nr=1 rd_size=67108864 max_part=0; \
# 		sudo mkfs /dev/ram0 64G; \
# 		sudo mount /dev/ram0 /mnt/ramdisk; \
# 		sudo rsync -a --stats /mnt/hdd/fast20/ /mnt/ramdisk; \
# 	fi)

# brd-down:
# 	sudo umount /mnt/ramdisk
# 	sudo rmmod brd
