# encoding: utf-8
from __future__ import print_function

from _filter_criteria import FilterCriteria as _FilterCriteria
from _choose_range import ChooseRange as _ChooseRange
from _choose_value import ChooseValue as _ChooseValue

from PyQt4 import QtCore, QtGui


class _ChooseNumberRange(_ChooseRange):

    INDICATE_CHANGE = QtCore.pyqtSignal(str)

    def __init__(self, name, table, min_=None, max_=None, parent=None):
        super(_ChooseNumberRange, self).__init__(parent)
        self.name = name
        self.table = table
        self.column_name.setText(self.name)
        if min_ is not None:
            self.lower_bound.setText(min_)
        if max_ is not None:
            self.upper_bound.setText(max_)

    def setupUi(self, parent):
        super(_ChooseNumberRange, self).setupUi(self)
        self.lower_bound.setMinimumWidth(40)
        self.upper_bound.setMinimumWidth(40)
        self.lower_bound.returnPressed.connect(self.return_pressed)
        self.upper_bound.returnPressed.connect(self.return_pressed)

    def return_pressed(self):
        self.INDICATE_CHANGE.emit(self.name)

    def update(self):
        pass


class ChooseFloatRange(_ChooseNumberRange):

    def get_limits(self):
        v1 = str(self.lower_bound.text()).strip()
        v2 = str(self.upper_bound.text()).strip()
        try:
            v1 = float(v1) if v1 else None
        except Exception:
            v1 = None
        try:
            v2 = float(v2) if v2 else None
        except Exception:
            v2 = None
        return self.name, v1, v2


class ChooseIntRange(_ChooseNumberRange):

    def get_limits(self):
        v1 = str(self.lower_bound.text()).strip()
        v2 = str(self.upper_bound.text()).strip()
        try:
            v1 = int(v1) if v1 else None
        except Exception:
            v1 = None
        try:
            v2 = int(v2) if v2 else None
        except Exception:
            v2 = None
        return self.name, v1, v2


class ChooseTimeRange(_ChooseNumberRange):

    def __init__(self, name, table, min_=None, max_=None, parent=None):
        super(ChooseTimeRange, self).__init__(name, table, min_, max_, parent)
        self.column_name.setText("%s [m]" % self.name)

    def get_limits(self):
        v1 = str(self.lower_bound.text()).strip()
        v2 = str(self.upper_bound.text()).strip()
        v1 = v1.rstrip("m").rstrip()
        v2 = v2.rstrip("m").rstrip()
        try:
            v1 = 60.0 * float(v1) if v1 else None
        except Exception:
            v1 = None
        try:
            v2 = 60.0 * float(v2) if v2 else None
        except Exception:
            v2 = None
        return self.name, v1, v2


class ChooseValue(_ChooseValue):

    INDICATE_CHANGE = QtCore.pyqtSignal(str)

    def __init__(self, name, table, parent=None):
        super(ChooseValue, self).__init__(parent)
        self.name = name
        self.table = table
        self.column_name.setText(self.name)
        self.update()

    def setupUi(self, parent):
        super(ChooseValue, self).setupUi(self)
        self.values.currentIndexChanged.connect(self.choice_changed)

    def choice_changed(self, *a):
        self.INDICATE_CHANGE.emit(self.name)

    def get_limits(self, *a):
        t = self.pure_values[self.values.currentIndex()]
        return self.name, t, t

    def update(self):
        before = self.values.currentText()
        values = sorted(set(self.table.getColumn(self.name).values))
        print("update for values", self.name, values)
        self.pure_values = [None] + values
        self.values.clear()
        new_items = [""] + map(str, values)
        self.values.addItems(new_items)
        if before in new_items:
            self.values.setCurrentIndex(new_items.index(before))


class FilterCriteria(_FilterCriteria):

    LIMITS_CHANGED = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super(FilterCriteria, self).__init__(parent=parent)
        self.choosers = []

    def addChooser(self, chooser):
        self.horizontalLayout.addWidget(chooser)
        self.horizontalLayout.setAlignment(chooser, QtCore.Qt.AlignTop)
        chooser.INDICATE_CHANGE.connect(self.value_commited)
        self.choosers.append(chooser)

    def update(self, name):
        for chooser in self.choosers:
            if chooser.name == name:
                chooser.update()

    def value_commited(self, name):
        limits = {}
        for chooser in self.choosers:
            name, min_, max_ = chooser.get_limits()
            limits[name] = (min_, max_)
        self.LIMITS_CHANGED.emit(limits)

    def number_of_choosers(self):
        return self.horizontalLayout.count()


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    fc = FilterCriteria()
    fc.addChooser(ChooseValue("pol", ("+", "-")))
    fc.addChooser(ChooseFloatRange("mz"))
    fc.show()
    sys.exit(app.exec_())
