#!/bin/bash

LOG_OUTPUT=/var/log/prep_migrate.log

if [ -f /etc/os-release ]; then
    . /etc/os-release
    distro=$ID
    distro_like=$ID_LIKE
else
    echo "Operating system could not be detected."
    exit 1
fi

if [[ "$distro" == "debian" || "$distro_like" =~ "debian" ]]; then
    echo "Detected Debian-based operating system."
    if [ -d "/boot/efi" ]; then
        grub-install --efi-directory=/boot/efi --bootloader-id=boot --removable 2>&1 | tee $LOG_OUTPUT
        echo "Fix EFI boot"
    fi

    if ! grep -q "net.ifnames=0 biosdevname=0" /etc/default/grub; then
        cp /etc/default/grub /etc/default/grub.bak_$(date +%F_%T)
        sed -i 's/^GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="net.ifnames=0 biosdevname=0"/' /etc/default/grub
        update-grub 2>&1 | tee $LOG_OUTPUT
    fi

elif [[ "$distro" == "fedora" || "$distro_like" =~ "rhel" ]]; then
    echo "Detected Red Hat-based operating system."
    if [ ! -e /etc/dracut.conf.d/virtio.conf ]; then
        cat <<EOF > /etc/dracut.conf.d/virtio.conf
add_drivers+=" virtio_blk "
EOF
    dracut -f --regenerate-all 2>&1 | tee $LOG_OUTPUT
    echo "Fix VIRTIO driver" 2>&1 | tee $LOG_OUTPUT
    fi

    if ! grep -q "net.ifnames=0 biosdevname=0" /etc/default/grub; then
        cp /etc/default/grub /etc/default/grub.bak_$(date +%F_%T) 2>&1 | tee $LOG_OUTPUT
        sed -i '/^GRUB_CMDLINE_LINUX=/ s/"$/ net.ifnames=0 biosdevname=0"/' /etc/default/grub 2>&1 | tee $LOG_OUTPUT
        grub2-mkconfig -o /boot/grub2/grub.cfg 2>&1 | tee $LOG_OUTPUT
    fi

    grubby --update-kernel=ALL --args="net.ifnames=0 biosdevname=0"  | tee $LOG_OUTPUT
else
    echo "Operating system could not be detected."
    exit 1
fi