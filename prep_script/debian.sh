#!/bin/bash

LOG_OUTPUT=/var/log/prep_migrate.log

if [ -d "/boot/efi" ]; then
    grub-install --efi-directory=/boot/efi --bootloader-id=boot --removable 2>&1 | tee $LOG_OUTPUT
    echo "Fix EFI boot"
fi

if grep -q '^GRUB_CMDLINE_LINUX=""' /etc/default/grub; then
    cp /etc/default/grub /etc/default/grub.bak_$(date +%F_%T)
    sed -i 's/^GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="net.ifnames=0 biosdevname=0"/' /etc/default/grub
    update-grub 2>&1 | tee $LOG_OUTPUT
fi
