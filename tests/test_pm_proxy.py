# encoding: utf-8
from __future__ import print_function


import emzed


def test_0(path):
    from emzed.core.data_types.ms_types import PeakMapProxy
    pm = PeakMapProxy(path("data/SHORT_MS2_FILE.mzData"))
    # this will trigger loading:
    n = len(pm)
    assert n == 41


def test_1(path, tmpdir):
    from emzed.core.data_types.ms_types import PeakMapProxy
    pm = emzed.io.loadPeakMap(path("data/SHORT_MS2_FILE.mzData"))
    t = emzed.utils.toTable("id", (1, 2, 3), type_=int)
    t.addColumn("peakmap", pm, type_=object)
    t.store(tmpdir.join("without_comp.table").strpath, True)
    t.store(tmpdir.join("with_comp.table").strpath, True, True, peakmap_cache_folder=tmpdir.strpath)

    tn = emzed.io.loadTable(tmpdir.join("with_comp.table").strpath)
    pm = tn.peakmap.uniqueValue()
    assert isinstance(pm, PeakMapProxy)
    assert len(pm) == 41

    t.store(tmpdir.join("with_comp_2.table").strpath, True, True, peakmap_cache_folder=tmpdir.strpath)

    tn = emzed.io.loadTable(tmpdir.join("with_comp_2.table").strpath)
    pm = tn.peakmap.uniqueValue()
    assert isinstance(pm, PeakMapProxy)
    assert len(pm) == 41
