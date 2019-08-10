#!/bin/bash

MOUNT_POINT=/mnt/scsi_drive

set -e

scsi__help() {
    echo "Helper to create/destroy virtual SCSI disk using scsi_debug kernel module."
}

scsi__hello() {
    echo "Hello world."
}

scsi__find_scsi_device() {
    echo $(lsscsi | grep scsi_debug | tr -s '[:blank:]' | cut -d' ' -f6)
}

scsi__setup() {
    device=$(scsi__find_scsi_device)
    [ -z "$device" ] || (echo "A scsi_debug drive is already in place: $device" >&2 && exit 1)
    sudo modprobe scsi_debug num_parts=1 dev_size_mb=8192 ndelay=1  # create an 8GB ramdisk
    device=$(scsi__find_scsi_device)
    echo "Created scsi_debg at $device" >&2
    sudo mkfs.ext4 ${device}1
    sudo mkdir -p $MOUNT_POINT
    sudo mount ${device}1 $MOUNT_POINT
    echo "Preparing files" >&2
    sudo rsync -a --stats /srv/diamond/flickr2500 $MOUNT_POINT
}

scsi__teardown() {
    device=$(scsi__find_scsi_device)
    [ ! -z "$device" ] || (echo "No scsi_debug device found." >&2 && exit 1)
    echo "umount'ing" >&2; sudo umount $MOUNT_POINT
    echo "rmmod'ing" >&2; sudo rmmod scsi_debug
}

subcommand=$1
case $subcommand in
    "" | "-h" | "--help")
        scsi__help
        ;;
    *)
        shift
        scsi__$subcommand $@
        if [ $? = 127 ]; then
            echo "Error: unknown subcommand $subcommand" >&2
        fi
        ;;
esac