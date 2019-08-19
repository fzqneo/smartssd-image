# smartssd-image
Smart SSD image processing

**FAST'20 submission deadline: 9/26/2019**

## Todo

- [x] Store all images' meta info (file name, original file size, image size) to MySQL.
- [x] Convert and save image in PPM format
- [x] Benchmark FS and RGB on PPM files
- [x] Use FUSE to map access to .jpg files to .ppm files
- [x] Add script to set up ram disk and populate it ppm data set
- [x] Modify FUSE: (1) Read .jpg from HDD; (2) Read .ppm from ram disk; (3) return PPM data
- [x] Use alembic to create experiment DB tables
- [x] Profile times to read image bytes from disk
- [ ] Profile image decode time in MobileNet/ResNet/Faster-RCNN inference
- [ ] Determine three (labeled) data sets to be used in the paper
- [ ] Determine 3~4 DNN models to be used in the paper


## Experiment Infrastructure

* cloudlet015.elijah.cs.cmu.edu (limited to CMU IP)
* User group: fast20 (Run `newgrp fast20` to change login group)
* Data: /mnt/hdd/fast20/

* MySQL DB for storing results
    * Web UI: http://cloudlet015.elijah.cs.cmu.edu:8081/
    * Credentials: /home/zf/git/smartssd-image/.envrc
    * Access DB in Python (see [script/profile_data.py](script/profile_data.py) for example): 
    ```python
    import s3dexp.db.utils as dbutils
    import s3dexp.db.models as models
    ``` 
* Conda environment (s3dexp)
    1. Install miniconda
    2. Add the following to `~/.condarc`:
    ```
    envs_dirs:
        - /home/zf/miniconda2/envs
    ```
    3. Activate: `conda activate s3dexp`
    4. Install changes of Python code to conda env: `make install`

## Running our custom FUSE on top of ram disk

```bash
make fuse-up    # will call `make brd-up`

# tear down
make fuse-down  # only unmount the FUSE; ram disk persists
# or:
make fuse-down brd-down   # this tears down the ram disk too
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

Set `ndelay=1` to have almost-zero nanoseconds delay. Don't set it to 0. It will disable the parameter.

```bash
# to see all parameters and meanings: modinfo scsi_debug
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
