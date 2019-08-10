# smartssd-image
Smart SSD image processing


## Todo

- [ ] Store all images' meta info (file name, original file size, image size) to MySQL.
- [ ] Convert and save image in PPM format
- [ ] Benchmark FS and RGB on PPM files
- [ ] Use FUSE to map access to .jpg files to .ppm files


## Running FUSE

```
# build
cd fuse
./configure
make

# mount
src/bbfs $FUSE_ROOTDIR $FUSE_MOUNTDIR

# un-mount
fusermount -u $FUSE_MOUNTDIR
```


## cgroup

```bash
sudo apt install cgroup-bin cgroup-lite cgroup-tools cgroupfs-mount libcgroup1

sudo cgcreate -t zf:zf -g blkio:/s3dexp
# Find major and minor number by `cat /proc/partitions` or `ls -l /dev/sdc`
echo "8:32 482344960" | sudo tee /sys/fs/cgroup/blkio/s3dexp/blkio.throttle.read_bps_device
sudo cgexec -g blkio:/s3dexp hdparm -tT /dev/sdc
```

## scsi_debug

Set `ndelay=1` to have almost-zero delay. Don't set it to 0. It will disable the parameter.

```bash
# see all parameters and meanings
# modinfo scsi_debug
sudo modprobe scsi_debug num_parts=1 dev_size_mb=4096 delay=1
lsscsi -s   # show device name
sudo mkfs.ext4 /dev/sdc1
sudo mount /dev/sdc1 /mnt/scsi_drive
sudo hdparm -tT /dev/sdc1

# change parameters at run time
echo 310000 | sudo tee /sys/bus/pseudo/drivers/scsi_debug/ndelay

# remove the virtual disk
# sudo umount /mnt/scsi_drive
# sudo rmmod scsi_debug

# check module parameters (rw or ro)
ls -l /sys/bus/pseudo/drivers/scsi_debug

```

## ramdisk (brd)

```bash
# rd_nr is num of /dev/ramX created. Following will create a 4G (rd_size kB) ramdisk.
sudo modprobe brd rd_nr=1 rd_size=4194304 max_part=0
ls /dev/ram*
sudo mkfs /dev/ram0 4G
# remove the ram disk
# sudo rmmod brd
```

## monitoring

```bash
iostat -x 1
```

## Upgrade Linux Kernel Version
scsi_debug + cgroup is buggy on kernel 4.4.0.
```bash
sudo apt install linux-image-4.15.0-54-generic linux-headers-4.15.0-54-generic linux-modules-extra-4.15.0-54-generic
# sudo reboot
```

### OpenCV vs. PIL

JPEG decode (input in RAM): 

OpenCV (officitial `opencv`)  ~=  PIL ~= 210

OpenCV (unofficial `opencv-contribe-python`) = 350 (uses libjpeg-turbo)
