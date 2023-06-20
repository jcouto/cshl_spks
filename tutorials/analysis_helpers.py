import os
import numpy as np
from os.path import join as pjoin
from tqdm import tqdm
from glob import glob
import pandas as pd

###############################################################################
################# HANDLE RAW BINARY FILES #####################################
###############################################################################

def map_binary(fname,nchannels,dtype=np.int16,
               offset = 0,
               mode = 'r',nsamples = None,transpose = False):
    ''' 
    dat = map_binary(fname,nchannels,dtype=np.int16,mode = 'r',nsamples = None)
    
Memory maps a binary file to numpy array.
    Inputs: 
        fname           : path to the file
        nchannels       : number of channels
        dtype (int16)   : datatype
        mode ('r')      : mode to open file ('w' - overwrites/creates; 'a' - allows overwriting samples)
        nsamples (None) : number of samples (if None - gets nsamples from the filesize, nchannels and dtype)
    Outputs:
        data            : numpy.memmap object (nchannels x nsamples array)
See also: map_spikeglx, numpy.memmap

    Usage:
Plot a chunk of data:
    dat = map_binary(filename, nchannels = 385)
    chunk = dat[:-150,3000:6000]
    
    import pylab as plt
    offset = 40
    fig = plt.figure(figsize=(10,13)); fig.add_axes([0,0,1,1])
    plt.plot(chunk.T - np.nanmedian(chunk,axis = 1) + offset * np.arange(chunk.shape[0]), lw = 0.5 ,color = 'k');
    plt.axis('tight');plt.axis('off');

    Joao Couto 2019
    '''
    dt = np.dtype(dtype)
    if not os.path.exists(fname):
        if not mode == 'w':
            raise(ValueError('File '+ fname +' does not exist?'))
        else:
            print('Does not exist, will create [{0}].'.format(fname))
            if not os.path.isdir(os.path.dirname(fname)):
                os.makedirs(os.path.dirname(fname))
    if nsamples is None:
        if not os.path.exists(fname):
            raise(ValueError('Need nsamples to create new file.'))
        # Get the number of samples from the file size
        nsamples = os.path.getsize(fname)/(nchannels*dt.itemsize)
    ret = np.memmap(fname,
                    mode=mode,
                    dtype=dt,
                    shape = (int(nsamples),int(nchannels)))
    if transpose:
        ret = ret.transpose([1,0])
    return ret

def read_spikeglx_meta(metafile):
    '''
    Read spikeGLX metadata file.

    Joao Couto - 2019
    '''
    with open(metafile,'r') as f:
        meta = {}
        for ln in f.readlines():
            tmp = ln.split('=')
            k,val = tmp
            k = k.strip()
            val = val.strip('\r\n')
            if '~' in k:
                meta[k.strip('~')] = val.strip('(').strip(')').split(')(')
            else:
                try: # is it numeric?
                    meta[k] = float(val)
                except:
                    try:
                        meta[k] = float(val) 
                    except:
                        meta[k] = val
    # Set the sample rate depending on the recording mode
    meta['sRateHz'] = meta[meta['typeThis'][:2]+'SampRate']
    try:
        parse_coords_from_spikeglx_metadata(meta)
    except:
        pass
    return meta

def parse_coords_from_spikeglx_metadata(meta,shanksep = 250):
    '''
    Python version of the channelmap parser from spikeglx files.
    Adapted from the matlab from Jeniffer Colonel

    Joao Couto - 2022
    '''
    if not 'imDatPrb_type' in meta.keys():
        meta['imDatPrb_type'] = 0.0 # 3A/B probe
    probetype = int(meta['imDatPrb_type'])
    shank_sep = 250

    imro = np.stack([[int(i) for i in m.split(' ')] for m in meta['imroTbl'][1:]])
    chans = imro[:,0]
    banks = imro[:,1]
    shank = np.zeros(imro.shape[0])
    connected = np.stack([[int(i) for i in m.split(':')] for m in meta['snsShankMap'][1:]])[:,3]
    if (probetype <= 1) or (probetype == 1100) or (probetype == 1300):
        # <=1 3A/B probe
        # 1100 UHD probe with one bank
        # 1300 OPTO probe
        electrode_idx = banks*384 + chans
        if probetype == 0:
            nelec = 960;    # per shank
            vert_sep  = 20; # in um
            horz_sep  = 32;
            pos = np.zeros((nelec, 2))
            # staggered
            pos[0::4,0] = horz_sep/2       # sites 0,4,8...
            pos[1::4,0] = (3/2)*horz_sep   # sites 1,5,9...
            pos[2::4,0] = 0;               # sites 2,6,10...
            pos[3::4,0] = horz_sep         # sites 3,7,11...
            pos[:,0] = pos[:,0] + 11          # x offset on the shank
            pos[0::2,1] = np.arange(nelec/2) * vert_sep   # sites 0,2,4...
            pos[1::2,1] = pos[0::2,1]                    # sites 1,3,5...

        elif probetype == 1100:   # HD
            nelec = 384      # per shank
            vert_sep = 6    # in um
            horz_sep = 6
            pos = np.zeros((nelec,2))
            for i in range(7):
                ind = np.arange(i,nelec,8)
                pos[ind,0] = i*horz_sep
                pos[ind,1] = np.floor(ind/8)* vert_sep
        elif probetype == 1300: #OPTO
            nelec = 960;    # per shank
            vert_sep  = 20; # in um
            horz_sep  = 48;
            pos = np.zeros((nelec, 2))
            # staggered
            pos[0:-1:2,0] = 0          # odd sites
            pos[1:-1:2,0] = horz_sep   # even sites
            pos[0:-1:2,1] = np.arange(nelec/2) * vert_sep
    elif probetype == 24 or probetype == 21:
        electrode_idx = imro[:,2]
        if probetype == 24:
            banks = imro[:,2]
            shank = imro[:,1]
            electrode_idx = imro[:,4]
        nelec = 1280       # per shank; pattern repeats for the four shanks
        vert_sep  = 15     # in um
        horz_sep  = 32
        pos = np.zeros((nelec, 2))
        pos[0::2,0] = 0                              # x pos
        pos[1::2,0] = horz_sep
        pos[1::2,0] = pos[1::2,0] 
        pos[0::2,1] = np.arange(nelec/2) * vert_sep   # y pos sites 0,2,4...
        pos[1::2,1] = pos[0::2,1]                     # sites 1,3,5...
    else:
        print('ERROR [parse_coords_from_spikeglx_metadata]: probetype {0} is not implemented.'.format(probetype))
        raise NotImplementedError('Not implemented probetype {0}'.format(probetype))
    coords = np.vstack([shank*shank_sep+pos[electrode_idx,0],
                        pos[electrode_idx,1]]).T    
    idx = np.arange(len(coords))
    meta['coords'] = coords[connected==1,:]
    meta['channel_idx'] = idx[connected==1]
    return idx,coords,connected

def load_spikeglx_binary(fname, dtype=np.int16):
    ''' 
    data,meta = load_spikeglx_binary(fname,nchannels)
    
    Memory maps a spikeGLX binary file to numpy array.

    Inputs: 
        fname           : path to the file
    Outputs:
        data            : numpy.memmap object (nchannels x nsamples array)
        meta            : meta data from spikeGLX

    Joao Couto - 2019
    '''
    name = os.path.splitext(fname)[0]
    ext = '.meta'

    metafile = name + ext
    if not os.path.isfile(metafile):
        raise(ValueError('File not found: ' + metafile))
    meta = read_spikeglx_meta(metafile)
    nchans = meta['nSavedChans']
    return map_binary(fname,nchans,dtype=np.int16,mode = 'r'),meta


def list_spikeglx_files(folder):
    '''
    A function to list (multiprobe) spikeglx files.
    
    apfiles,nidqfile = list_spikeglx_files(folder)
    
    Joao Couto - CSHL Ion Channels course 2023
    '''
    niqdfile = glob(pjoin(folder,'*.nidq.bin'),recursive = True)
    if len(niqdfile): niqdfile = niqdfile[0] 
    apfiles = np.sort(glob(pjoin(folder,'*','*.ap.bin'),recursive = True))
    #raise an error if the folder did not have probe files
    if not len(apfiles):
        raise(OSError('There were no probe files in folder '+ folder))
    return apfiles,niqdfile

###############################################################################
################# HANDLE SYNCHRONIZATION AND THE SYNC BYTES ###################
###############################################################################

def unpackbits(x,num_bits = 16):
    '''
    unpacks numbers in bits.

    Joao Couto - April 2019
    '''
    xshape = list(x.shape)
    x = x.reshape([-1,1])
    to_and = 2**np.arange(num_bits).reshape([1,num_bits])
    return (x & to_and).astype(bool).astype(int).reshape(xshape + [num_bits])


def unpack_npix_sync(syncdat,srate=1,output_binary = False):
    '''Unpacks neuropixels phase external input data
events = unpack_npix3a_sync(trigger_data_channel)    
    Inputs:
        syncdat               : trigger data channel to unpack (pass the last channel of the memory mapped file)
        srate (1)             : sampling rate of the data; to convert to time - meta['imSampRate']
        output_binary (False) : outputs the unpacked signal
    Outputs
        events        : dictionary of events. the keys are the channel number, the items the sample times of the events.

    Joao Couto - April 2019

    Usage:
Load and get trigger times in seconds:
    dat,meta = load_spikeglx('test3a.imec.lf.bin')
    srate = meta['imSampRate']
    onsets,offsets = unpack_npix_sync(dat[:,-1],srate);
Plot events:
    plt.figure(figsize = [10,4])
    for ichan,times in onsets.items():
        plt.vlines(times,ichan,ichan+.8,linewidth = 0.5)
    plt.ylabel('Sync channel number'); plt.xlabel('time (s)')
    '''
    dd = unpackbits(syncdat.flatten(),16)
    mult = 1
    if output_binary:
        return dd
    sync_idx_onset = np.where(mult*np.diff(dd,axis = 0)>0)
    sync_idx_offset = np.where(mult*np.diff(dd,axis = 0)<0)
    onsets = {}
    offsets = {}
    for ichan in np.unique(sync_idx_onset[1]):
        onsets[ichan] = sync_idx_onset[0][
            sync_idx_onset[1] == ichan]/srate
    for ichan in np.unique(sync_idx_offset[1]):
        offsets[ichan] = sync_idx_offset[0][
            sync_idx_offset[1] == ichan]/srate
    return onsets,offsets

###############################################################################
############################ LOAD PHY DATA ####################################
###############################################################################

def load_phy_folder(sortfolder):
    '''
    Phy stores data as .npy and tab separated (.tsv) files in a folder.

    This function reads the spike times and cluster identities from a folder and 
computes the spike amplitudes and approximate spike locations (XY).

    This is an approximate way of computing the spike depths since we don't 
actually read the waveforms (so it is fast); we use the templates instead.

Example:
 
spike_times,spike_clusters,spike_amplitudes,spike_positions,templates_raw,templates_position,cluster_groups = load_phy_folder(folder)

    Joao Couto - CSHL Ion Channels 2023
 
    '''
    # load the channel locations
    channel_pos =  np.load(pjoin(sortfolder,'channel_positions.npy'))
    # load each spike cluster number
    spike_clusters = np.load(pjoin(sortfolder,'spike_clusters.npy'))
    # load spiketimes
    spike_times = np.load(pjoin(sortfolder,'spike_times.npy'))
    # load spike templates (which template was fitted)
    spike_templates = np.load(pjoin(sortfolder,'spike_templates.npy'))
    # load the templates used to extract the spikes
    templates =  np.load(pjoin(sortfolder,'templates.npy'))
    # Load the amplitudes used to fit the template
    spike_template_amplitudes = np.load(pjoin(sortfolder,'amplitudes.npy'))
    # load the whitening matrix (to correct for the data having been whitened)
    whitening_matrix = np.load(pjoin(sortfolder,'whitening_mat_inv.npy')).T
    cluster_groups = pjoin(sortfolder,'cluster_group.tsv')
    if os.path.exists(cluster_groups):
        cluster_groups = pd.read_csv(cluster_groups,sep = '\t')
    else:
        cluster_groups = None

    # the raw templates are the dot product of the templates by the whitening matrix
    templates_raw = np.dot(templates,whitening_matrix)
    # compute the peak to peak of each template
    templates_peak_to_peak = (templates_raw.max(axis = 1) - templates_raw.min(axis = 1))
    # the amplitude of each template is the max of the peak difference for all channels
    templates_amplitude = templates_peak_to_peak.max(axis=1)
    # compute the center of mass (X,Y) of the templates
    template_position = [templates_peak_to_peak*pos for pos in channel_pos.T]
    template_position = np.vstack([np.sum(t,axis =1 )/np.sum(templates_peak_to_peak,axis = 1) 
                                   for t in template_position]).T
    # get the spike positions and amplitudes from the average templates
    spike_amplitudes = templates_amplitude[spike_templates]*spike_template_amplitudes
    spike_positions = template_position[spike_templates,:].squeeze()
    return spike_times,spike_clusters,spike_amplitudes,spike_positions,templates_raw,template_position,cluster_groups

