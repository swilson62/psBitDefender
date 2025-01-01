#!/usr/bin/env python
"""
###################################################################################################
This file is part of `PS BitDefender`.

`PS BitDefender` is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

`PS BitDefender` is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with PS BitDefender. If not, see
<https://www.gnu.org/licenses/>.  
###################################################################################################

Program Name: PS BitDefender

psBitDefender.py: Python script to provide adaptive top listing for BitDefender tasks.

changeLog(v1.15.06):
- v1.15: Removed old thoughts.
- Added GPL licensing requirements.
- Fixed hard coded log file to use CWD.
- Fixed hard coded log file to use
`/home/swilson/Documents/Coding/Python/psBitDefender/psBitDefender.log`.
- On upgrade to UBuntu Studio, new BD version loads 6 processes. Updated checks for this.
- Updated logging output to reflect this when check fails.
- Discovered on 12/29/24 that BD now loads 5 processes. Update checks & logging output.
- Reworked code to get num of processes from `psCnt=` line in `psBD.cfg` file.
- Moved psCnt code into BdProc object to avoid having to pass it around so much.
- Moved myTop into the bdProc object to simplify working with it.
- Added code to reconfigure default number of processes should `self.psCntLoopFailCnt` exceed 20.


Thoughts:
- Need to add code to copy log to an archive file and create new log file at 100k. Should make the
copy overwrite preexisting files, since 100k is enough to last well over 7 months, maybe a year.
- Moved to another directory, and suddenly logging now fails. Cannot understand why. Probably
something stupid and simple. Problem was caused by running program from the command line in `~/`.
Fixed temporarily by hardcoding CWD to be directory script is in. Might consider logging to
`/var/log`, but that requires root permissions, or maybe using rsyslogd logging service.
- Should probably re-write to determine the correct number of processes on start. One way to do
this would be to have a default number of processes that only get changed if it takes longer than
say 30 seconds for myTop to load. Having an incorrect default results in this. Default might need
to survive script restart. To change, run getPids() without # of processes restriction, & save
number as default. Just keep re-running this until it stabilizes.
- Code required to get pcCnt from `psBD.cfg file added. Code to update default config saved in
config file whenever number of processes change still needs to be added.
- The way I came up with to write new config to file was similar to:
    with open('psBD.cfg', 'a')
        for i in len(cfgList)
            cfgFile.write(f'{list(cfgDict.items())[i][0]}={list(cfgDict.items())[i][1]}')
If the psCnt changes from default, the `if len(self.bdProcs) != self.psCnt:` check will loop
forever. Adding variable to count fails, rewrite psCnt both to memory & cfg file after 20 fails, &
bailing might work to fix.
- `v1.15.06` has it working correctly when process is popped of the list. Fails on start when psCnt
default is < actual number pf processes. Probably need to rewrite getPids and getAllPids (possibly
by combining them) so that the iteration of processes is limited by psCnt unless the default has
changed. This is sort of going back to the way it worked except on change.
    

Attributions:
- 

"""

# Imports
import psutil, time, logging, os


class BdProc(object):
    """
    Represents bdsecd processes & top listing of same
    """
    def __init__(self):
        """Initialize BdProc object list of processes"""
        self.bdProcs = []
        self.currBdProcs = []

        # Get config & init config vars
        self.cfgDict = {}
        with open('psBD.cfg', 'r') as cfgFile:
            for line in cfgFile.readlines():
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    self.cfgDict[key] = value

        self.psCnt = int(self.cfgDict['psCnt'])
        self.psCntLoopFailCnt = 0

    def getAllPids(self):
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] == 'bdsecd':
                self.bdProcs.append(proc.info['pid'])
    
    def getPids(self):        
        """ 
        Returns PIDs used by bdsecd processes.
        Obtain bdsecd pids, verify 5 pids, list in bdProcs, & return bdProcs
        """
        self.bdProcs = []

        # Populate self.BdProc with default number of processes
        while len(self.bdProcs) != self.psCnt:
            self.getAllPids()

            # If number of processes not matching default, keep trying
            if len(self.bdProcs) != self.psCnt:
                logging.debug('Number of BD processes incorrect. Will retry `getPids()`.')
                self.bdProcs = []
                self.psCntLoopFailCnt += 1
                
                # More than 20 failures probably means change in default
                if self.psCntLoopFailCnt >= 2:
                    self.getAllPids()
                    self.psCnt = len(self.bdProcs)
                    self.cfgDict['psCnt'] = self.psCnt

                    with open('psBD.cfg', 'w') as cfgFile:
                        for i in range(len(self.cfgDict)):
                            cfgFile.write(f'{list(self.cfgDict.items())[i][0]}={ \
                                list(self.cfgDict.items())[i][1]}\n')

                    logging.debug('Change in default number of processes required.')
                    self.psCntLoopFailCnt = 0
                
                # Less than 20 probably means update not finished loading
                self.psCntLoopFailCnt = 0
                #time.sleep(3)

    def spawnTop(self):
        """
        Spawn `top` as child to display all bdsecd process details & return that var for control
        """

        # Create topCmd list, populate processes, & load top
        topCmd = ['top']
        for i in range(self.psCnt):
            topCmd.append(f'-p {self.currBdProcs[i]}')

        self.myTop = psutil.Popen(topCmd)

    def reSpawnTop(self):
        """
        Re-Spawn 'top' as child & return var as needed when processes change during upgrades
        """
        #time.sleep(5)  # If removed for testing, don't forget to re-enable (causes high CPU!!!)
        self.getPids()
        
        # Check for pid changes. If failures,  terminate with timeout or returncode checks.
        if self.bdProcs != self.currBdProcs:
            self.myTop.terminate()
            logging.info('Change in BD processes detected. TOP instance terminated')
            try:
                self.myTop.wait(timeout=2)
            except psutil.TimeoutExpired:
                """ Old logging code
                logging.debug('TOP instance timed out while waiting for termination.')
                """

                #""" This might be better:
                logging.debug('TOP instance timed out while waiting for termination (extSts= ' \
                        + psutil.Process(self.myTop.pid).status() + ').')
                #"""
                
                print('\nProcess TOP was asked to terminate, but timeout expired while waiting.')
                print('\nCurrent process status of TOP on exit was: ' \
                      + psutil.Process(self.myTop.pid).status() + '.')
               
                exit()
            
            if self.myTop.returncode != 0:
                logging.debug('Unusual TOP return code of (' + str(myTop.returncode) +
                              ') causing exit.')
                
                print('\nTOP exited with unusual return code of (' + str(myTop.returncode) + ').')
                print('\nSee `https://psutil.readthedocs.io/en/latest/#psutil.Process.wait` ' \
                      'for details.\n')
                exit()
            
            # If checks pass, copy bpProcs to currBdProcs & spawn new top
            self.currBdProcs = self.bdProcs.copy()
            self.spawnTop()
            logging.info('TOP has been re-initialized showing new BD processes.')


def main():
    # Intialize logging
    os.chdir('/home/swilson/Documents/Coding/Python/psBitDefender/')
    logFilePathName = os.getcwd() + '/psBitDefender.log'
    if (os.path.exists(logFilePathName)) and (os.path.getsize(logFilePathName) > 100000):
        os.remove(logFilePathName)
    
    logging.basicConfig(filename=logFilePathName, format='%(asctime)s <%(levelname)s>: %(message)s',
                        datefmt='%b %d %H:%M:%S', level=logging.DEBUG)
    logging.info('The `psBitDefender.py` script was initialized.')

    # Initialize BdProc instance, & populate process lists
    bdProc = BdProc()
    bdProc.getPids()
    bdProc.currBdProcs = bdProc.bdProcs.copy()

    # Spawn top to monitor bdsecd processes
    bdProc.spawnTop()
    logging.info('Initial TOP instance started.')

    try:
        while True:
            # Check for changes to pids & re-spawn as needed
            bdProc.reSpawnTop()

    except KeyboardInterrupt:
        # End while loop & kill myTop with keyboard interrupt
        bdProc.myTop.terminate()
        logging.info('The `psBitDefender.py` script terminated by keyboard interrupt.')
        print('Caught keyboard interrupt.')
        exit()


if __name__ == '__main__':
    main()
