# smartssd-image
Smart SSD image processing

## scsi_debug

```bash
sudo modprobe scsi_debug num_parts=1 dev_size_mb=4096 delay=0
sudo mkfs.ext4 /dev/sdc1
sudo mount /dev/sdc1 /mnt/scsi_drive
sudo hdparm -tT /dev/sdc1
```

## cgroup

```bash
sudo apt-get install cgroup-bin cgroup-lite cgroup-tools cgroupfs-mount libcgroup1

sudo cgcreate -t zf:zf -g blkio:/s3dexp
echo "8:32 400000000" | sudo tee /sys/fs/cgroup/blkio/s3dexp/blkio.throttle.read_bps_device
sudo cgexec -g blkio:/s3dexp hdparm -tT /dev/sdc
```