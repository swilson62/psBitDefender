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

changeLog(v1.16.03):
- Rewrote signal handler to get handling details from cfgFile.

Thoughts:
- 

Attributions:
- 

"""

# Imports
import psutil, time, logging, os, signal, csv


class BdProc(object):
    """
    Object representing functions & configuration required to produce adaptive top listing of
    bdsecd processes.
    """
    def __init__(self):
        """
        Function to Initialize BdProc object list of processes, & configuration 
        dictionary/variables from config file.
        """
        self.bdProcs = []
        self.currBdProcs = []
        self.cfgFilePath = '/home/swilson/Documents/Coding/Python/psBitDefender/'

        self.cfgDict = {}
        with open(os.path.join(self.cfgFilePath, 'psBD.cfg'), 'r') as cfgFile:
            for line in cfgFile.readlines():
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    self.cfgDict[key] = value

        self.psCnt = int(self.cfgDict['psCnt'])
        self.psCntLoopFailCnt = 0
    

    def changeCfg(self):
        """
        Function to change config file as needed
        """
        with open(os.path.join(self.cfgFilePath, 'psBD.cfg'), 'w') as cfgFile:
            for i in range(len(self.cfgDict)):
                cfgFile.write(f'{list(self.cfgDict.items())[i][0]}={ \
                    list(self.cfgDict.items())[i][1]}\n')
    
    
    def getAllPids(self):
        """
        Function to get all pids named `bdsecd`. If called with `self.psCnt == 0` make cfg file &
        dictionarly/variable changes as needed.
        """
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] == 'bdsecd':
                self.bdProcs.append(proc.info['pid'])

        if self.psCnt == 0:
            if len(self.bdProcs) != int(self.cfgDict['psCnt']):
                self.psCnt = self.cfgDict['psCnt'] = len(self.bdProcs)
                self.changeCfg()
            else:
                self.psCnt = int(self.cfgDict['psCnt'])


    def getPids(self):        
        """ 
        Manages PIDs used by bdsecd processes by approprately calling getAllPids().
        """
        self.bdProcs = []

        # Populate or re-populate self.BdProc
        while len(self.bdProcs) != self.psCnt:
            self.getAllPids()

            # If number of processes not matching default, keep trying
            if len(self.bdProcs) != self.psCnt:
                logging.debug('Number of BD processes incorrect. Will retry `getPids()`.')
                self.bdProcs = []
                self.psCntLoopFailCnt += 1
                
                # More than 20 failures probably means change in default
                if self.psCntLoopFailCnt >= 20:
                    self.psCnt = 0
                    self.getAllPids()
                    logging.debug('Change in default number of processes required.')
                    self.psCntLoopFailCnt = 0
                    return
                
                # Less than 20 probably means update not finished loading. Sleep & try again.
                time.sleep(3)

            # Update completed sucessfully
            else:
                self.psCntLoopFailCnt = 0


    def spawnTop(self):
        """
        Create topCmd list, populate processes, & load top
        """
        topCmd = ['top']
        for i in range(self.psCnt):
            topCmd.append(f'-p {self.currBdProcs[i]}')

        self.myTop = psutil.Popen(topCmd)


    def reSpawnTop(self):
        """
        Terminate and respawn 'top' as child as needed when processes change during upgrades
        """
        time.sleep(5)  # If removed for testing, don't forget to re-enable (causes high CPU!!!)
        self.getPids()
        
        # Check for pid changes & terminate myTop on change.
        if self.bdProcs != self.currBdProcs:
            self.myTop.terminate()
            logging.info('Change in BD processes detected. TOP instance terminated')
            try:
                self.myTop.wait(timeout=2)

            # If termination failures, printout failure info & end script.
            except psutil.TimeoutExpired:
                logging.debug('TOP instance timed out while waiting for termination (extSts= ' \
                        + psutil.Process(self.myTop.pid).status() + ').')
                
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


    def receiveSignal(self, signum, frame):
        """
        bdPoc system signal handler. Will obtain signal handling configuration from CSV line items
        `sigTerm=`, & `sigNoLog=` parameters added to `cfgFile`. Parsed internally from `cfgDict`.
        Parameters `signum` & `frame` are provided from `signal.signal()` trap when tripped.
        """
        sigTerm = self.cfgDict['sigTerm'].split(',')
        sigNoLog = self.cfgDict['sigNoLog'].split(',')

        if signum > 0:
            # Kill myTop on specific terminating signals
            if str(signum) in sigTerm:
                self.myTop.terminate()

                # Add to log for various terminating signals then exit
                if signum == 1:
                    logging.info('The `psBitDefender.py` script terminated by SIGHUP.')
                if signum == 2:
                    logging.info('The `psBitDefender.py` script terminated by keyboard interrupt.')
                    print('Caught keyboard interrupt.')
                exit()

            # Signals not requiring logging
            if str(signum) in sigNoLog:
                pass
            
            # And log the rest but do not terminate
            else:
                logging.info(f'Signal {signal.Signals(signum).name} received, causing no termination.')


def main():
    # Initialize BdProc instance
    bdProc = BdProc()

    # Set traps for signal interrupts
    for sigNumber in range(1, signal.NSIG):
        try:
            # Skip SIGKILL and SIGSTOP
            if sigNumber not in (signal.SIGKILL, signal.SIGSTOP, 32, 33):
                signal.signal(sigNumber, bdProc.receiveSignal)
        except OSError:
            print(f"Signal {sigNumber} cannot be caught")

    # Intialize logging
    os.chdir('/home/swilson/Documents/Coding/Python/psBitDefender/')
    logFilePathName = os.getcwd() + '/psBitDefender.log'
    if (os.path.exists(logFilePathName)) and (os.path.getsize(logFilePathName) > 100000):
        os.remove(logFilePathName)
    
    logging.basicConfig(filename=logFilePathName, format='%(asctime)s <%(levelname)s>: %(message)s',
                        datefmt='%b %d %H:%M:%S', level=logging.DEBUG)
    logging.info('The `psBitDefender.py` script was initialized.')

    # Populate process lists
    bdProc.psCnt = 0
    bdProc.getAllPids()
    bdProc.currBdProcs = bdProc.bdProcs.copy()

    # Spawn top to monitor bdsecd processes
    bdProc.spawnTop()
    logging.info('Initial TOP instance started.')

    #try:
    while True:
        # Check for changes to pids & re-spawn as needed
        bdProc.reSpawnTop()


if __name__ == '__main__':
    main()
