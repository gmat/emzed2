import emzed.utils
import emzed.io
import os.path as osp


def test_formula():
    mf1 = emzed.utils.formula("H2O")
    mf2 = emzed.utils.formula("CH2O")
    assert str(mf1+mf2) == "CH4O2"
    mf3 = mf1 + mf2 - mf2
    assert str(mf3) == "H2O"


def test_load_map(path, tmpdir):
    from_ = path(u"data/SHORT_MS2_FILE.mzData")
    ds = emzed.io.loadPeakMap(from_)
    assert osp.basename(ds.meta.get("source")) ==  osp.basename(from_)

    # with unicode
    emzed.io.storePeakMap(ds, tmpdir.join("utilstest.mzML").strpath)
    ds2 = emzed.io.loadPeakMap(tmpdir.join("utilstest.mzML").strpath)
    assert len(ds)==len(ds2)

    # without unicode
    emzed.io.storePeakMap(ds2, tmpdir.join("utilstest.mzData").strpath)
    ds3 = emzed.io.loadPeakMap(tmpdir.join("utilstest.mzData").strpath)
    assert len(ds)==len(ds3)


def test_merge_tables():
    t1 = emzed.utils.toTable("a", [1,2])
    t2 = emzed.utils.mergeTables([t1, t1])
    assert len(t2) == 2*len(t1)

