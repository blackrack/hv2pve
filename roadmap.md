## Roadmap

### Features Planned for Future Releases

- Project refactoring and implementation of a dedicated Service Layer
- Support for Production Checkpoints
- Ability to resume import after a failure
- Automatic cleanup of VM and storage after a failed import
- Automatic selection of the appropriate datastore for each VM disk in PVE (no manual disk-to-storage binding required)
- Automatic shutdown of the VM on Hyper-V after migration (with or without user interaction)
- Migration of block devices / iSCSI
- Migration of a Hyper-V cluster to a PVE cluster with automatic VM placement
- Migration of Parallels virtual machines
- VM disk transfer via NFS and SSH
- Generic EFI support
- Web GUI for migration management (progress monitoring, configuration, error handling)