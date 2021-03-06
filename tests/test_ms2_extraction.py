# encoding: utf-8
from __future__ import print_function

import emzed
import pytest


@pytest.fixture
def peaks(path):
    peaks = emzed.io.loadTable(path("data", "peaks_for_ms2_extraction.table"))

    # in order to reduce output for regtest:
    peaks.dropColumns("feature_id", "intensity", "quality", "fwhm", "z", "source")

    # additionally reduces output:
    return peaks.filter((peaks.id <= 6) | (peaks.id > 17))


@pytest.fixture
def peakmap(path):
    return emzed.io.loadPeakMap(path("data", "peaks_for_ms2_extraction.mzXML"))


def check(peaks, peakmap, regtest, mode):
    print(file=regtest)
    print("MODE=", mode, file=regtest)
    print(file=regtest)

    emzed.utils.attach_ms2_spectra(peaks, peakmap, mode=mode)

    def mz_range(spectra):
        mzs = [mz for s in spectra for mz in s.peaks[:, 0]]
        if not mzs:
            return None
        return max(mzs) - min(mzs)

    def energy(spectra):
        iis = [ii for s in spectra for ii in s.peaks[:, 1]]
        return sum(i * i for i in iis)

    peaks.addColumn("ms2_mz_range", peaks.spectra_ms2.apply(mz_range), type_=float)
    peaks.addColumn("ms2_energy", peaks.spectra_ms2.apply(energy), type_=float, format_="%.2e")
    peaks.setColFormat("spectra_ms2", None)

    print(peaks, file=regtest)


def test_mode_is_intersection(peaks, peakmap, regtest):
    check(peaks, peakmap, regtest, "intersection")


def test_mode_is_union(peaks, peakmap, regtest):
    check(peaks, peakmap, regtest, "union")


def test_mode_is_union_no_overlap(peaks, peakmap, regtest):
    Spectrum = emzed.core.data_types.Spectrum
    PeakMap = emzed.core.data_types.PeakMap

    # we create an artificial peakmap with non overlapping ms2 spectra
    spectra = []
    for s in peakmap:
        if s.msLevel == 2:
            n = s.peaks.shape[0]
            peaks1 = s.peaks[:n/2, :]
            peaks2 = s.peaks[n/2 + 1:, :]
            spectra.append(Spectrum(peaks1, s.rt, 2, s.polarity, s.precursors))
            spectra.append(Spectrum(peaks2, s.rt, 2, s.polarity, s.precursors))

    peakmap = PeakMap(spectra)
    check(peaks, peakmap, regtest, "union")


def test_mode_is_max_range(peaks, peakmap, regtest):
    check(peaks, peakmap, regtest, "max_range")


def test_mode_is_max_energy(peaks, peakmap, regtest):
    check(peaks, peakmap, regtest, "max_energy")


def test_mode_is_all(peaks, peakmap, regtest):
    check(peaks, peakmap, regtest, "all")


def test_overlay(peakmap, regtest):
    overlay = emzed.utils.overlay_spectra(peakmap.spectra[5:10])
    print(overlay.peaks.shape, file=regtest)
    print(overlay.peaks, file=regtest)

    common = emzed.utils.overlay_spectra(peakmap.spectra[5:10], mode="intersection")
    print(common.peaks.shape, file=regtest)
    print(common.peaks, file=regtest)
