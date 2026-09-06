#!/sbin/sh

### AnyKernel3 Flashable Kernel Script
## Adapted for Xiaomi Mi 11 Ultra (star)

properties() { '
kernel.string= 5.4.302-ikun-NekoMake-star-qgqi for Xiaomi 11 Ultra
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=star
device.name2=mars
device.name3=
device.name4=
device.name5=
supported.versions=
supported.patchlevels=
supported.vendorpatchlevels=
'; } # end properties

# boot shell variables
BLOCK=boot;
IS_SLOT_DEVICE=1;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

# import functions/variables and setup patching - do not remove
. tools/ak3-core.sh;

# pure kernel swap: keep the existing ramdisk and repack with the new Image.gz
split_boot;
flash_boot;
