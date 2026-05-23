#!/bin/bash
echo "Installing GameCube adapter udev rules..."
sudo tee /etc/udev/rules.d/51-gcadapter.rules << 'RULES'
# Allow non-root users to access the Mayflash GC adapter in Wii U mode
# (idVendor 057e = Nintendo, idProduct 0337 = Wii U GameCube Adapter)
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="0337", MODE="0666"

# Unbind the kernel's usbhid driver from the adapter when it is connected
# This is required so the app can access it directly via libusb
# %k is replaced by the kernel device name at runtime
SUBSYSTEM=="usb", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="0337", DRIVER=="usbhid", RUN+="/bin/sh -c 'echo -n %k > /sys/bus/usb/drivers/usbhid/unbind'"
RULES
sudo udevadm control --reload-rules && sudo udevadm trigger
echo "Done. Unplug and replug your adapter, then run gc_gui_controller_tester.py or gc_cli_controller_tester.py."
