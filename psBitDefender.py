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

changeLog(v1.15-beta03):
- v1.15: Removed old thoughts.
- Added GPL licensing requirements.
- Fixed hard coded log file to use CWD.
- Fixed hard coded log file to use
`/home/swilson/Documents/Coding/Python/psBitDefender/psBitDefender.log`.
- On upgrade to UBuntu Studio, new BD version loads 6 processes. Updated checks for this.
- Updated logging output to reflect this when check fails.
- Discovered on 12/29/24 that BD now loads 5 processes. Update checks & logging output.
- Reworked code to get num of processes from `psCnt=` line in `psBD.cfg` file.


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
        
    def getPids(self, psCnt):        
        """ 
        Returns PIDs used by bdsecd processes.
        Obtain bdsecd pids, verify 5 pids, list in bdProcs, & return bdProcs
        """
        self.bdProcs = []

        while len(self.bdProcs) != psCnt:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] == 'bdsecd':
                    self.bdProcs.append(proc.info['pid'])

            if len(self.bdProcs) != psCnt:
                logging.debug('Number of BD processes not 5. Will retry `getPids()`.')
                self.bdProcs = []
                time.sleep(3)

    def spawnTop(self, psCnt):
        """
        Spawn `top` as child to display all bdsecd process details & return that var for control
        """

        topCmd = ['top']
        for i in range(psCnt):
            topCmd.append(f'-p {self.currBdProcs[i]}')

        myTop = psutil.Popen(topCmd)

        return myTop

    def reSpawnTop(self, myTop, psCnt):
        """
        Re-Spawn 'top' as child & return var as needed when processes change during upgrades
        """
        time.sleep(5)  # If removed for testing, don't forget to re-enable (causes high CPU!!!)
        self.getPids(psCnt)
        
        # Check for pid changes. If failures,  terminate with timeout or returncode checks.
        if self.bdProcs != self.currBdProcs:
            myTop.terminate()
            logging.info('Change in BD processes detected. TOP instance terminated')
            try:
                myTop.wait(timeout=2)
            except psutil.TimeoutExpired:
                """ Old logging code
                logging.debug('TOP instance timed out while waiting for termination.')
                """

                #""" This might be better:
                logging.debug('TOP instance timed out while waiting for termination (extSts= ' \
                        + psutil.Process(myTop.pid).status() + ').')
                #"""
                
                print('\nProcess TOP was asked to terminate, but timeout expired while waiting.')
                print('\nCurrent process status of TOP on exit was: ' \
                      + psutil.Process(myTop.pid).status() + '.')
               
                exit()
            
            if myTop.returncode != 0:
                logging.debug('Unusual TOP return code of (' + str(myTop.returncode) +
                              ') causing exit.')
                
                print('\nTOP exited with unusual return code of (' + str(myTop.returncode) + ').')
                print('\nSee `https://psutil.readthedocs.io/en/latest/#psutil.Process.wait` ' \
                      'for details.\n')
                exit()
            
            # If checks pass, copy bpProcs to currBdProcs & spawn new top
            self.currBdProcs = self.bdProcs.copy()
            myTop = self.spawnTop(psCnt)
            logging.info('TOP has been re-initialized showing new BD processes.')

        return myTop


def main():
    # Intialize logging
    os.chdir('/home/swilson/Documents/Coding/Python/psBitDefender/')
    logFilePathName = os.getcwd() + '/psBitDefender.log'
    if (os.path.exists(logFilePathName)) and (os.path.getsize(logFilePathName) > 100000):
        os.remove(logFilePathName)
    
    logging.basicConfig(filename=logFilePathName, format='%(asctime)s <%(levelname)s>: %(message)s',
                        datefmt='%b %d %H:%M:%S', level=logging.DEBUG)
    logging.info('The `psBitDefender.py` script was initialized.')

    # Get config & init config vars
    cfgDict = {}
    with open('psBD.cfg', 'r') as cfgFile:
        for line in cfgFile.readlines():
            if '=' in line:
                key, value = line.strip().split('=', 1)
                cfgDict[key] = value

    psCnt = int(cfgDict['psCnt'])
    
    # Initialize BdProc instance, & populate process lists
    bdProc = BdProc()
    bdProc.getPids(psCnt)
    bdProc.currBdProcs = bdProc.bdProcs.copy()

    # Spawn top to monitor bdsecd processes
    myTop = bdProc.spawnTop(psCnt)
    logging.info('Initial TOP instance started.')

    try:
        while True:
            # Check for changes to pids & re-spawn as needed
            myTop = bdProc.reSpawnTop(myTop, psCnt)

    except KeyboardInterrupt:
        # End while loop & kill myTop with keyboard interrupt
        myTop.terminate()
        logging.info('The `psBitDefender.py` script terminated by keyboard interrupt.')
        print('Caught keyboard interrupt.')
        exit()


if __name__ == '__main__':
    main()
