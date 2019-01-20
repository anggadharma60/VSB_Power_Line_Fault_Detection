

import os
from datetime import datetime
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
import scipy
import pywt
import peakutils
from statsmodels.robust import mad
import collections
from matplotlib import pyplot as plt
import seaborn as sns



# Loads the meta data file that maps columns to data samples and phases
def load_metadata(source_meta):  
    df = pd.read_csv(source_meta)
    min_id = min(df.id_measurement)
    max_id = max(df.id_measurement)
    return df, min_id, max_id

# Returns a dataframe with the three phase measurement time series
def load_sample(source_data, idx_start, idx_stop):  
    df = pq.read_pandas(source_data, columns=[str(i) for i in range(idx_start, idx_stop + 1)]).to_pandas()
    return df


def plot_signal(phase0, phase1, phase2, plot_title):
    fig=plt.figure(figsize=(15, 8), dpi= 80, facecolor='w', edgecolor='k')
    plot_labels = ['Phase_0', 'Phase_1', 'Phase_2']
    blues = ["#66D7EB", "#51ACC5", "#3E849E", "#2C5F78", "#1C3D52", "#0E1E2B"]
    #plt.plot(list(range(len(subset_train))), subset_train["0"], '-', label=plot_labels[0], color=blues[0])  # TODO Template
    plt.plot(list(range(len(phase0))), phase0, '-', label=plot_labels[0], color=blues[0])
    plt.plot(list(range(len(phase1))), phase1, '-', label=plot_labels[1], color=blues[1])
    plt.plot(list(range(len(phase2))), phase2, '-', label=plot_labels[2], color=blues[2])
    plt.legend(loc='lower right')
    plt.title(plot_title)
    plt.xlabel('Sample')
    plt.ylabel('Amplitude [bit]')
    # TODO fix y-axis
    plt.show()
    return


# Discrete Wavelet Transform on the Signal to Remove Noise
def discete_wavelet_transform(signal, wavelet="db4", level=1, plot_enable=False, title=None):
    coeff = pywt.wavedec( signal, wavelet, mode="per")  # calculate the wavelet coefficients
    sigma = mad(coeff[-level])  # calculate a threshold
    uthresh = sigma * np.sqrt(2*np.log(len(signal)))  # changing this threshold also changes the behavior, but hasn't been adjusted much
    coeff[1:] = (pywt.threshold(i, value=uthresh, mode="soft") for i in coeff[1:])
    dwt_signal = pywt.waverec(coeff, wavelet, mode="per")  # reconstruct the signal using the thresholded coefficients

    if plot_enable:
        f, ax = plt.subplots(figsize=(15, 8), dpi= 80, facecolor='w', edgecolor='k')
        blues = ["#66D7EB", "#51ACC5", "#3E849E", "#2C5F78", "#1C3D52", "#0E1E2B"]
        plt.plot(signal, color="#66D7EB", alpha=0.5) # plot original noisy signal with some transparency
        plt.plot(dwt_signal, color="#2C5F78")  # plot the smoothed DWT signal on top of the original
        plt.ylim((-60, 60))
        if title:
            ax.set_title(title)
        ax.set_xlim((0,len(dwt_signal)))
        plt.show()
    return dwt_signal


# Detrend Sinusoidal Behavior to "flatten" signal
def detrend_signal(signal):
    return np.diff(signal, n=1, axis=-1)  # Calculate the n-th discrete difference along the given axis


#  Feature Extraction Functions
def calculate_entropy(signal):
    counter_values = collections.Counter(signal).most_common()
    probabilities = [elem[1]/len(signal) for elem in counter_values]
    entropy=scipy.stats.entropy(probabilities)
    return entropy

def calculate_statistics(signal):
    n5 = np.nanpercentile(signal, 5)
    n25 = np.nanpercentile(signal, 25)
    n75 = np.nanpercentile(signal, 75)
    n95 = np.nanpercentile(signal, 95)
    median = np.nanpercentile(signal, 50)
    mean = np.nanmean(signal)
    std = np.nanstd(signal)
    var = np.nanvar(signal)
    rms = np.nanmean(np.sqrt(signal**2))
    return [n5, n25, n75, n95, median, mean, std, var, rms]
 
def calculate_crossings(signal):
    zero_crossing_indices = np.nonzero(np.diff(np.array(signal) > 0))[0]
    no_zero_crossings = len(zero_crossing_indices)
    mean_crossing_indices = np.nonzero(np.diff(np.array(signal) > np.nanmean(signal)))[0]
    no_mean_crossings = len(mean_crossing_indices)
    return [no_zero_crossings, no_mean_crossings]  # TODO no_mean_crossings a very promising feature!!!!

def calculate_peak_widths(peak_idxs):
    tmp_w = 1
    widths = []
    for idx in range(1,len(peak_idxs)):
        if peak_idxs[idx]-peak_idxs[idx-1] < 3:
            tmp_w +=1
        else:
            widths.append(tmp_w)
            tmp_w = 1
    widths.append(tmp_w)
    min_width = min(np.array(widths))
    max_width = max(np.array(widths))
    mean_width = np.nanmean(np.array(widths))
    num_true_peaks = len(widths)

    return min_width, max_width, mean_width, num_true_peaks

def calculate_peaks(signal):
    peak_indexes = peakutils.indexes(signal, thres=0.5, min_dist=1)  # where peaks are
    peak_values = signal[peak_indexes]
    num_detect_peak = len(peak_indexes)
    if num_detect_peak > 0:
        min_height = min(peak_values)
        max_height = max(peak_values)
        mean_height = np.nanmean(peak_values)
        min_width, max_width, mean_width, num_true_peaks = calculate_peak_widths(peak_indexes)
        return [min_height, max_height, mean_height, min_width, max_width, mean_width, num_detect_peak, num_true_peaks]
    else:
        return [0, 0, 0, 0, 0, 0, 0, 0]


# Extract features from the signal and build an array of them
def get_features(signal):
    entropy = calculate_entropy(signal)
    crossings = calculate_crossings(signal)
    statistics = calculate_statistics(signal)
    peaks = calculate_peaks(signal)
    return [entropy] + crossings + statistics + peaks

# Store Extracted Features in Features Dataframe for input to machine learning models
def store_features(df, features):
    phase0_features = get_features()
    phase1_features = get_features()
    phase2_features = get_features()
    features = phase0_features + phase1_features + phase2_features
    # TODO Complete, and is it best to seperate features
    return df

def classifier_vote():
    # TODO for three phase signals, classify each idependently, then have a best of 3 voting mechanism to classify the complete sample
    return classification

def create_feature_matrix():
    feature_matrix_columns = ["signal_id", "measurement_id", "entropy", "n5", "n25", "n75", "n95", "median", "mean", "std", "var", "rms", "no_zero_crossings", "no_mean_crossings", "min_height", "max_height", "mean_height", "min_width", "max_width", "mean_width", "num_detect_peak", "num_true_peaks", "fault"]
    feature_matrix = pd.DataFrame([], columns=feature_matrix_columns)
    return feature_matrix, feature_matrix_columns

def vsb_feature_extraction(source_meta, source_data, data_type, dwt_type):
    
    df_meta, min_id, max_id = load_metadata(source_meta)  # retrieve relevant meta data for training or test
    feature_matrix, feature_matrix_columns = create_feature_matrix()  # create new feature matrix data frame

    for measurement_id in range(min_id, max_id+1):
        measurement_meta_df = df_meta[df_meta["id_measurement"]==measurement_id]
        signal_ids = measurement_meta_df.signal_id.tolist()  # example [8709, 8710, 8711]
        #print(signal_ids)  # example [8709, 8710, 8711]
        sample_df = load_sample(source_data, signal_ids[0], signal_ids[2])

        # Raw Signal from Data
        phase0_raw_signal = sample_df[str(signal_ids[0])]
        phase1_raw_signal = sample_df[str(signal_ids[1])]
        phase2_raw_signal = sample_df[str(signal_ids[2])]

        # Denoise the Raw Signal with Discrete Wavelet Transform
        phase0_dwt_signal = discete_wavelet_transform(phase0_raw_signal, wavelet=dwt_type, level=1, plot_enable=False)
        phase1_dwt_signal = discete_wavelet_transform(phase1_raw_signal, wavelet=dwt_type, level=1, plot_enable=False)
        phase2_dwt_signal = discete_wavelet_transform(phase2_raw_signal, wavelet=dwt_type, level=1, plot_enable=False)

        # Detrend the Transformed Signal to "Flatten" it
        phase0_dwt_detrend_signal = detrend_signal(phase0_dwt_signal)
        phase1_dwt_detrend_signal = detrend_signal(phase1_dwt_signal)
        phase2_dwt_detrend_signal = detrend_signal(phase2_dwt_signal)

        # Perform Feature Extraction on the Transformed, "Flattened" Signal
        phase0_features = get_features(phase0_dwt_detrend_signal)
        phase1_features = get_features(phase1_dwt_detrend_signal)
        phase2_features = get_features(phase2_dwt_detrend_signal)

        # Stage Feature Arrays for Addition to Feature Matrix
        if data_type.lower() == "train":
            phase0_features_df = pd.DataFrame([[signal_ids[0], measurement_id] + phase0_features + [df_meta.target[df_meta.signal_id == signal_ids[0]].values[0]]], columns=feature_matrix_columns)
            phase1_features_df = pd.DataFrame([[signal_ids[1], measurement_id] + phase0_features + [df_meta.target[df_meta.signal_id == signal_ids[1]].values[0]]], columns=feature_matrix_columns)
            phase2_features_df = pd.DataFrame([[signal_ids[2], measurement_id] + phase0_features + [df_meta.target[df_meta.signal_id == signal_ids[2]].values[0]]], columns=feature_matrix_columns)
        else:  # for test data
            phase0_features_df = pd.DataFrame([[signal_ids[0], measurement_id] + phase0_features + [np.NaN]], columns=feature_matrix_columns)
            phase1_features_df = pd.DataFrame([[signal_ids[1], measurement_id] + phase0_features + [np.NaN]], columns=feature_matrix_columns)
            phase2_features_df = pd.DataFrame([[signal_ids[2], measurement_id] + phase0_features + [np.NaN]], columns=feature_matrix_columns)

        # Append Feature Matrix Data Frame
        feature_matrix = feature_matrix.append(phase0_features_df, ignore_index=True)
        feature_matrix = feature_matrix.append(phase1_features_df, ignore_index=True)
        feature_matrix = feature_matrix.append(phase2_features_df, ignore_index=True)
        
        if measurement_id%500 == 0:
            print("Now processing measurement_id: "+str(measurement_id)+" at "+datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # After processing and extracting features from each signal in the test set, save feature matrix
    feature_matrix.to_csv("extracted_features/"+data_type+"_features_"+dwt_type+".csv", sep=",")



# Discrete Wavelet Transform Types
Discrete_Meyer = ["dmey"]
Daubechies = ["db1", "db2", "db3", "db4", "db5", "db6", "db7", "db8", "db9", "db10", "db11", "db12", "db13", "db14", "db15", "db16", "db17", "db18", "db19", "db20"]
Symlets = ["sym2", "sym3", "sym4", "sym5", "sym6", "sym7", "sym8", "sym9", "sym10", "sym11", "sym12", "sym13", "sym14", "sym15", "sym16", "sym17", "sym18", "sym19", "sym20"]
Coiflet = ["coif1", "coif2", "coif3", "coif4", "coif5"]
Biorthogonal = ["bior1.1", "bior1.3", "bior1.5", "bior2.2", "bior2.4", "bior2.6", "bior2.8", "bior3.1", "bior3.3", "bior3.5", "bior3.7", "bior3.9", "bior4.4", "bior5.5", "bior6.8"]
Reverse_Biorthogonal = ["rbio1.1", "rbio1.3", "rbio1.5", "rbio1.2", "rbio1.4", "rbio1.6", "rbio1.8", "rbio3.1", "rbio3.3", "rbio3.5", "rbio3.7", "rbio3.9", "rbio4.4", "rbio5.5", "rbio6.8"]

#dwt_types = Discrete_Meyer + Coiflet
#dwt_types = Daubechies[1:4] + Symlets[1:4]
#dwt_types = Daubechies[5:6] 
#dwt_types = Daubechies[4:5] + Daubechies[6:10] 
dwt_types = ["db4", "db5"]

# Data Source
source_data = "/home/jeffrey/repos/VSB_Power_Line_Fault_Detection/source_data/train.parquet"
source_meta = "/home/jeffrey/repos/VSB_Power_Line_Fault_Detection/source_data/metadata_train.csv"
data_type = "train"

source_data = "/home/jeffrey/repos/VSB_Power_Line_Fault_Detection/source_data/test.parquet"
source_meta = "/home/jeffrey/repos/VSB_Power_Line_Fault_Detection/source_data/metadata_test.csv"
data_type = "test"

for dwt_type in dwt_types:
    print("Starting signal processing and feature extraction on "+data_type+" data with the "+dwt_type+" transform at "+datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    vsb_feature_extraction(source_meta, source_data, data_type, dwt_type)
print("Done! at "+datetime.now().strftime('%Y-%m-%d %H:%M:%S'))