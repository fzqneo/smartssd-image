Smart Disk for Machine Learning

s3d (previously "Smart SSD", now maybe "Somewhat Smart Spinning Disk"?)

**FAST'20 submission deadline: 9/26/2019**

![](fast20_arch.png)

## Todo

Emulated Storage:
- [ ] Create in-process storage emulator (as a Python module) (Edmond)
- [ ] Create communication stub using ZeroMQ and Protobuf (Haithem)
- [x] Implement emulated JPEG ASIC that scales decode time based on software decode time

TensorFlow Application:
- [ ] Profile MobileNet/Inception/ResNet inference + JPEG/PPM + GPU/CPU (Roger)
- [ ] Profile SSD_MobileNet/FasterRCNN_ResNet inference + JPEG/PPM + GPU/CPU (Shilpa)
- [ ] Compile TensorFlow with CPU optimization

Infrastructure:
- [x] Create cgroup for host and emulated disk
- [x] Store all images' meta info (file name, original file size, image size) to MySQL.
- [x] Add script to set up ram disk and populate it ppm data set
- [x] Use alembic to create experiment DB tables
- [x] Benchmark FS and RGB on PPM files
- [x] Profile times to read image bytes from disk
- [x] Profile software JPEG decode time

DiskSim:
- [ ] DiskSim 4.0 Manual (Edmond)

FUSE:
- [x] Use FUSE to map access to .jpg files to .ppm files
- [x] Modify FUSE: (1) Read .jpg from HDD; (2) Read .ppm from ram disk; (3) return PPM data

Data:
- [ ] Find or create a PNG data set
- [x] Convert and save image in PPM format

Literature survey:
- [ ] FAST papers 2005 - 2019. Keyword: smart disk, active disk, disk simulation/emulation (Edmond)
- [x] Reference numbers of ASIC for JPEG decoding (Shilpa)


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
* Jupyter notebook server: http://cloudlet015.elijah.cs.cmu.edu:8888 (ask me for password)


## Clearing OS page cache before running experiments

... if an experiment includes disk read times. For example:
```bash
make drop-cache
cgexec -g cpuset,memory:/s3dexphost python script/profile_mobilenet.py /mnt/hdd/fast20/jpeg/flickr2500
```

## Create a RAM disk to hold PPM files

```bash
make brd-up
# remove it
make brd-down
```

## Use cgroup to isolate resource of host applications and emulated disk
* cgroup for host: s3dexphost    (8 cores, 16g)
* cgroup for emulated disk: s3dexpdisk   (4 cores, 8g)

Executing a program under cgroup:
```bash
cgexec -g cpuset,memory:/s3dexphost python script/profile_mobilenet.py /mnt/hdd/fast20/jpeg/flickr2500 
```

## Running MKL-enabled TensorFlow on CPU (conda env: s3dexp-mkl)
Because CUDA and MKL cannot coexist in TensorFlow. I have to make two different conda envs.
```bash
conda deactivate
conda activate s3dexp-mkl
python ...
```


## Miscellaneous Notes

### cgroup
Limiting CPU and memory
```bash
sudo apt install cgroup-bin cgroup-lite cgroup-tools cgroupfs-mount libcgroup1

# create cgroup (users of group fast20 can create processes under the cgroup)
sudo cgcreate -t zf:fast20 -g cpuset,memory:/s3dexphost

# fix to cpu cores
sudo cgset -r cpuset.mems=0 s3dexphost
sudo cgset -r cpuset.cpus=0,1,2,3 s3dexphost
# fix memory upper limit
sudo cgset -r memory.limit_in_bytes=16g s3dexphost
```

Limiting block IO
```bash
sudo cgcreate -t zf:zf -g blkio:/s3dexp
# Find major and minor number by `cat /proc/partitions` or `ls -l /dev/sdc`
echo "8:32 482344960" | sudo tee /sys/fs/cgroup/blkio/s3dexp/blkio.throttle.read_bps_device
sudo cgexec -g blkio:/s3dexp hdparm -tT /dev/sdc
```

### scsi_debug

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

### ramdisk (brd)

```bash
# rd_nr is num of /dev/ramX created. Following will create a 4G (rd_size kB) ramdisk.
sudo modprobe brd rd_nr=1 rd_size=4194304 max_part=0
ls /dev/ram*
sudo mkfs /dev/ram0 4G
# remove the ram disk
# sudo rmmod brd
```

### I/O monitoring

```bash
iostat -x 1
```

### Upgrade Linux kernel version
scsi_debug + cgroup is buggy on kernel 4.4.0.
```bash
sudo apt install linux-image-4.15.0-54-generic linux-headers-4.15.0-54-generic linux-modules-extra-4.15.0-54-generic
# sudo reboot
```

### tfrecord
https://www.tensorflow.org/tutorials/load_data/tf_records#tfrecords_format_details

### OpenCV vs. PIL

JPEG decode (input in RAM): 

OpenCV (officitial `opencv`)  ~=  PIL ~= 210

OpenCV (unofficial `opencv-contribe-python`) = 350 (uses libjpeg-turbo)

`cv2.imread()` returns a numpy array of `.shape=(H, W, 3)`. `PIL.Image.open()` returns an `PIL.Image` object with attributes `.height`, `.width` and `.size`. Shell command `file` shows image size in `WxH` format.
