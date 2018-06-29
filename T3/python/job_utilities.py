#!/usr/bin/env python

import os
import json
import socket
import requests
from re import sub
from sys import exit
from glob import glob 
from random import choice
from time import clock,time,sleep
from os import system,getenv,path,environ,getpid

import ROOT as root
from PandaCore.Tools.Misc import *
from PandaCore.Utils.load import Load
import PandaCore.Tools.job_config as cb

_sname = 'T3.job_utilities'                                    # name of this module
_data_dir = getenv('CMSSW_BASE') + '/src/PandaAnalysis/data/'  # data directory
_host = socket.gethostname()                                   # where we're running
_IS_T3 = (_host.startswith('t3') and _host.endswith('mit.edu'))# are we on the T3?
REMOTE_READ = True                                             # should we read from hadoop or copy locally?
local_copy = bool(environ.get('SUBMIT_LOCALACCESS', True))     # should we always xrdcopy from T2?
_task_name = getenv('SUBMIT_NAME')                             # name of this task
_user = getenv('SUBMIT_USER')                                  # user running the task
YEAR = 2016                                                    # what year's data is this analysis?
MAXCOPY = 3                                                    # maximum number of stagein attempts

stageout_protocol = None                                       # what stageout should we use?
if _IS_T3:
    stageout_protocol = 'cp' 
elif system('which gfal-copy') == 0:
    stageout_protocol = 'gfal'
elif system('which lcg-cp') == 0:
    stageout_protocol = 'lcg'
else:
    try:
        ret = system('wget -nv http://t3serv001.mit.edu/~snarayan/misc/lcg-cp.tar.gz')
        ret = max(ret, system('tar -xvf lcg-cp.tar.gz'))
        if ret:
            raise RuntimeError
        environ['PATH'] = '$PWD/lcg-cp:'+environ['PATH']
        environ['LD_LIBRARY_PATH'] = '$PWD/lcg-cp:'+environ['LD_LIBRARY_PATH']
        stageout_protocol = 'lcg'
    except Exception as e:
        logger.error(_sname,
                     'Could not install lcg-cp in absence of other protocols!')
        raise e


# derived from t3serv006.mit.edu:/etc/bestman2/conf/bestman2.rc
_gsiftp_doors = [
        't3btch000.mit.edu',
        't3btch001.mit.edu',
        't3btch003.mit.edu',
        't3btch004.mit.edu',
        't3btch005.mit.edu',
        't3btch006.mit.edu',
        't3btch010.mit.edu',
        't3btch013.mit.edu',
        't3btch014.mit.edu',
        't3btch018.mit.edu',
        't3btch021.mit.edu',
        't3btch025.mit.edu',
        't3btch026.mit.edu',
        't3btch027.mit.edu',
        't3btch028.mit.edu',
        't3btch029.mit.edu',
        't3btch030.mit.edu',
        ]



# global to keep track of how long things take
_stopwatch = time() 
def print_time(label):
    global _stopwatch
    now_ = time()
    logger.debug(_sname+'.print_time:',
           '%.1f s elapsed performing "%s"'%((now_-_stopwatch),label))
    _stopwatch = now_

# set the data-taking period
def set_year(analysis, year):
    global YEAR
    analysis.year = year
    YEAR = year

# isolate the job
def isolate():
    pid = getpid()
    p = 'job_%i'%pid 
    try:
        os.mkdir(p)
    except OSError:
        pass
    os.chdir(p)
    return p

def un_isolate(p):
    os.chdir('..')
    cleanup(p)

# convert an input name to an output name
def input_to_output(name):
    if 'input' in name:
        return name.replace('input','output')
    else:
        return 'output_' + name.split('/')[-1]


# find data and bring it into the job somehow 
#  - if local_copy and it exists locally, then:
#    - if REMOTE_READ, read from hadoop
#    - else copy it locally
#  - else xrdcopy it locally
def copy_local(long_name):
    full_path = long_name
    logger.info(_sname,full_path)

    panda_id = long_name.split('/')[-1].split('_')[-1].replace('.root','')
    input_name = 'input_%s.root'%panda_id
    copied = False

    # if the file is cached locally, why not use it?
    if 'scratch' in full_path:
        local_path = full_path.replace('root://t3serv006.mit.edu/','/mnt/hadoop')
    else:
        local_path = full_path.replace('root://xrootd.cmsaf.mit.edu/','/mnt/hadoop/cms')
    logger.info(_sname+'.copy_local','Local access is configured to be %s'%('on' if local_copy else 'off'))
    if local_copy and path.isfile(local_path): 
        # apparently SmartCached files can be corrupted...
        ftest = root.TFile(local_path)
        if bool(ftest) and not(ftest.IsZombie()):
            logger.info(_sname+'.copy_local','Opting to read locally')
            if REMOTE_READ:
                return local_path
            else:
                cmd = 'cp %s %s'%(local_path, input_name)
                logger.info(_sname+'.copy_local',cmd)
                ret = system(cmd)
                if ret:
                    return None 
                copied = True

    if not copied:
        cmd = "xrdcopy --nopbar -f %s %s"%(full_path,input_name)
        logger.info(_sname+'.copy_local',cmd)
        ret = system(cmd)
        if ret:
            logger.error(_sname+'.copy_local','Failed to xrdcopy %s'%input_name)
            return None 
        ftest = root.TFile.Open(input_name)
        if not(bool(ftest)) or ftest.IsZombie():
            logger.error(_sname+'.copy_local', 'Copy succeeded but %s is corrupt'%input_name)
            return None 
        copied = True
            
    if path.isfile(input_name):
        logger.info(_sname+'.copy_local','Successfully copied to %s'%(input_name))
        return input_name
    else:
        logger.error(_sname+'.copy_local','Failed to copy %s'%input_name)
        return None


# wrapper around remove. be careful!
def cleanup(fname, _verbose=True):
    if path.isfile(fname):
        os.remove(fname)
    elif path.isdir(fname):
        os.rmdir(fname)
    else:
        for f in glob(fname):
            cleanup(f, False)
    if _verbose:
        logger.info(_sname+'.cleanup','Removed '+fname)
    return 0 # if it made it this far without OSError, it's good


# wrapper around hadd
def hadd(good_inputs, output='output.root'):
    good_outputs = ' '.join([input_to_output(x) for x in good_inputs])
    cmd = 'hadd -f ' + output + ' ' + good_outputs
    print cmd
    ret = system(cmd)    
    if not ret:
        logger.info(_sname+'.hadd','Merging exited with code %i'%ret)
    else:
        logger.error(_sname+'.hadd','Merging exited with code %i'%ret)


# remove any irrelevant branches from the final tree.
# this MUST be the last step before stageout or you 
# run the risk of breaking something
def drop_branches(to_drop=None, to_keep=None):
    if not to_drop and not to_keep:
        return 0

    if to_drop and to_keep:
        logger.error(_sname+'.drop_branches','Can only provide to_drop OR to_keep')
        return 0

    f = root.TFile('output.root','UPDATE')
    t = f.FindObjectAny('events')
    n_entries = t.GetEntriesFast() # to check the file wasn't corrupted
    if to_drop:
        if type(to_drop)==str:
            t.SetBranchStatus(to_drop,False)
        else:
            for b in to_drop:
                t.SetBranchStatus(b,False)
    elif to_keep:
        t.SetBranchStatus('*',False)
        if type(to_keep)==str:
            t.SetBranchStatus(to_keep,True)
        else:
            for b in to_keep:
                t.SetBranchStatus(b,True)
    t_clone = t.CloneTree()
    f.WriteTObject(t_clone,'events','overwrite')
    f.Close()

    # check that the write went okay
    f = root.TFile('output.root')
    if f.IsZombie():
        logger.error(_sname+'.drop_branches','Corrupted file trying to drop '+str(to_drop))
        return 1 
    t_clone = f.FindObjectAny('events')
    if (n_entries==t_clone.GetEntriesFast()):
        return 0
    else:
        logger.error(_sname+'.drop_branches','Corrupted tree trying to drop '+str(to_drop))
        return 2



# stageout a file (e.g. output or lock)
#  - if _IS_T3, execute a simple cp
#  - else, use lcg-cp
# then, check if the file exists:
#  - if _IS_T3, use os.path.isfile
#  - else, use lcg-ls
def stageout(outdir,outfilename,infilename='output.root',n_attempts=10,ls=None):
    gsiftp_doors = _gsiftp_doors[:]
    if ls is None:
        # if it's not on hadoop, copy the file to test it exists, to force nfs refresh
        ls = not('hadoop' in outdir) 
    ls = False # override, I don't trust network-mounted filesystems anymore 
    if stageout_protocol is None:
        logger.error(_sname+'.stageout',
               'Stageout protocol has not been satisfactorily determined! Cannot proceed.')
        return -2
    timeout = 300
    ret = -1
    for i_attempt in xrange(n_attempts):
        door = choice(gsiftp_doors); gsiftp_doors.remove(door)
        failed = False
        if stageout_protocol == 'cp':
            cpargs =     ' '.join(['cp',
                                   '-v', 
                                   '$PWD/%s'%infilename,
                                   '%s/%s'%(outdir,outfilename)])
            if ls:
                lsargs = ' '.join(['ls',
                                   '%s/%s'%(outdir,outfilename)])
            else:
                lsargs = ' '.join(['cp',
                                   '-v',
                                   '%s/%s'%(outdir,outfilename),
                                   '$PWD/testfile'])
        elif stageout_protocol == 'gfal':
            cpargs =     ' '.join(['gfal-copy',
                                   '-f', 
                                   '--transfer-timeout %i'%timeout,
                                   '$PWD/%s'%infilename,
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename)])
            if ls:
                lsargs = ' '.join(['gfal-ls',
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename)])
            else:
                lsargs = ' '.join(['gfal-copy',
                                   '-f', 
                                   '--transfer-timeout %i'%timeout,
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename),
                                   '$PWD/testfile'])
        elif stageout_protocol == 'lcg':
            cpargs =     ' '.join(['lcg-cp',
                                   '-v -D srmv2 -b', 
                                   'file://$PWD/%s'%infilename,
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename)])
            if ls:       
                lsargs = ' '.join(['lcg-ls',
                                   '-v -D srmv2 -b', 
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename)])
            else:
                lsargs = ' '.join(['lcg-cp',
                                   '-v -D srmv2 -b', 
                                   'gsiftp://%s:2811//%s/%s'%(door,outdir,outfilename),
                                   'file://$PWD/testfile'])
        logger.info(_sname+'.stageout',cpargs)
        ret = system(cpargs)
        if not ret:
            logger.info(_sname+'.stageout','Move exited with code %i'%ret)
            sleep(10) # give the filesystem a chance to respond
        else:
            logger.warning(_sname+'.stageout','Move exited with code %i'%ret)
            failed = True
        if not failed:
            logger.info(_sname+'.stageout',lsargs)
            ret = system(lsargs)
            if ret:
                logger.warning(_sname+'.stageout','Output file is missing!')
                failed = True
        if not failed:
            logger.info(_sname+'.stageout', 'Copy succeeded after %i attempts'%(i_attempt+1))
            cleanup('testfile')
            return ret
        else:
            timeout = int(timeout * 1.5)
        cleanup('testfile')
    logger.error(_sname+'.stagoeut', 'Copy failed after %i attempts'%(n_attempts))
    return ret

# report home that the job has started
def report_start(outdir,outfilename,args):
    if not cb.textlock:
        for _ in xrange(5):
            try:
                hashed = [cb.md5hash(x) for x in args]
                job_id = '_'.join(outfilename.replace('.root','').split('_')[-2:])
                payload = {'starttime' : int(time()),
                           'host' : _host, 
                           'task' : _task_name + '_' + _user,
                           'job_id' : job_id,
                           'args' : hashed}
                r = requests.post(cb.report_server+'/condor/start', json=payload)
                if r.status_code == 200:
                    logger.info('T3.job_utilities.report_start', 'return=%s'%(str(r).strip()))
                    return 
                else:
                    logger.error('T3.job_utilities.report_start', 'return=%s'%(str(r).strip()))
                sleep(10)
            except requests.ConnectionError as e:
                logger.error('T3.job_utilities.report_start', str(e))
        logger.error('T3.job_utilities.report_start', 'Dying after 5 attempts!')
        raise requests.ConnectionError()


# write a lock file, based on what succeeded,
# and then stage it out to a lock directory
def report_done(outdir,outfilename,processed):
    if cb.textlock:
        outfilename = outfilename.replace('.root','.lock')
        flock = open(outfilename,'w')
        for k,v in processed.iteritems():
            flock.write(v+'\n')
        flock.close()
        stageout(outdir,outfilename,outfilename,ls=False)
        cleanup('*.lock')
    else:
        # this really has to work, so go forever
        while True:
            try:
                job_id = '_'.join(outfilename.replace('.root','').split('_')[-2:])
                payload = {'timestamp' : int(time()),
                           'task' : _task_name + '_' + _user,
                           'job_id' : job_id,
                           'args' : [cb.md5hash(v) for _,v in processed.iteritems()]}
                logger.info('T3.job_utilities.report_done',
                            'payload=\n%s'%repr(payload))
                r = requests.post(cb.report_server+'/condor/done', json=payload)
                if r.status_code == 200:
                    logger.info('T3.job_utilities.report_done', 'return=%s'%(str(r).strip()))
                    return 
                else:
                    logger.error('T3.job_utilities.report_done', 'return=%s'%(str(r).strip()))
                sleep(10)
            except requests.ConnectionError as e:
                logger.error('T3.job_utilities.report_done', str(e))


# make a record in the primary output of what
# inputs went into it
def record_inputs(outfilename,processed):
    fout = root.TFile.Open(outfilename,'UPDATE')
    names = root.TNamed('record',
                        ','.join(processed.values()))
    fout.WriteTObject(names)
    fout.Close()


# classify a sample based on its name
def classify_sample(full_path, isData):
    _classification = [
                (root.pa.kSignal , ['Vector_', 'Scalar_']),
                (root.pa.kTop    , ['ST_', 'ZprimeToTT']),
                (root.pa.kZEWK   , 'EWKZ2Jets'),
                (root.pa.kWEWK   , 'EWKW'),
                (root.pa.kZ      , ['ZJets', 'DY']),
                (root.pa.kW      , 'WJets'),
                (root.pa.kA      , 'GJets'),
                (root.pa.kTT     , ['TTJets', 'TT_', 'TTTo']),
                (root.pa.kH      , 'HTo'),
            ]
    if not isData:
        for e,pattern in _classification:
            if type(pattern) == str:
                if pattern in full_path:
                    return e 
            else:
                if any([x in full_path for x in pattern]):
                    return e
    return root.pa.kNoProcess


# read a CERT json and add it to the skimmer
_jsons = {
        2016 : '/certs/Cert_271036-284044_13TeV_23Sep2016ReReco_Collisions16_JSON.txt',
        2017 : '/certs/Cert_294927-306462_13TeV_EOY2017ReReco_Collisions17_JSON_v1.txt',
        }
def add_json(skimmer):
    json_path = _jsons.get(YEAR, None)
    if not json_path:
        logger.error("T3.job_utilities.add_json", "Unknown key = "+str(YEAR))
    json_path = _data_dir + json_path
    with open(json_path) as jsonFile:
        payload = json.load(jsonFile)
        for run_str,lumis in payload.iteritems():
            run = int(run_str)
            for l in lumis:
                skimmer.AddGoodLumiRange(run,l[0],l[1])


# some common stuff that doesn't need to be configured
def run_Analyzer(skimmer, isData, output_name):
    # run and save output
    skimmer.Run()
    skimmer.Terminate()

    ret = path.isfile(output_name)
    if ret:
        logger.info(_sname+'.run_Analyzer','Successfully created %s'%(output_name))
        return output_name 
    else:
        logger.error(_sname+'.run_Analyzer','Failed in creating %s!'%(output_name))
        return False


def run_PandaAnalyzer(skimmer, isData, output_name):
    if isData:
        add_json(skimmer)

    return run_Analyzer(skimmer, isData, output_name)


def run_HRAnalyzer(*args, **kwargs):
    return run_Analyzer(*args, **kwargs) 

# main function to run a skimmer, customizable info 
# can be put in fn
def main(to_run, processed, fn):
    print_time('loading')
    for f in to_run.files:
        for _ in xrange(MAXCOPY):
            input_name = copy_local(f)
            if input_name is not None:
                break
            sleep(30)
        print_time('copy %s'%input_name)
        if input_name:
            success = fn(input_name,(to_run.dtype!='MC'),f)
            print_time('analyze %s'%input_name)
            if success:
                processed[input_name] = f
            if input_name[:5] == 'input': # if this is a local copy
                cleanup(input_name)
            print_time('remove %s'%input_name)
    
    if len(processed)==0:
        logger.warning(_sname+'.main', 'No successful outputs!')
        exit(1)


