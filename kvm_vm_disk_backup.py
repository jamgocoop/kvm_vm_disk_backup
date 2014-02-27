#!/usr/bin/env python

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

from subprocess import Popen, PIPE, STDOUT
from libvirt import open, libvirtError
from xml.dom.minidom import parseString
from time import gmtime, strftime
from os import remove
from sys import exit

class BashCommandError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return 'ERROR executing '+repr(self.value)

def _execute_bash_command(command):
    ''' Executes a bash command an returns the output '''
    ps = Popen(command, shell=True, stdout=PIPE, stderr=STDOUT)
    output = ps.communicate()[0]
    if ps.returncode <> 0:
        raise BashCommandError(command)
    return output

def _log(string):
    ''' Outputs the string to specified media, by default stdout '''
    date_time = strftime("%d/%b/%Y %H:%M:%S", gmtime())
    print '%s - %s' % (date_time, string)

class LV:

    def __init__(self, lv_path = None, backup_path = None):
        ''' Class constructor '''
        self.lv_path = lv_path
        self.lv_path_backup = self.lv_path + '_backup'
        self.nicename = self.lv_path.split('/')[-1]
        self.nicename_backup = self.nicename + '_backup'
        self.vg_name = self._get_vg_name(self.lv_path)
        self.lv_path_backup_compressed = backup_path + '/' + self.nicename +\
                                         '.gz'
    def _get_lv_path(self, nicename):
        ''' Returns LV Path given a hint '''
        command = 'lvdisplay | grep Path | grep %s | egrep -v backup' %\
                 nicename
        try:
            output = _execute_bash_command(command)
        except BashCommandError as e:
            print e
            exit()
        return output.split(' ')[-1]

    def _get_vg_name(self, lv_path):
        ''' Returns LV Path given a hint '''
        try:
            output = _execute_bash_command(('lvdisplay %s | grep "VG Name"' %\
                                           lv_path))
        except BashCommandError as e:
            print e
            print 'Probably you need to execute this script as root'
            exit()
        return output.split(' ')[-1]

    def create_snapshot(self, size_gb):
        ''' Creates a LV snapshot of the given LV Path '''
        # It takes less than 1 second for a 8B LV
        command = 'lvcreate -s %s -L %sG -n %s' % (self.lv_path, size_gb,\
                  self.lv_path_backup)
        try:
            output = _execute_bash_command(command)
        except BashCommandError as e:
            print e
            print 'Either you are not root or the LV "%s" already exists'\
                  % self.lv_path_backup
            exit()

    def backup_snapshot(self, blocksize):
        ''' Copy the snapshot and compress it on the fly ''' 
        # It takes 2m48s for a 8B LV
        command = 'dd if=%s | gzip -c | dd of=%s bs=%s' % (\
                  self.lv_path_backup, self.lv_path_backup_compressed,\
                  blocksize)
        output = _execute_bash_command(command)

    def _remove_snapshot(self):
        ''' Removes the LV snapshot '''
        # It takes less than 1 second for a 8B LV
        command = 'lvremove -f %s' % self.lv_path_backup
        output = _execute_bash_command(command)

class  KvmVmDiskBackup:

    def __init__(self, vms = None, backup_path = None, lv_backup_size = 1,\
                 blocksize = 4096):
        ''' Class constructor '''
        try:
            self.conn = open("qemu:///system")
        except libvirtError:
            print ('ERROR: user should belong to libvirt group and this '
                   'script needs to be run from the hypervisor host')
        self.vms = vms
        self.backup_path = backup_path
        self.lv_backup_size = lv_backup_size
        self.blocksize = blocksize

    def _get_disk_source(self, virDomain):
        ''' Returns a list with VM disk source '''
        disk_source = []
        xml = virDomain.XMLDesc() 
        dom = parseString(xml)
        disks = dom.getElementsByTagName('disk')
        for disk in disks:
            disk_source.append(disk.getElementsByTagName('source').item(0).\
                             toxml().split('"')[1].strip())
        return disk_source

    def backup(self):
        ''' Performs a backup of all the disks of the list of VMS '''
        for vm_name in self.vms:
            _log('Backing up VM %s' % vm_name)
            virDomain = self.conn.lookupByName(vm_name)
            for disk_source in self._get_disk_source(virDomain):
                _log('Backing up disk %s' % disk_source)
                lv = LV(lv_path = disk_source, backup_path = self.backup_path)
                # Let's check if there's enough space. At least 1GB
                if self._get_free_space(self.backup_path) >= self.lv_backup_size:
                    _log('Creating snapshot %s' % lv.nicename_backup)
                    lv.create_snapshot(self.lv_backup_size)

                    _log('Backing up snapshot %s to %s' % (\
                          lv.nicename_backup, lv.lv_path_backup_compressed))
                    # Once snapshot is created it starts decreasing LV performance
                    lv.backup_snapshot(self.blocksize)

                    if self._is_snapshot_full(lv.nicename_backup):
                        _log(('ERROR: snapshot %s is full. Starting'
                               ' rollback' % lv.nicename_backup))
                        remove(lv.lv_path_backup_compressed)
                    else:
		        _log('Removing snapshot %s' % lv.nicename_backup)
                    lv._remove_snapshot()

    def _get_free_space(self, path):
        ''' Returns the remaining space in GB of a path '''
        output = _execute_bash_command('df -kh %s | grep /' % path)
        return int(output.strip().split('G')[2].strip())

    def _get_lv_snapshot_fullness(self, lv_name):
        ''' Returns Data% column of the given LV '''
        command = 'lvs | grep %s' % lv_name

        return float(_execute_bash_command(command).strip().split(' ')[-1].\
                split('g')[0].strip())

    def _is_snapshot_full(self, lv_name):
        ''' Checks if the Data% of the snapshot is less than 100 '''
        # If Data% = 100 backup will not work, let's roll it back       
        if self._get_lv_snapshot_fullness(lv_name) < 100:
            return False
        return True

    def _restore_snapshot(self):
        ''' Restores the compressed backup of the LV snapshot '''
        # dd if=/srv/no_data/lv_test_2_backup.gz | gzip -c -d | dd of=/dev/vg/lv_test_2
        pass

    def _rollback_lv_snapshot(self):
        ''' Removes the snapshot backup and the LV with the snapshot '''
        pass

