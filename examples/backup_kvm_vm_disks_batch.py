#us/bin/python

'''
    Copyright 2013 Jamgo S.C.C.L. info@jamgo.es

    kvm_vm_disk_backup is free software: you can redistribute it and/or
    modify it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
'''

backup_path = '/srv/data/backups/vms_disks'

# TODO: use libvirt API to lookup VM name to LV path
vms = (
    'vm-1.example.com',
    'vm-2.example.com',
)

from kvm_vm_disk_backup import KvmVmDiskBackup

k = KvmVmDiskBackup(vms = vms, backup_path = backup_path)
k.backup()
