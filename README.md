Smart Disk for Visual Data Analytics

s3dexp (previously "Smart SSD", now maybe "Somewhat Smart Spinning Disk"?)

Cloning: `git clone --recursive git@github.com:fzqneo/smartssd-image.git`

https://anonymous.4open.science/r/866346b2-db04-4beb-a636-a26b3551092e/

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
    4. Install changes of Python code to conda env: `make install` (if you've changed group, you don't need sudo).
* Jupyter notebook server: http://cloudlet015.elijah.cs.cmu.edu:8888 (ask me for password)


## Run Video Search
```bash
# The script is specific to frame skipping + image difference detection [+ object detection]
python script/video_search.py --every_frame=10 --expname=baseline_videodiff-every10 --num_workers=8
# To run with emulated smart disk
make ramfs-down # destroy ramfs for image data
make video-ramfs-up

# Macro benchmark
make frcnn-up # for human detection
make drop-cache # before each run
python script/video_search.py /mnt/hdd/fast20/video/VIRAT/mp4/VIRAT_S_000200_02_000479_000635.mp4 --every_frame=10  --detect --num_workers=8  --expname=macro-pedestrian-hdd
python script/video_search.py /mnt/ssd/fast20/video/VIRAT/mp4/VIRAT_S_000200_02_000479_000635.mp4 --every_frame=10  --detect --num_workers=8 --expname=macro-pedestrian-ssd
# smart emulator beforehand
python script/video_search.py /mnt/hdd/fast20/video/VIRAT/mp4/VIRAT_S_000200_02_000479_000635.mp4 --every_frame=10  --detect --num_workers=8 --smart --expname=macro-pedestrian-smart
```

## Run Image Macro Benchmarks
Red bus and Obama.
```bash
make ramfs-up

# start emulated storage in another terminal

make drop-cache # before each
python script/search_driver.py workload/baseline_redbus.yml /mnt/hdd/fast20/jpeg/flickr50k --expname=macro-redbus-hdd --store_result=True
python script/search_driver.py workload/baseline_redbus.yml /mnt/ssd/fast20/jpeg/flickr50k --expname=macro-redbus-ssd --store_result=True
# start emulator beforehand
python script/search_driver.py workload/smart_redbus.yml /mnt/hdd/fast20/jpeg/flickr50k --expname=macro-redbus-smart --sort_fie=True --store_result=True
```

## Run ResNet10
```bash
python script/run_resnet10.py /mnt/hdd/fast20/jpeg/flickr50k --batch_size=64
```

### Start the Emulated Smart Disk
```bash
# in a separate terminal, run this first
python s3dexp/sim/storage.py --base_dir=/mnt/hdd/fast20/jpeg/flickr2500
# after "======READY" shows up, start the search_driver
python script/search_driver.py ...
```

## Change DB Schema (Adding tables, columns, etc.)

1. Update [s3dexp/db/models.py](s3dexp/db/models.py)
2. `make install`
3. `alembic revision --autogenerate -m "Some message here"`
4. Check the auto-generated file alembic/versions/xxxxxx_xxxxxxxxx.py
5. `alembic upgrade head` -- this will actually update the DB schema
6. git add alembic/versions/xxx.py


## Create a ramfs to hold PPM files of decoded JPEG or video frames

```bash
# for image data
make ramfs-up
# for video data
make video-ramfs-up
# remove it
make ramfs-down
```

## Running TensorFlow batch inference
```bash
python script/profile_mobilenet_batch.py /mnt/hdd/fast20/jpeg/flickr2500  --batch_size=64 
```

## Run programs under cgroup to isolate resource
* cgroup for host: s3dexphost    (8 cores, 16g)
* cgroup for emulated disk: s3dexpdisk   (4 cores, 8g)

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

### ResNet10 on GTX 1080 Ti
|Batch size | ms / image |
| --- | --- |
| 64 | 0.099 |
|128 | 0.063 |
|256 | 0.049 |
|512 | 0.024 |

It means > 40,000 images / sec.

### Face in YFCC100M

23\% images have face. Average face 97x127 pixels.

### Macro Benchmark Params and Stats

#### Red Bus
Selectivity: total 50629, red 1170 (2.3%), bus 5 (0.001%)  
```yml
filters:
  -
    filter: SimpleReadFilter
  -
    filter: DecodeFilter
  -
    filter: ColorFilter
    kwargs:
      bgr_lb: [0, 0, 180]
      pixels_threshold: 5000
  -
    filter: ObjectDetectionFilter
    kwargs:
      targets: ["bus"]
      confidence: 0.8
```

#### Obama
Selectivity: total 45891, face ???, Obama 2 (0.004%)
```yml
filters:
  -
    filter: SimpleReadFilter
  -
    filter: DecodeFilter
  -
    filter: FaceDetectorFilter
  -
    filter: ObamaDetectorFilter
    kwargs:
      tolerance: 0.5
```

#### Pedestrian
Selectivity: 20655 (frames), frame skipping (10%), image difference ???, human 508 (2.45%)


### ffmpeg

```bash
# split video into frames
ffmpeg -i video1.mp4 video1/%06d.jpg -hide_banner
# also works for %06d.ppm
```

### Coordinate systems

* OpenCV `cv2.imread` returns (H, W, 3)
* OpenCV face detection uses (left, top, right, bottom), namely (StartX, StartY, EndX, EndY). Note: in OpenCV's X-Y system, X is along the width (the second dimension), Y is along the height (the first dimension).
* face_recognition's `face_recognition.face_locations()` returns (top, right, bottom, left)
* TensorFlow's Object Detection API uses (top, left, bottom, right), and it's normalized between 0 and 1.0


### TensorFlow

* tfrecord: https://www.tensorflow.org/tutorials/load_data/tf_records#tfrecords_format_details
* Example of batching with tf.data.Dataset in eager mode: https://www.tensorflow.org/tutorials/load_data/images
* tf.data.Dataset version 1.13 Doc: https://www.tensorflow.org/versions/r1.13/api_docs/python/tf/data/Dataset
* Data input pipeline performance optimization: https://www.tensorflow.org/guide/performance/datasets
* Installing TF: `sudo apt-get install libcuda1-410` in addition to following the [website](https://www.tensorflow.org/install/gpu#linux_setup)

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


### OpenCV vs. PIL

JPEG decode (input in RAM): 

OpenCV (officitial `opencv`)  ~=  PIL ~= 210

OpenCV (unofficial `opencv-contribe-python`) = 350 (uses libjpeg-turbo)

`cv2.imread()` returns a numpy array of `.shape=(H, W, 3)`. `PIL.Image.open()` returns an `PIL.Image` object with attributes `.height`, `.width` and `.size`. Shell command `file` shows image size in `WxH` format.

## Todo

Emulated Storage:
- [x] Add emulated video decoder (Edmond)
- [x] Add emulated face detector ASIC (Edmond)
- [x] Store pre-computed face boxes in DB for emulation (Shilpa)
- [x] Emulated smart storage client side (Edmond)
- [x] Client/Server communication between application and emulated storage over 0MQ+ipc:// (Haithem)
- [x] Basic simulator framework using SimPy (Edmond)
- [x] Create communication stub using ZeroMQ and Protobuf (Haithem)
- [x] Implement emulated JPEG ASIC that scales decode time based on software decode time

Applications:
- [x] Improve object detection DNN efficiency on GPU. Maybe batching (Edmond)
- [ ] Find a few more filters from related papers
- [x] Macro benchmarks
- [x] Create MobileNet filter (that connects to a web service) (Edmond)
- [x] Add face detection filter (Shilpa)
- [x] RGB hist 2D filter, background subtraction filter, perceptual hashing filter (Shilpa)
- [x] Simple file reader, OpenCV decoder, and RGB hist 1D as filters (Edmond)
- [x] Simple Eureka-ish filtering framework (Edmond)
- [x] RGB color histogram (Edmond)

TensorFlow Application:
- [x] Use Active Disk in 10-layers ResNet (Edmond)
- [x] 10-layer ResNet. Refer to [BlazeIt](https://arxiv.org/abs/1805.01046) (Roger)
- [x] MobileNet inference (Edmond)
- [x] Create batching example using tf.data.Dataset (Edmond)
- [x] Install MKL-enabled TensorFlow

Infrastructure:
- [x] Create cgroup for host and emulated disk
- [x] Store all images' meta info (file name, original file size, image size) to MySQL.
- [x] Add script to set up ram disk and populate it ppm data set
- [x] Use alembic to create experiment DB tables
- [x] Benchmark FS and RGB on PPM files
- [x] Profile times to read image bytes from disk
- [x] Profile software JPEG decode time

DiskSim:
- [ ] Create Protobuf for communication with syssim
- [x] Compile and run syssim (Edmond)
- [x] DiskSim 4.0 Manual (Edmond)

FUSE:
- [x] Use FUSE to map access to .jpg files to .ppm files
- [x] Modify FUSE: (1) Read .jpg from HDD; (2) Read .ppm from ram disk; (3) return PPM data

Data:
- [x] Transcode Flickr2500 JPEG to PNG
- [x] Convert and save image in PPM format

Literature survey:
- [ ] Reference numbers of ASIC for PNG decoding
- [x] Reference numbers of video decoding hardware
- [x] Reference numbers of ASIC for face detection
- [x] FAST papers 2005 - 2019. Keyword: smart disk, active disk, disk simulation/emulation (Edmond)
- [x] Reference numbers of ASIC for JPEG decoding (Shilpa)
