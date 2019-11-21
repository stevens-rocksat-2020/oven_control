from multiprocessing import Queue

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import sys
from oven.oven_pb2 import OvenStatus as OvenStatusProto
import oven.oven_pb2 as oven_proto
import reflow_curve
import serial_connection

class CurvePlotter:
    def __init__(self, curve):
        self.data = np.empty(100)
        self.ptr = 0
        self.curve = curve

    def add_point(self, data):
        self.data[self.ptr] = data
        self.ptr += 1
        if self.ptr >= self.data.shape[0]:
            tmp = self.data
            self.data = np.empty(self.data.shape[0] * 2)
            self.data[:tmp.shape[0]] = tmp
        self.curve.setData(self.data[:self.ptr])
        self.curve.setPos(-self.ptr, 0)


class ToggleButton(QtGui.QWidget):
    def __init__(self, label, callback=lambda x: None, description=None):
        super(ToggleButton, self).__init__()

        self.callback = callback

        label = QtGui.QLabel(label)
        btn = QtGui.QPushButton("on")
        btn2 = QtGui.QPushButton("off")

        btn.clicked.connect(self.on_clicked)
        btn2.clicked.connect(self.off_clicked)
        layout = QtGui.QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(label)
        layout.addStretch(1)
        if description is not None:
            layout.addWidget(QtGui.QLabel(description))
        layout.addWidget(btn)
        layout.addWidget(btn2)

    def on_clicked(self):
        self.callback(True)

    def off_clicked(self):
        self.callback(False)


class OvenState(QtGui.QWidget):
    def __init__(self, callback=lambda x: None):
        super(OvenState, self).__init__()

        self.callback = callback

        label = QtGui.QLabel("Current Status:")
        self.status_label = QtGui.QLabel("OFF")
        btn1 = QtGui.QPushButton("off")
        btn2 = QtGui.QPushButton("on")
        btn3 = QtGui.QPushButton("profile")
        btn1.clicked.connect(lambda: self.callback("off"))
        btn2.clicked.connect(lambda: self.callback("on"))
        btn3.clicked.connect(lambda: self.callback("profile"))

        layout = QtGui.QHBoxLayout()
        self.setLayout(layout)

        for w in [label, self.status_label, btn1, btn2, btn3]:
            layout.addWidget(w)

    def set_status(self, status):
        self.status_label.setText(status)


class TempSetter(QtGui.QWidget):
    def __init__(self, callback=lambda x: None):
        super(TempSetter, self).__init__()

        self.callback = callback

        label = QtGui.QLabel("Set Temp:")
        self.temp_label = QtGui.QLabel("0 °C")
        self.temp_box = QtGui.QLineEdit()
        btn = QtGui.QPushButton("Set")
        btn.clicked.connect(self.temp_callback)

        layout = QtGui.QHBoxLayout()
        self.setLayout(layout)

        for w in [label, self.temp_label, self.temp_box, btn]:
            layout.addWidget(w)

    def temp_callback(self):
        self.callback(float(self.temp_box.text()))

    def set_temp(self, temp):
        self.temp_label.setText(f"{temp} °C")


class OvenControl(QtGui.QWidget):
    def __init__(self, controller: serial_connection.Controller):
        super(OvenControl, self).__init__()

        self.controller = controller
        layout = QtGui.QVBoxLayout()
        self.oven_state = OvenState(self.oven_state_callback)
        self.temp_setter = TempSetter(self.temp_callback)
        self.output_power = QtGui.QLabel("Output power: 0")

        layout.addWidget(self.oven_state)
        layout.addWidget(self.temp_setter)
        layout.addWidget(self.output_power)

        self.pidControl = PIDControl(controller)
        layout.addWidget(self.pidControl)

        self.setLayout(layout)

    def oven_state_callback(self, new_state: str):
        print(f"oven_state_callback() {new_state}")
        if new_state == "profile":
            self.controller.set_oven_configuration(reflow_curve.reflow_profile_configuration())
        self.controller.set_oven_status(oven_proto.OvenState.Value(new_state.upper()))
        pass

    def temp_callback(self, new_temp):
        # print(f"temp_callback() {new_temp}")
        self.controller.set_target_temp(new_temp)

    def set_output_power_indicator(self, value):
        self.output_power.setText(f"Output power: {value}")



class ValueSetter(QtGui.QWidget):
    def __init__(self, label, callback=lambda x: None):
        super(ValueSetter, self).__init__()

        self.callback = callback

        label = QtGui.QLabel(label)
        self.value_label = QtGui.QLabel("-")
        self.value_box = QtGui.QLineEdit()
        btn = QtGui.QPushButton("Set")
        btn.clicked.connect(self.value_callback)

        layout = QtGui.QHBoxLayout()
        self.setLayout(layout)

        for w in [label, self.value_label, self.value_box, btn]:
            layout.addWidget(w)

    def value_callback(self):
        try:
            self.callback(float(self.value_box.text()))
        except ValueError:
            pass

    def set_value(self, value):
        self.value_label.setText(str(value))

    def get_value(self) -> float:
        return float(self.value_box.text())


class PIDControl(QtGui.QWidget):
    def __init__(self, controller: serial_connection.Controller):
        super(PIDControl, self).__init__()

        self.controller = controller
        layout = QtGui.QVBoxLayout()

        self.p = ValueSetter("P", self.p_callback)
        self.i = ValueSetter("I", self.i_callback)
        self.d = ValueSetter("D", self.d_callback)

        for w in [self.p, self.i, self.d]:
            layout.addWidget(w)

        self.setLayout(layout)

    def p_callback(self, value):
        c = oven_proto.OvenConfiguration()
        c.pidTune.p = self.p.get_value()
        self.controller.set_oven_configuration(c)

    def i_callback(self, value):
        c = oven_proto.OvenConfiguration()
        c.pidTune.i = self.i.get_value()
        self.controller.set_oven_configuration(c)

    def d_callback(self, value):
        c = oven_proto.OvenConfiguration()
        c.pidTune.d = self.d.get_value()
        self.controller.set_oven_configuration(c)


class GraphWindow:

    def __init__(self, controller: serial_connection.Controller):
        self.win = pg.GraphicsWindow()
        self.win.setWindowTitle('RockSAT Power Supply Data Viewer')

        # 2) Allow data to accumulate. In these examples, the array doubles in length
        #    whenever it is full.
        self.p1 = self.win.addPlot(title="Oven Temps")
        self.p2 = self.win.addPlot(title="Ambient Temps")

        # Use automatic downsampling and clipping to reduce the drawing load
        self.p1.setDownsampling(mode='peak')
        self.p1.setClipToView(True)
        self.p1.setRange(xRange=[-100, 0])

        self.p2.setDownsampling(mode='peak')
        self.p2.setClipToView(True)
        self.p2.setRange(xRange=[-100, 0])

        colors = ["b", "g", "r", "c", "m", "y", "w", (0.5, 0.5, 0.5, 1.0)]  #"bgrcmywk"

        self.oven_curves = [CurvePlotter(self.p1.plot(pen=c)) for c in colors[:2]]
        self.ambient_curves = CurvePlotter(self.p2.plot(pen="b"))

        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.data_poll)
        self.timer.start(1)

        proxy = QtGui.QGraphicsProxyWidget()
        # button = QtGui.QPushButton('button')
        # button = ToggleButton("Supply 1", lambda x: print("ps1", x), description="Pressure Sensor 5V")
        self.ovenControl = OvenControl(controller)
        proxy.setWidget(self.ovenControl)


        self.p3 = self.win.addLayout(row=1, col=0)
        self.p3.addItem(proxy, row=1, col=1)


        # proxy2 = QtGui.QGraphicsProxyWidget()
        # self.pidControl = PIDControl(controller)
        # proxy2.setWidget(self.pidControl)
        #
        #
        # self.p4 = self.win.addLayout(row=1, col=1)
        # self.p4.addItem(proxy, row=1, col=1)

        self.queue = Queue()
        self.configQueue = Queue()

    def data_poll(self):
        while not self.queue.empty():
            ovenStatusBytes: bytes = self.queue.get_nowait()
            ovenStatus = OvenStatusProto()
            ovenStatus.ParseFromString(ovenStatusBytes)

            if ovenStatus.HasField("ambientTemp"):
                self.ambient_curves.add_point(ovenStatus.ambientTemp)

            if ovenStatus.HasField("ovenTemp"):
                self.oven_curves[0].add_point(ovenStatus.ovenTemp)

            if ovenStatus.HasField("targetTemp"):
                self.oven_curves[1].add_point(ovenStatus.targetTemp)
                self.ovenControl.temp_setter.set_temp(ovenStatus.targetTemp)

            if ovenStatus.HasField("ovenState"):
                self.ovenControl.oven_state.set_status(oven_proto.OvenState.Name(ovenStatus.ovenState))

            if ovenStatus.HasField("outputPower"):
                self.ovenControl.set_output_power_indicator(ovenStatus.outputPower)

        while not self.configQueue.empty():
            configBytes: bytes = self.configQueue.get_nowait()
            config = oven_proto.OvenConfiguration()
            config.ParseFromString(configBytes)
            if config.HasField("pidTune"):
                pid = self.ovenControl.pidControl
                pid.p.set_value(config.pidTune.p)
                pid.i.set_value(config.pidTune.i)
                pid.d.set_value(config.pidTune.d)

    def add_data(self, data: OvenStatusProto):
        self.queue.put(data.SerializeToString())

    def config_data(self, config: oven_proto.OvenConfiguration):
        self.configQueue.put(config.SerializeToString())

    @staticmethod
    def event_loop():
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()


#
# ## Start Qt event loop unless running in interactive mode or using pyside.
# if __name__ == '__main__':
#     import sys
#     if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#         QtGui.QApplication.instance().exec_()
#

if __name__ == '__main__':
    g = GraphWindow()
    g.event_loop()

