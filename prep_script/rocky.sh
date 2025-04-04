#!/bin/bash

LOG_OUTPUT=/var/log/prep_migrate.log

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
