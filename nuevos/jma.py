import numpy as np
from obspy import read
from scipy.fft import fft, ifft, fftfreq
import argparse


def jma_filters(frequencies):
    f = frequencies
    x = f / 10.0
    with np.errstate(divide='ignore', invalid='ignore'):
        F1 = np.sqrt(1.0 / np.where(f > 0, f, np.inf))
    F2 = (1 + 0.694 * x**2 + 0.241 * x**4 + 0.0557 * x**6
          + 0.009664 * x**8 + 0.00134 * x**10 + 0.000155 * x**12) ** -0.5
    F3 = np.sqrt(1 - np.exp(-(f / 0.5)**3))
    return F1 * F2 * F3


def compute_jma_intensity(acc_ns, acc_ew, acc_up, fs=200.0):
    n = len(acc_ns)
    freqs = fftfreq(n, d=1/fs)

    def filter_component(acc):
        A_f = fft(acc)
        filt = jma_filters(np.abs(freqs))
        return np.real(ifft(A_f * filt))

    ns_filt = filter_component(acc_ns)
    ew_filt = filter_component(acc_ew)
    up_filt = filter_component(acc_up)

    a_comp = np.sqrt(ns_filt**2 + ew_filt**2 + up_filt**2)

    def find_a0():
        lo, hi = 0.0, np.max(a_comp)
        target_samples = int(0.3 * fs)
        for _ in range(50):
            mid = (lo + hi) / 2
            count = np.sum(a_comp >= mid)
            if count > target_samples:
                lo = mid
            else:
                hi = mid
        return lo

    a0 = find_a0()

    if a0 <= 0:
        return {
            "a0_gal": a0,
            "I_continuous": 0.0,
            "I_truncated": 0.0,
            "JMA_intensity": 0
        }

    I = 2 * np.log10(a0) + 0.94
    I_rounded = round(I, 3)
    I_truncated = np.floor(I_rounded * 100) / 100.0

    def classify_intensity(I_val):
        if I_val < 0.5:
            return 0
        elif I_val < 1.5:
            return 1
        elif I_val < 2.5:
            return 2
        elif I_val < 3.5:
            return 3
        elif I_val < 4.5:
            return 4
        elif I_val < 5.0:
            return "5−"
        elif I_val < 5.5:
            return "5+"
        elif I_val < 6.0:
            return "6−"
        elif I_val < 6.5:
            return "6+"
        else:
            return 7

    jma_level = classify_intensity(I_truncated)

    return {
        "a0_gal": round(a0, 3),
        "I_continuous": I_rounded,
        "I_truncated": I_truncated,
        "JMA_intensity": jma_level
    }


def load_components_from_miniseed(file_path):
    st = read(file_path)
    if len(st) < 3:
        raise ValueError("Expected at least 3 traces in the MiniSEED file (NS, EW, UP)")

    # Try to match components by channel code endings
    components = {'N': None, 'E': None, 'Z': None}
    for tr in st:
        channel = tr.stats.channel.upper()
        if channel.endswith("N") or channel.endswith("1"):
            components['N'] = tr
        elif channel.endswith("E") or channel.endswith("2"):
            components['E'] = tr
        elif channel.endswith("Z"):
            components['Z'] = tr

    if not all(components.values()):
        raise ValueError("Could not find all 3 components (N, E, Z) in MiniSEED file.")

    # Extract data and ensure same length
    acc_ns = components['N'].data.astype(np.float64)*100
    acc_ew = components['E'].data.astype(np.float64)*100
    acc_up = components['Z'].data.astype(np.float64)*100
    fs = components['N'].stats.sampling_rate

    min_len = min(len(acc_ns), len(acc_ew), len(acc_up))
    acc_ns = acc_ns[:min_len]
    acc_ew = acc_ew[:min_len]
    acc_up = acc_up[:min_len]

    return acc_ns, acc_ew, acc_up, fs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute JMA Intensity from a MiniSEED file containing all 3 components.")
    parser.add_argument("mseed_file", help="MiniSEED file with NS, EW, and UP acceleration (in gals)")
    args = parser.parse_args()

    acc_ns, acc_ew, acc_up, fs = load_components_from_miniseed(args.mseed_file)

    result = compute_jma_intensity(acc_ns, acc_ew, acc_up, fs)

    print("\n📊 JMA Instrumental Seismic Intensity Results")
    print("============================================")
    print(f"Threshold a₀ (gal):       {result['a0_gal']}")
    print(f"Continuous intensity (I): {result['I_continuous']}")
    print(f"Truncated intensity (I):  {result['I_truncated']}")
    print(f"JMA Intensity Level:      {result['JMA_intensity']}")
