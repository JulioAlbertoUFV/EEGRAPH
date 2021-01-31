import numpy as np
import pandas as pd
import mne
import matplotlib.pyplot as plt
import networkx as nx
import plotly.graph_objects as go
import scot
from scipy import signal, stats
from scipy.stats import entropy
from math import pow, exp, atan
from itertools import combinations
#https://raphaelvallat.com/entropy/build/html/index.html
from entropy import spectral_entropy

    
def input_data_type(path, exclude):
    """Process to identify the input extension, and extract it with mne EEG reader.
    Parameters
    ----------
    path : string
        Path to the EEG file.
    exclude : list of strings
        Channels names to exclude from the EEG.
        
    Returns
    -------
    data : mne.io.Raw
        Processed EEG data file generated using mne.read, which can be used to extract all the information.
    """
    
    #Split the path in two parts, left and right of the dot. 
    file_type = path.split(".")
    
    #https://mne.tools/0.17/manual/io.html
    #Check the extension of the file, and read it accordingly. 
    if(file_type[-1] == 'edf'):
        data = mne.io.read_raw_edf(path, exclude= exclude)
    elif(file_type[-1] == 'gdf'):
        data = mne.io.read_raw_gdf(path, exclude= exclude)
    elif(file_type[-1] == 'vhdr'):
        data = mne.io.read_raw_brainvision(path, exclude= exclude)
    elif(file_type[-1] == 'cnt'):
        data = mne.io.read_raw_cnt(path, exclude= exclude)   
    elif(file_type[-1] == 'bdf'):
        data = mne.io.read_raw_edf(path, exclude= exclude)
    elif(file_type[-1] == 'egi'):
        data = mne.io.read_raw_egi(path, exclude= exclude)
    elif(file_type[-1] == 'mff'):
        data = mne.io.read_raw_egi(path, exclude= exclude)
    elif(file_type[-1] == 'nxe'):
        data = mne.io.read_raw_eximia(path, exclude= exclude)
        
    return data


def get_display_info(data):
    """Process to extract the data from the mne.io.Raw file and display it.
    Parameters
    ----------
    data : mne.io.Raw
        Processed EEG data file generated using mne.read. 
        
    Returns
    -------
    raw_data : array
        Raw EEG signal; each row is one EEG channel, each column is data point.
    num_channels: int
        Number of channels in the EEG.
    sample_rate: float
        Sample frequency used in the EEG (Hz).
    sample_duration: float
        Duration of the EEG (seconds).
    ch_names: list of strings
        Channel names in the EEG.
    """
    
    #Extract the raw_data and info with mne methods. 
    raw_data = data.get_data()
    info = data.info
    
    #Obtain different variables from the data. 
    ch_names = data.ch_names
    num_channels = info['nchan']
    print("\nNumber of Channels:", num_channels)
    sample_rate = info['sfreq']
    print("Sample rate:", sample_rate, "Hz")
    sample_duration = data.times.max()
    print("Duration:", sample_duration, "seconds")
    
    return raw_data, num_channels, sample_rate, sample_duration, ch_names


def re_scaling(raw_data):
    df = pd.DataFrame(raw_data)
    df.sub(df.mean(axis=1), axis=0)
    scaled_data = df.to_numpy()

    return scaled_data

def input_bands(bands):
    """Process to identify which bands does the user want to use.
    Parameters
    ----------
    bands : string
        String with the bands to use, separated by commas. 
        
    Returns
    -------
    wanted_bands : list
        Boolean list, with 5 positions one for each frequency band.
    """
    
    #Frequency bands.
    freq_bands = ['delta', 'theta', 'alpha', 'beta', 'gamma']
    wanted_bands = []
    
    #Loop over all frequency bands, and append True if it is in the input bands, otherwise append False. 
    for elem in freq_bands:
        if elem in bands:
            wanted_bands.append(True)
        else:
            wanted_bands.append(False)

    return wanted_bands


def time_intervals(data, sample_rate, sample_duration, seconds):
    """Process to split the data based on the window size or time intervals.
    Parameters
    ----------
    data : array
        Raw EEG signal; each row is one EEG channel, each column is data point.
    sample_rate : float
        Sample frequency used in the EEG (Hz). 
    sample_duration : float
        Duration of the EEG (seconds).
    seconds : int or list
        Can be of two types. int; a single value that determines the window size (seconds). list; a set of intervals, where each value is in (seconds). 
    
    Returns
    -------
    epochs : array
        Array containing the data points according to window size, the number of rows will be (Number of Channels X Intervals).
    steps : list
        List with the intervals, pairs of (Start, End) values in data points (seconds x sample frequency).
    """
    
    #Calculate the sample length in data points. 
    sample_length = sample_rate * sample_duration
    epochs = []
    
    #Obtain the steps using the time_stamps helper function. 
    steps = time_stamps(seconds, sample_rate, sample_length, sample_duration)
    
    #Loop over the intervals.
    for i,_ in enumerate(steps):
        #loop over the number of rows.
        for j in range(len(data)):
            snippet = data[j][int(steps[i][0]):int(steps[i][1])]
            #Append the snippet 
            epochs.append(snippet)
    
    return np.array(epochs), steps


def time_stamps(seconds, sample_rate, sample_length, sample_duration):
    """Process to calculate the intervals based on the window size or time intervals.
    Parameters
    ----------
    seconds : int or list
        Can be of two types. int; a single value that determines the window size (seconds). list; a set of intervals, where each value is in (seconds).
    sample_rate : float
        Sample frequency used in the EEG (Hz).
    sample_length : float
        Sample length in data points (seconds x sample frequency).
    sample_duration : float
        Duration of the EEG (seconds).
    
    Returns
    -------
    intervals : list
        List with the intervals, pairs of (Start, End) values in data points (seconds x sample frequency).
    """
    
    intervals, i= [] , 0
    
    #If the input is a list, but only contains one value it is a window size. 
    if type(seconds) == list:
        if len(seconds) == 1:
            seconds = seconds[0]
        #If it is a list, and contains more than one value is a set of intervals. 
        else:
            #If the last interval is bigger than the sample duration raise Exception. 
            if seconds[-1] > (sample_duration).round():
                raise Exception("Error in Window size. Intervals exceeds sample length.")
            #First value of a ser of intervals must be 0. 
            if seconds[0] != 0:
                raise Exception("Error in Window size. First interval must be 0.")
            else:
                #Obtain the difference between the time intervals.
                diff = np.diff(seconds)
                #Loop over all the values in diff. 
                for j,value in enumerate(diff):
                    #Samples in the frame will be the result of the value of the difference in the first interval x sample frequency. 
                    samples_per_frame = (value * sample_rate)
                    #Append the pair (Start, End) for the interval.
                    intervals.append((i, i + samples_per_frame))
                    #The End will be the Start for the next step. 
                    i += samples_per_frame
    
    #If the input is int or float. 
    if type(seconds) == int or type(seconds) == float:
        #Samples in the frame will be the result of the window size x sample frequency.
        samples_per_frame = (seconds * sample_rate)
        
        #Loop over, adding the samples per frame until it is bigger than the sample length. 
        while i+samples_per_frame <= sample_length:    
            #Append the pair (Start, End) for the interval.
            intervals.append((i,i+samples_per_frame))
            #The End will be the Start for the next step. 
            i = i + samples_per_frame
        
        #If the next time we add the samples per frame it is bigger than the sample length, append the remaining data points in a new interval. 
        #This new interval will not be the same size as the others. 
        if(i+samples_per_frame > sample_length):
            intervals.append((i,sample_length))

    print("Intervals: ",intervals)
    return intervals


def calculate_bands_fft(values, sample_rate):
    """Process to calculate the numpy fft for the snippets.
    Parameters
    ----------
    values : array
        Snippet of values for the signal.
    sample_rate : float
        Sample frequency used in the EEG (Hz).
    
    Returns
    -------
    fft_freq : list
        Frequency bins for given FFT parameters.
    fft_vals : ndarray
        Values calculated with the Fast Fourier Transform.
    """
    
    fft_vals = np.absolute(np.fft.fft(values))
    fft_freq = np.fft.fftfreq(len(values), 1/sample_rate)
    
    
    delta1, theta1, alpha1, beta1, gamma1 = frequency_bands(fft_freq, fft_vals)
    
    delta = np.absolute(np.fft.ifft(delta1))
    theta= np.absolute(np.fft.ifft(theta1))
    alpha= np.absolute(np.fft.ifft(alpha1))
    beta= np.absolute(np.fft.ifft(beta1))
    gamma= np.absolute(np.fft.ifft(gamma1))
    
    return delta, theta, alpha, beta, gamma


def frequency_bands(f,Y):
    """Process to obtain the values for each frequency band.
    Parameters
    ----------
    f : list
        Frequency bins for given FFT parameters.
    Y : ndarray
        Array of values from which we divide into frequency bands. 
    
    Returns
    -------
    delta : array
        Array with values within the ranges of delta band.
    theta : array
        Array with values within the ranges of theta band.
    alpha : array
        Array with values within the ranges of alpha band.
    beta : array
        Array with values within the ranges of beta band.
    gamma : array
        Array with values within the ranges of gamma band.
    """
    
    delta_range = (1,4)
    theta_range = (4,8)
    alpha_range = (8,13)
    beta_range = (13,30)
    gamma_range = (30,45)
    
    #delta = ( Y[(f>delta_range[0]) & (f<=delta_range[1])].mean())
    delta = Y[(f>delta_range[0]) & (f<=delta_range[1])]
    theta = Y[(f>theta_range[0]) & (f<=theta_range[1])]
    alpha = Y[(f>alpha_range[0]) & (f<=alpha_range[1])]
    beta = Y[(f>beta_range[0]) & (f<=beta_range[1])]
    gamma = Y[(f>gamma_range[0]) & (f<=gamma_range[1])]

    return delta, theta, alpha, beta, gamma


def calculate_connectivity(data_intervals, steps, channels, sample_rate, conn):
    """Process to calulate the correlation matrix, using cross correlation.
    Parameters
    ----------
    data_intervals : array
        Array containing the data points according to window size, the number of rows will be (Number of Channels X Intervals).
    steps : list
        List with the intervals, pairs of (Start, End) values in data points (seconds x sample frequency).
    channels: int
        Number of channels in the EEG.
    
    Returns
    -------
    matrix : ndarray
        Correlation matrix using cross correlation.
    """
    #Calculate the number of intervals and create the matrix. 
    intervals = (len(steps))
    matrix = np.zeros(shape=(intervals, channels, channels))
    start, stop = 0, channels
    
    #Loop over the number of intervals
    for k in range(intervals):
        #If there is more than one interval, the new start is the last stop and we calculate the new stop with the number of channels. 
        if k!=0:
            start = stop
            stop+= channels
        #Loop over all possible pairs of channels in the interval calculating the cross correlation coefficient and saving it in the correlation matrix. 
        for x,i in enumerate(range(start, stop)):
            for y,j in enumerate(range(start, stop)):
                matrix[k][x,y] = calculate_conn(data_intervals, i, j, sample_rate, conn, channels)

    return matrix


def calculate_connectivity_with_bands(data_intervals, steps, channels, sample_rate, conn, bands):
    #Calculate the number of bands, number of intervals and create the matrix. 
    num_bands = sum(bands)
    intervals = (len(steps))
    matrix = np.zeros(shape=((intervals * num_bands), channels, channels))
    start, stop = 0, channels
    
    #Loop over the number of intervals
    for k in range(intervals):
        #If there is more than one interval, the new start is the last stop and we calculate the new stop with the number of channels. 
        if k!=0:
            start = stop
            stop+= channels
        #Loop over 
        for x,i in enumerate(range(start, stop)):
            for y,j in enumerate(range(start, stop)):
                delta, theta, alpha, beta, gamma = calculate_conn(data_intervals, i, j, sample_rate, conn, channels)
                r=0
                for z, item in enumerate ([delta, theta, alpha, beta, gamma]):
                    if bands[z]:
                        matrix[(k * num_bands) + r][x,y] = item
                        r+=1
                        
    return matrix


def calculate_conn(data_intervals, i, j, sample_rate, conn, channels):
    if conn == 'cc':
        x = data_intervals[i]
        y = data_intervals[j]
        
        Rxy = signal.correlate(x,y, 'full')
        Rxx = signal.correlate(x,x, 'full')
        Ryy = signal.correlate(y,y, 'full')
        
        lags = np.arange(-len(data_intervals[i]) + 1, len(data_intervals[i]))
        lag_0 = int((np.where(lags==0))[0])

        Rxx_0 = Rxx[lag_0]
        Ryy_0 = Ryy[lag_0]
        
        Rxy_norm = (1/(np.sqrt(Rxx_0*Ryy_0)))* Rxy
        
        #We use the mean from lag 0 to a 10% displacement. 
        disp = round((len(data_intervals[i])) * 0.10)

        cc_coef = Rxy_norm[lag_0: lag_0 + disp].mean()
        
        return cc_coef
    
    if conn == 'pearson':
        r, p_value = (stats.pearsonr(data_intervals[i],data_intervals[j]))
        
        return r
    
    if conn == 'coh':
        f, Cxy = (signal.coherence(data_intervals[i], data_intervals[j], sample_rate))
        
        delta, theta, alpha, beta, gamma = frequency_bands(f, Cxy)
        
        return delta.mean(), theta.mean(), alpha.mean(), beta.mean(), gamma.mean()
    
    if conn == 'icoh':
        _, Pxx = signal.welch(data_intervals[i], fs=sample_rate)
        _, Pyy = signal.welch(data_intervals[j], fs=sample_rate)
        f, Pxy = signal.csd(data_intervals[i],data_intervals[j],fs=sample_rate)
        icoh = np.imag(Pxy)/(np.sqrt(Pxx*Pyy))
        
        delta, theta, alpha, beta, gamma = frequency_bands(f, icoh)
        
        return delta.mean(), theta.mean(), alpha.mean(), beta.mean(), gamma.mean()
    
    if conn == 'corcc':
        x = data_intervals[i]
        y = data_intervals[j]
        
        Rxy = signal.correlate(x,y, 'full')
        Rxx = signal.correlate(x,x, 'full')
        Ryy = signal.correlate(y,y, 'full')
        
        lags = np.arange(-len(data_intervals[i]) + 1, len(data_intervals[i]))
        lag_0 = int((np.where(lags==0))[0])

        Rxx_0 = Rxx[lag_0]
        Ryy_0 = Ryy[lag_0]
        
        Rxy_norm = (1/(np.sqrt(Rxx_0*Ryy_0)))* Rxy
        negative_lag = Rxy_norm[:lag_0]
        positive_lag = Rxy_norm[lag_0 + 1:]
        
        corCC = positive_lag - negative_lag
        
        disp = round((len(data_intervals[i])) * 0.15)
        
        corCC_coef = corCC[:disp].mean()
        
        return corCC_coef
    
    if conn == 'wpli':
        f, Pxy = signal.csd(data_intervals[i],data_intervals[j],fs=sample_rate)
        
        delta, theta, alpha, beta, gamma = frequency_bands(f, Pxy)
        
        wpli_delta = abs(np.mean(abs(np.imag(delta)) * np.sign(np.imag(delta)))) / (np.mean(abs(np.imag(delta))))
        wpli_theta = abs(np.mean(abs(np.imag(theta)) * np.sign(np.imag(theta)))) / (np.mean(abs(np.imag(theta))))
        wpli_alpha = abs(np.mean(abs(np.imag(alpha)) * np.sign(np.imag(alpha)))) / (np.mean(abs(np.imag(alpha)))) 
        wpli_beta = abs(np.mean(abs(np.imag(beta)) * np.sign(np.imag(beta)))) / (np.mean(abs(np.imag(beta))))
        wpli_gamma = abs(np.mean(abs(np.imag(gamma)) * np.sign(np.imag(gamma)))) / (np.mean(abs(np.imag(gamma))))
        
        return wpli_delta, wpli_theta, wpli_alpha, wpli_beta, wpli_gamma
    
    if conn == 'plv':
        sig1_delta, sig1_theta, sig1_alpha, sig1_beta, sig1_gamma = calculate_bands_fft(data_intervals[i], sample_rate)
        sig2_delta, sig2_theta, sig2_alpha, sig2_beta, sig2_gamma = calculate_bands_fft(data_intervals[j], sample_rate)
        
        sig1_bands = instantaneous_phase([sig1_delta, sig1_theta, sig1_alpha, sig1_beta, sig1_gamma])
        sig2_bands = instantaneous_phase([sig2_delta, sig2_theta, sig2_alpha, sig2_beta, sig2_gamma])
        
        complex_phase_diff_delta = np.exp(np.complex(0,1)*(sig1_bands[0] - sig2_bands[0]))
        complex_phase_diff_theta = np.exp(np.complex(0,1)*(sig1_bands[1] - sig2_bands[1]))
        complex_phase_diff_alpha = np.exp(np.complex(0,1)*(sig1_bands[2] - sig2_bands[2]))
        complex_phase_diff_beta = np.exp(np.complex(0,1)*(sig1_bands[3] - sig2_bands[3]))
        complex_phase_diff_gamma = np.exp(np.complex(0,1)*(sig1_bands[4] - sig2_bands[4]))
        
        plv_delta = np.abs(np.sum(complex_phase_diff_delta))/len(sig1_bands[0])
        plv_theta = np.abs(np.sum(complex_phase_diff_theta))/len(sig1_bands[1])
        plv_alpha = np.abs(np.sum(complex_phase_diff_alpha))/len(sig1_bands[2])
        plv_beta = np.abs(np.sum(complex_phase_diff_beta))/len(sig1_bands[3])
        plv_gamma = np.abs(np.sum(complex_phase_diff_gamma))/len(sig1_bands[4])
        
        return plv_delta, plv_theta, plv_alpha, plv_beta, plv_gamma
    
    if conn == 'pli':
        sig1_delta, sig1_theta, sig1_alpha, sig1_beta, sig1_gamma = calculate_bands_fft(data_intervals[i], sample_rate)
        sig2_delta, sig2_theta, sig2_alpha, sig2_beta, sig2_gamma = calculate_bands_fft(data_intervals[j], sample_rate)
        
        sig1_bands = instantaneous_phase([sig1_delta, sig1_theta, sig1_alpha, sig1_beta, sig1_gamma])
        sig2_bands = instantaneous_phase([sig2_delta, sig2_theta, sig2_alpha, sig2_beta, sig2_gamma])
        
        phase_diff_delta = sig1_bands[0] - sig2_bands[0]
        phase_diff_delta = (phase_diff_delta + np.pi) % (2 * np.pi) - np.pi
        
        phase_diff_theta = sig1_bands[1] - sig2_bands[1]
        phase_diff_theta = (phase_diff_theta + np.pi) % (2 * np.pi) - np.pi
        
        phase_diff_alpha = sig1_bands[2] - sig2_bands[2]
        phase_diff_alpha = (phase_diff_alpha + np.pi) % (2 * np.pi) - np.pi
        
        phase_diff_beta = sig1_bands[3] - sig2_bands[3]
        phase_diff_beta  = (phase_diff_beta  + np.pi) % (2 * np.pi) - np.pi
        
        phase_diff_gamma = sig1_bands[4] - sig2_bands[4]
        phase_diff_gamma  = (phase_diff_gamma  + np.pi) % (2 * np.pi) - np.pi
        
        pli_delta = abs(np.mean(np.sign(phase_diff_delta)))
        pli_theta = abs(np.mean(np.sign(phase_diff_theta)))
        pli_alpha = abs(np.mean(np.sign(phase_diff_alpha)))
        pli_beta = abs(np.mean(np.sign(phase_diff_beta)))
        pli_gamma = abs(np.mean(np.sign(phase_diff_gamma)))
        
        return pli_delta, pli_theta, pli_alpha, pli_beta, pli_gamma
    
    if conn == 'pli_no_bands':
        sig1_phase = instantaneous_phase([data_intervals[i]])
        sig2_phase = instantaneous_phase([data_intervals[j]])
        phase_diff = sig1_phase[0] - sig2_phase[0]
        phase_diff = (phase_diff  + np.pi) % (2 * np.pi) - np.pi
        pli = abs(np.mean(np.sign(phase_diff)))
        
        return pli

    
def instantaneous_phase(bands):
    for i,item in enumerate(bands):
        #First obtain the analytical signal with hilbert transformation. 
        bands[i] = signal.hilbert(item)
        #The instantaneous phase can then simply be obtained as the angle between the real and imaginary part of the analytic signal
        bands[i] = np.angle(bands[i])
    return bands


def calculate_dtf(data_intervals, steps, channels, sample_rate, bands):
    num_bands = sum(bands)
    intervals = (len(steps))
    matrix = np.zeros(shape=((intervals * num_bands), channels, channels))
    start, stop = 0, channels
    
    ws = scot.Workspace({'model_order': channels - 5}, reducedim = 'no_pca', nfft= int(sample_rate/2), fs = sample_rate)
    
    f = np.arange(0, int(sample_rate/2))
    
    #Loop over the number of intervals
    for k in range(intervals):
        #If there is more than one interval, the new start is the last stop and we calculate the new stop with the number of channels. 
        if k!=0:
            start = stop
            stop+= channels
            
        ws.set_data(data_intervals[start:stop])
        ws.do_mvarica()
        ws.fit_var()
        results = ws.get_connectivity('DTF')
        #Loop over 
        for x,i in enumerate(range(start, stop)):
            for y,j in enumerate(range(start, stop)):
                delta, theta, alpha, beta, gamma = frequency_bands(f, results[x][y])
                r=0
                for z, item in enumerate ([delta, theta, alpha, beta, gamma]):
                    if bands[z]:
                        matrix[(k * num_bands) + r][x,y] = item.mean()
                        r+=1                  
    return matrix

def calculate_connectivity_single_channel(data_intervals, sample_rate, conn):
    values = []
    
    for i in range (len(data_intervals)):
        values.append(single_channel_connectivity(data_intervals[i], sample_rate, conn))
    
    return values


def calculate_connectivity_single_channel_with_bands(data_intervals, sample_rate, conn, bands):
    values = []
    num_bands = sum(bands)
    
    for i in range (len(data_intervals)):
        delta, theta, alpha, beta, gamma = calculate_bands_fft(data_intervals[i], sample_rate)
        
        for z,item in enumerate([delta, theta, alpha, beta, gamma]):
            if bands[z]:
                values.append(single_channel_connectivity(item, sample_rate, conn))
                
    return values


def single_channel_connectivity(data, sample_rate, conn):
    #Power Spectrum
    #https://www.kite.com/python/answers/how-to-plot-a-power-spectrum-in-python
    if conn == 'ps':
        fourier_transform = np.fft.rfft(data)
        abs_fourier_transform = np.abs(fourier_transform)
        power_spectrum = np.square(abs_fourier_transform)
        return power_spectrum.mean()
       
    #Spectral Entropy
    #https://raphaelvallat.com/entropy/build/html/index.html
    if conn == 'se':
        se = spectral_entropy(data, sample_rate, method='welch', normalize=True)
        return se
    
    #Shannon Entropy
    #https://www.kite.com/python/answers/how-to-calculate-shannon-entropy-in-python
    if conn == 'she':
        pd_series = pd.Series(data)
        counts = pd_series.value_counts()
        she = entropy(counts)
        return she

def single_channel_graph(data, ch_names, channels, bands=None):     
    num_graphs = int(len(data)/channels)
    print("\nNumber of graphs created:", num_graphs)
    nodes = process_channel_names(ch_names)
    
    G = {}
    for i in range(num_graphs):
        G[i] = nx.Graph()
        G[i].add_nodes_from(nodes, values=5)
        elegible_nodes = []
        
        #Calculate the 75th percentile of the channels
        threshold = np.percentile(data[(i*channels):(((i+1)*channels)-1)], 75)

        for j in range(channels):
            if(data[(channels * i) + j]) > threshold:
                elegible_nodes.append(nodes[j])
        edges = combinations(elegible_nodes,2)        
        G[i].add_edges_from(edges, weight = 1, thickness=1)
        
     #For each graph, we call the helper function "draw_graph". 
    for k in range(num_graphs):
        #plt.figure(k, figsize=(12,12))
        #plt.title("--------------------------------\nGraph: " + str(k+1))
        fig = draw_graph(G[k], False, True)
        fig.update_layout(title='', plot_bgcolor='white' ) 
        fig.write_html('plot' + str(k+1) + '.html', auto_open=True, default_height='100%', default_width='100%')

#Visibility Graph
def calculate_visibility_graphs(data_intervals, kernel):
    VG = {}
    for i in range(len(data_intervals)):
        VG[i] = visibility_graph(data_intervals[i], kernel)
    
    return VG

def visibility_graph(series, kernel):
    G = nx.Graph()
    
    # convert list of magnitudes into list of tuples that hold the index
    tseries = []
    n = 0
    for magnitude in series:
        tseries.append( (n, magnitude ) )
        n += 1

    # contiguous time points always have visibility
    for n in range(0,len(tseries)-1):
        (ta, ya) = tseries[n]
        (tb, yb) = tseries[n+1]
        G.add_node(ta, mag=ya)
        G.add_node(tb, mag=yb)
        
        edge_weight = calculate_vg_weight(tseries, kernel, ta, tb, ya, yb)
        G.add_edge(ta, tb, weight = edge_weight)

    for a,b in combinations(tseries, 2):
        # two points, maybe connect
        (ta, ya) = a
        (tb, yb) = b

        connect = True
        
        # let's see all other points in the series
        for tc, yc in tseries[ta:tb]:
            # other points, not a or b
            if tc != ta and tc != tb:
                # does c obstruct?
                if yc > yb + (ya - yb) * ( (tb - tc) / (tb - ta) ):
                    connect = False
                    
        if connect:
            edge_weight = calculate_vg_weight(tseries, kernel, ta, tb, ya, yb)
            G.add_edge(ta, tb, weight = edge_weight)

    return G
    
def calculate_vg_weight(series, kernel, ta, tb, ya, yb):
    if kernel == 'binary':
        return 1
    
    #Mathur_2020
    if kernel == 'gaussian':
        std = np.std(series)
        return exp(-((abs(ta-tb))**2)/ (2*(std)**2))
    
    #Supriya_2016
    if kernel == 'weighted':
        return atan((yb - ya)/(tb-ta))

        
def make_graph(matrix, ch_names, threshold):
    """Process to create the networkX graphs.
    Parameters
    ----------
    matrix : ndarray
        Matrix containing all the correlation matrix.
    ch_names : list
        Channel names in the EEG.
    """
    #The number of graphs will be the number of correlation matrixes. 
    num_graphs = len(matrix)
    print("\nNumber of graphs created:", num_graphs)
    #Uses the helper function "process_channel_names" to obtain the names of the electrodes, to be used as nodes
    nodes = process_channel_names(ch_names)
    
    G = {}
    num_nodes = len(nodes)
    
    #Loop over the number of graphs, creating the nx Graph, adding the nodes (which will be the same in all graphs) and adding an edge if the connectivity measure is above the threshold.
    #Also we add a weight to the edge, to draw the edge´s size according to this value. It is the connectivity coefficient to a power, to really difference big from smaller coefficients. 
    for k in range(num_graphs):
        G[k] = nx.Graph()
        G[k].add_nodes_from(nodes)
        for i in range(num_nodes):
            for j in range(num_nodes):
                if matrix[k][i,j] > threshold and i!=j:
                    #print("graph:",k,"Edge between:", i,j)
                    G[k].add_edge(nodes[i],nodes[j], thickness = pow(matrix[k][i,j], 3) * 6, weight = matrix[k][i,j])
    
    #For each graph, we call the helper function "draw_graph". 
    for k in range(num_graphs):
        #plt.figure(k, figsize=(12,12))
        #plt.title("--------------------------------\nGraph: " + str(k+1))
        fig = draw_graph(G[k], False, False)
        fig.update_layout(title='', plot_bgcolor='white' ) 
        fig.write_html('plot' + str(k+1) + '.html', auto_open=True, default_height='100%', default_width='100%')
                   
    
    
def make_directed_graph(matrix, ch_names, threshold):
    
    #The number of graphs will be the number of correlation matrixes. 
    num_graphs = len(matrix)
    print("\nNumber of graphs created:", num_graphs)
    #Uses the helper function "process_channel_names" to obtain the names of the electrodes, to be used as nodes
    nodes = process_channel_names(ch_names)
    
    G = {}
    num_nodes = len(nodes)
    
    #Loop over the number of graphs, creating the nx Graph, adding the nodes (which will be the same in all graphs) and adding an edge if the connectivity measure is above the threshold.
    #Also we add a weight to the edge, to draw the edge´s size according to this value. It is the connectivity coefficient to a power, to really difference big from smaller coefficients. 
    for k in range(num_graphs):
        G[k] = nx.DiGraph()
        G[k].add_nodes_from(nodes)
        for i in range(num_nodes):
            for j in range(num_nodes):
                if matrix[k][i,j] > threshold and i!=j:
                    #print("graph:",k,"Edge between:", i,j)
                    G[k].add_edge(nodes[i],nodes[j], thickness = pow(matrix[k][i,j], 3) * 6, weight = matrix[k][i,j])
    
    #For each graph, we call the helper function "draw_graph". 
    for k in range(num_graphs):
        #plt.figure(k, figsize=(12,12))
        #plt.title("--------------------------------\nGraph: " + str(k+1))
        fig = draw_graph(G[k], True, False)
        fig.update_layout(title='', plot_bgcolor='white' ) 
        fig.write_html('plot' + str(k+1) + '.html', auto_open=True, default_height='100%', default_width='100%')
        
        
    
def process_channel_names(channel_names):
    """Process to obtain the electrode name from the channel name.
    Parameters
    ----------
    channel_names : list
        Channel names in the EEG.
    
    Returns
    -------
    channel_names : list
        Proccessed channel names, containing only the name of the electrode.
    """
    
    channel_names = [(elem.split())[-1] for elem in channel_names]
    channel_names = [(elem.replace("-", " ").split())[0] for elem in channel_names]
    print('Channel Names:', channel_names)
    
    return channel_names


def draw_graph(G, directed, hover_nodes):
    """Process to create the networkX graphs.
    Parameters
    ----------
    G : NetworkX graph
    """
    
    #Dictionary with all the possible electrode positions. 
    
    pos = {'Cz': (0,0), 'C2h': (1.2,0), 'C2': (2.5,0), 'C4h': (3.85,0), 'C4': (5,0),'C6h': (6.20,0), 'C6': (7.6,0), 'T8h': (8.9,0), 'T8': (10.1,0), 'T10h': (11.3,0), 'T10': (12.75,0), 
           'C1h': (-1.2,0), 'C1': (-2.5,0), 'C3h': (-3.85,0), 'C3': (-5,0), 'C5h': (-6.20,0),'C5': (-7.6,0), 'T7h': (-8.9,0), 'T7': (-10.1,0), 'T9h': (-11.3,0), 'T9': (-12.75,0),
           
           'CCPz': (0, -0.95), 'CCP2h': (1.15,-0.96), 'CCP2': (2.4,-0.97), 'CCP4h': (3.8,-0.98), 'CCP4': (4.98,-0.99), 'CCP6h': (6.10,-1), 'CCP6': (7.45,-1.05),'TTP8h': (8.7,-1.10),
           'TTP8': (10, -1.15), 'TTP10h': (11.15,-1.25), 'TTP10': (12.5,-1.4), 'CCP1h': (-1.15,-0.96), 'CCP1': (-2.4,-0.97), 'CCP3h': (-3.8,-0.98), 'CCP3': (-4.98,-0.99), 
           'CCP5h': (-6.10,-1), 'CCP5': (-7.45,-1.05), 'TTP7h': (-8.7,-1.10), 'TTP7': (-10, -1.15), 'TTP9h': (-11.15,-1.25), 'TTP9': (-12.5,-1.4), 
           
           'CPz': (0, -1.80), 'CP2h': (1.1, -1.83), 'CP2': (2.35, -1.87), 'CP4h': (3.65, -1.93), 'CP4': (4.85, -1.96), 'CP6h': (6,-2), 'CP6': (7.2,-2.05), 'TP8h': (8.3, -2.10),  
           'TP8': (9.7, -2.20), 'TP10h': (10.8, -2.5), 'TP10': (12, -2.85), 'CP1h': (-1.1, -1.83), 'CP1': (-2.35, -1.87), 'CP3h': (-3.65, -1.93), 'CP3': (-4.85, -1.96),
           'CP5h': (-6,-2), 'CP5': (-7.2,-2.05), 'TP7h': (-8.3, -2.10), 'TP7': (-9.7, -2.20), 'TP9h': (-10.8, -2.5), 'TP9': (-12, -2.85), 
           
           'CPPz': (0, -2.70), 'CPP2h': (1.10, -2.75), 'CPP2': (2.20, -2.80), 'CPP4h': (3.45, -2.85), 'CPP4': (4.55, -2.92), 'CPP6h': (5.65, -2.98), 'CPP6': (6.9, -3.05),
           'TPP8h': (7.95, -3.12), 'TPP8': (9, -3.20), 'TPP10h': (10.1, -3.8), 'TPP10': (11.2, -4.05), 'CPP1h': (-1.10, -2.75), 'CPP1': (-2.20, -2.80), 'CPP3h': (-3.45, -2.85), 
           'CPP3': (-4.55, -2.92), 'CPP5h': (-5.65, -2.98), 'CPP5': (-6.9, -3.05),'TPP7h': (-7.95, -3.12), 'TPP7': (-9, -3.20), 'TPP9h': (-10.1, -3.8), 'TPP9': (-11.2, -4.05),
           
           'Pz': (0, -3.6), 'P2h': (1, -3.63), 'P2': (2.05, -3.68), 'P4h': (3.05, -3.75), 'P4': (4.05, -3.83), 'P6h': (5.05, -3.91), 'P6': (6.1, -4), 'P8h': (7.10, -4.08), 
           'P8': (8.10, -4.17), 'P10h': (9.15, -4.85), 'P10': (10.15, -5.25), 'P1h': (-1, -3.63), 'P1': (-2.05, -3.68), 'P3h': (-3.05, -3.75), 'P3': (-4.05, -3.83), 
           'P5h': (-5.05, -3.91), 'P5': (-6.1, -4), 'P7h': (-7.10, -4.08), 'P7': (-8.10, -4.17), 'P9h': (-9.15, -4.85), 'P9': (-10.15, -5.25),
           
           'PPOz': (0, -4.5), 'PPO2h': (0.98, -4.54), 'PPO2': (1.90, -4.61), 'PPO4h': (2.8, -4.68), 'PPO4': (3.7, -4.75), 'PPO6h': (4.5, -4.82), 'PPO6': (5.3, -4.90), 
           'PPO8h': (6.2, -4.98), 'PPO8': (7.05, -5.05), 'PPO10h': (8, -5.75), 'PPO10': (8.95, -6.3), 'PPO1h': (-0.98, -4.54), 'PPO1': (-1.90, -4.61), 'PPO3h': (-2.8, -4.68), 
           'PPO3': (-3.7, -4.75), 'PPO5h': (-4.5, -4.82), 'PPO5': (-5.3, -4.90), 'PPO7h': (-6.2, -4.98), 'PPO7': (-7.05, -5.05), 'PPO9h': (-8, -5.75), 'PPO9': (-8.95, -6.3),
           
           'POz': (0, -5.4), 'PO2h': (0.8, -5.4), 'PO2': (1.5, -5.43), 'PO4h': (2.2, -5.48), 'PO4': (3, -5.53), 'PO6h': (3.75, -5.6), 'PO6': (4.4, -5.67), 'PO8h': (5.1, -5.74), 
           'PO8': (5.98, -5.81), 'PO10h': (6.8, -6.6), 'PO10': (7.4, -7.3), 'PO1h': (-0.8, -5.4), 'PO1': (-1.5, -5.43), 'PO3h': (-2.2, -5.48), 'PO3': (-3, -5.53), 
           'PO5h': (-3.75, -5.6), 'PO5': (-4.4, -5.67), 'PO7h': (-5.1, -5.74), 'PO7': (-5.98, -5.81), 'PO9h': (-6.8, -6.6), 'PO9': (-7.4, -7.3),
           
           'POOz': (0, -6.2), 'POO2': (1.1, -6.22), 'POO4': (2.2, -6.25), 'POO6': (3.4, -6.28), 'POO8': (4.6, -6.32), 'POO10h': (5.1, -7.1), 'POO10': (5.8, -8.05), 
           'POO1': (-1.1, -6.22), 'POO3': (-2.2, -6.25), 'POO5': (-3.4, -6.28), 'POO7': (-4.6, -6.32), 'POO9h': (-5.1, -7.1), 'POO9': (-5.8, -8.05),
           
           'Oz': (0, -7.2), 'O2h': (1.6, -7.1), 'O2': (3.15, -6.85), 'O1h': (-1.6, -7.1), 'O1': (-3.15, -6.85),
           
           'Olz': (0, -8.05), 'Ol2h': (1.6, -8), 'Ol2': (3.5, -7.75), 'Ol1h': (-1.6, -8), 'Ol1': (-3.5, -7.75), 
           
           'lz': (0, -9.05), 'l2h': (1.98, -8.95), 'l2': (3.85, -8.6), 'l1h': (-1.98, -8.95), 'l1': (-3.85, -8.6),
           
           'FCCz': (0, 0.95), 'FCC2h': (1.15,0.96), 'FCC2': (2.4, 0.97), 'FCC4h': (3.8, 0.98), 'FCC4': (4.98, 0.99), 'FCC6h': (6.10, 1), 'FCC6': (7.45, 1.05),'FTT8h': (8.7, 1.10),
           'FTT8': (10, 1.15), 'FTT10h': (11.15, 1.25), 'FTT10': (12.5, 1.4), 'FCC1h': (-1.15, 0.96), 'FCC1': (-2.4, 0.97), 'FCC3h': (-3.8, 0.98), 'FCC3': (-4.98, 0.99), 
           'FCC5h': (-6.10, 1), 'FCC5': (-7.45, 1.05), 'FTT7h': (-8.7, 1.10), 'FTT7': (-10, 1.15), 'FTT9h': (-11.15, 1.25), 'FTT9': (-12.5, 1.4), 
           
           'FCz': (0, 1.80), 'FC2h': (1.1, 1.83), 'FC2': (2.35, 1.87), 'FC4h': (3.65, 1.93), 'FC4': (4.85, 1.96), 'FC6h': (6, 2), 'FC6': (7.2, 2.05), 'FT8h': (8.3, 2.10),  
           'FT8': (9.7, 2.20), 'FT10h': (10.8, 2.5), 'FT10': (12, 2.85), 'FC1h': (-1.1, 1.83), 'FC1': (-2.35, 1.87), 'FC3h': (-3.65, 1.93), 'FC3': (-4.85, 1.96),
           'FC5h': (-6,2), 'FC5': (-7.2,2.05), 'FT7h': (-8.3, 2.10), 'FT7': (-9.7, 2.20), 'FT9h': (-10.8, 2.5), 'FT9': (-12, 2.85), 
           
           'FFCz': (0, 2.70), 'FFC2h': (1.10, 2.75), 'FFC2': (2.20, 2.80), 'FFC4h': (3.45, 2.85), 'FFC4': (4.55, 2.92), 'FFC6h': (5.65, 2.98), 'FFC6': (6.9, 3.05),
           'FFT8h': (7.95, 3.12), 'FFT8': (9, 3.20), 'FFT10h': (10.1, 3.8), 'FFT10': (11.2, 4.05), 'FFC1h': (-1.10, 2.75), 'FFC1': (-2.20, 2.80), 'FFC3h': (-3.45, 2.85), 
           'FFC3': (-4.55, 2.92), 'FFC5h': (-5.65, 2.98), 'FFC5': (-6.9, 3.05),'FFT7h': (-7.95, 3.12), 'FFT7': (-9, 3.20), 'FFT9h': (-10.1, 3.8), 'FFT9': (-11.2, 4.05),
           
           'Fz': (0, 3.6), 'F2h': (1, 3.63), 'F2': (2.05, 3.68), 'F4h': (3.05, 3.75), 'F4': (4.05, 3.83), 'F6h': (5.05, 3.91), 'F6': (6.1, 4), 'F8h': (7.10, 4.08), 
           'F8': (8.10, 4.17), 'F10h': (9.15, 4.85), 'F10': (10.15, 5.25), 'F1h': (-1, 3.63), 'F1': (-2.05, 3.68), 'F3h': (-3.05, 3.75), 'F3': (-4.05, 3.83), 
           'F5h': (-5.05, 3.91), 'F5': (-6.1, 4), 'F7h': (-7.10, 4.08), 'F7': (-8.10, 4.17), 'F9h': (-9.15, 4.85), 'F9': (-10.15, 5.25),
           
           'AFFz': (0, 4.5), 'AFF2h': (0.98, 4.54), 'AFF2': (1.90, 4.61), 'AFF4h': (2.8, 4.68), 'AFF4': (3.7, 4.75), 'AFF6h': (4.5, 4.82), 'AFF6': (5.3, 4.90), 
           'AFF8h': (6.2, 4.98), 'AFF8': (7.05, 5.05), 'AFF10h': (8, 5.75), 'AFF10': (8.95, 6.3), 'AFF1h': (-0.98, 4.54), 'AFF1': (-1.90, 4.61), 'AFF3h': (-2.8, 4.68), 
           'AFF3': (-3.7, 4.75), 'AFF5h': (-4.5, 4.82), 'AFF5': (-5.3, 4.90), 'AFF7h': (-6.2, 4.98), 'AFF7': (-7.05, 5.05), 'AFF9h': (-8, 5.75), 'AFF9': (-8.95, 6.3),
           
           'AFz': (0, 5.4), 'AF2h': (0.8, 5.4), 'AF2': (1.5, 5.43), 'AF4h': (2.2, 5.48), 'AF4': (3, 5.53), 'AF6h': (3.75, 5.6), 'AF6': (4.4, 5.67), 'AF8h': (5.1, 5.74), 
           'AF8': (5.98, 5.81), 'AF10h': (6.8, 6.6), 'AF10': (7.4, 7.3), 'AF1h': (-0.8, 5.4), 'AF1': (-1.5, 5.43), 'AF3h': (-2.2, 5.48), 'AF3': (-3, 5.53), 
           'AF5h': (-3.75, 5.6), 'AF5': (-4.4, 5.67), 'AF7h': (-5.1, 5.74), 'AF7': (-5.98, 5.81), 'AF9h': (-6.8, 6.6), 'AF9': (-7.4, 7.3),
           
           'AFpz': (0, 6.2), 'AFp2': (1.1, 6.22), 'AFp4': (2.2, 6.25), 'AFp6': (3.4, 6.28), 'AFp8': (4.6, 6.32), 'AFp10h': (5.1, 7.1), 'AFp10': (5.8, 8.05), 
           'AFp1': (-1.1, 6.22), 'AFp3': (-2.2, 6.25), 'AFp5': (-3.4, 6.28), 'AFp7': (-4.6, 6.32), 'AFp9h': (-5.1, 7.1), 'AFp9': (-5.8, 8.05),
           
           'Fpz': (0, 7.2), 'Fp2h': (1.6, 7.1), 'Fp2': (3.15, 6.85), 'Fp1h': (-1.6, 7.1), 'Fp1': (-3.15, 6.85),
           
           'NFpz': (0, 8.05), 'NFp2h': (1.6, 8), 'NFp2': (3.5, 7.75), 'NFp1h': (-1.6, 8), 'NFp1': (-3.5, 7.75), 
           
           'Nz': (0, 9.05), 'N2h': (1.98, 8.95), 'N2': (3.85, 8.6), 'N1h': (-1.98, 8.95), 'N1': (-3.85, 8.6),
           
           'T3': (-10.1,0), 'T4': (10.1,0), 'T5': (-8.10, -4.17), 'T6': (8.10, -4.17)
          }
    
    nx.set_node_attributes(G, pos, 'pos')
    edges = G.edges()
    nodes = G.nodes()
    visibility = []
    for i in edges:
        visibility.append(True)
    visibility.append(True)
    visibility.append(True)
    visibility.append(False)

    # convert to plotly graph
    edge_trace, eweights_trace_hover, eweights_trace_markers  = get_edge_trace(G)
    node_trace = get_node_trace(G)

    fig = go.Figure(data=(edge_trace + [node_trace,  eweights_trace_hover, eweights_trace_markers]),
                    layout=go.Layout(
                        titlefont_size=16,
                        showlegend=False,
                        margin=dict(b=40, l=0, r=350, t=30),
                        xaxis_visible=False,
                        yaxis_visible=False),
                    )
    
    fig.update_layout(updatemenus=[dict(
                                        type = "buttons",
                                        direction = "left",
                                        buttons=list([
                                            dict(
                                                args=[{"visible": visibility}],
                                                label="Hide edge markers",
                                                method="restyle"
                                            ),
                                            dict(
                                                args=[{"visible":[1]}],
                                                label="Show edge markers",
                                                method="restyle"
                                            )]))])
    
    if directed:
        edges_control = []
        for i,edge in enumerate(edges):
            x0, y0 = G.nodes[edge[0]]['pos']
            x1, y1 = G.nodes[edge[1]]['pos']
            
            #If there is another edge between the same nodes in the opposite direction
            if edge in edges_control:
                x0= x0 - 0.05
                y0= y0 + 0.05
                x1= x1 - 0.05
                y1= y1 + 0.05
                
            fig.add_annotation(
                ax=x0, ay=y0, axref='x', ayref='y',x=x1, y=y1, xref='x', yref='y', showarrow=True, arrowhead=1, arrowsize=2, standoff = 22, startstandoff = 15, opacity= 0.8
            )
            #We add the edge in the opposite direction to control edges between the same nodes
            edges_control.append((edge[1],edge[0]))
    return fig
    
    
def get_edge_trace(G):
    etext = [f'weight: {"{:.2f}".format(w)}' for w in list(nx.get_edge_attributes(G, 'weight').values())]
    xtext, ytext, edges_control = [], [], []
    
    edges = G.edges()
    weights = [G[u][v]['weight'] for u,v in edges]
    thickness = [G[u][v]['thickness'] for u,v in edges]
    
    edge_traces = {}
    
    for i, edge in enumerate (G.edges()):  
        edge_x = []
        edge_y = []
        
        x0, y0 = G.nodes[edge[0]]['pos']
        x1, y1 = G.nodes[edge[1]]['pos']
        
        #If there is another edge between the same nodes in the opposite direction
        if edge in edges_control:
            x0= x0 - 0.05
            y0= y0 + 0.05
            x1= x1 - 0.05
            y1= y1 + 0.05

        xtext.append((x0+x1)/2)
        ytext.append((y0+y1)/2)
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)
        width = thickness[i]

        #We add the edge in the opposite direction to control edges between the same nodes
        edges_control.append((edge[1],edge[0]))
        
        edge_traces['trace_' + str(i)] = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=width, color='#000'),
        mode='lines',
        hoverinfo='skip',
        )
    
    edge_trace = list(edge_traces.values())
    
    eweights_trace_hover = go.Scatter(x=xtext,y= ytext, mode='markers',
                              marker_size=0.5,
                              text= etext,
                              hoverlabel=dict(bgcolor='lightblue'),
                              hovertemplate='%{text}<extra></extra>')
    
    eweights_trace_markers = go.Scatter(x=xtext,y= ytext, mode='markers',
                                marker = dict( size=8, color='black'),
                                hoverinfo='none',
                                visible=False)
                        
    
    return edge_trace, eweights_trace_hover, eweights_trace_markers


def get_node_trace(G):
    node_x = []
    node_y = []
    for node in G.nodes():
        x, y = G.nodes[node]['pos']
        node_x.append(x)
        node_y.append(y)

    labels = [str(node) for node in G.nodes()]
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers + text',
        marker = dict( size=40 , color='lightskyblue', line=dict(color='#000', width=1)),
        text=labels,
        hoverinfo='none',
        textfont=dict(size=14)
            )

    return node_trace
