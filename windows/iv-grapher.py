from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import QTimer, QSize
import pyqtgraph as pg
import sys, random
import numpy
import serial

samplesToStore = 256


class RingBuffer:
    def __init__(self, size):
        self.data = [0 for i in range(size)]

    def append(self, x):
        self.data.pop(0)
        self.data.append(x)

    def get(self):
        return self.data


class MyApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.current = 0

        self.serialPort = "COM5"
        self.serialSpeed = 38400
        self.serial = serial.Serial()

        # Default values for sweeping
        self.sweepStart = 0
        self.sweepEnd = 1000
        self.sweepStep = 1
        self.sweepEnabled = False
        self.sweepInterval = 200
        self.sweepValuesVolts = []
        self.sweepValuesCurrent = []
        self.sweepValues = []

        self.createButtons()

        # 3 main window plots
        self.voltagePlot = pg.PlotWidget(title="Voltage drop")
        self.voltagePlot.setYRange(0, 4)
        self.voltagePlot.setLabel("left", text="Drop", units="V")

        self.currentPlot = pg.PlotWidget(title="Current")
        self.currentPlot.setYRange(0, 450)
        self.currentPlot.setLabel("left", text="Current (μA)")

        self.currentErrorPlot = pg.PlotWidget(title="Current error")
        self.currentErrorPlot.setYRange(-2, 2)
        self.currentErrorPlot.setLabel("left", text="Current (μA)")

        # Default grid layout
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.voltagePlot, 0, 0)
        self.layout.addWidget(self.currentPlot, 0, 1)
        self.layout.addWidget(self.currentErrorPlot, 1, 0)

        # Left column in the control panel
        left_column_layout = QtWidgets.QVBoxLayout()

        # Text fields for displaying data
        label_layout = QtWidgets.QFormLayout()
        left_column_layout.addLayout(label_layout)

        self.setCurrentLabel = QtWidgets.QLabel()
        self.setCurrentLabel.setText("0μA")

        label_layout.addRow(QtWidgets.QLabel("Set current: "), self.setCurrentLabel)

        self.currentLabel = QtWidgets.QLabel()
        self.currentLabel.setText("0μA")
        label_layout.addRow(QtWidgets.QLabel("Read current: "), self.currentLabel)

        self.voltageLabel = QtWidgets.QLabel()
        self.voltageLabel.setText("0V")
        label_layout.addRow(QtWidgets.QLabel("Voltage: "), self.voltageLabel)

        self.avgVoltageLabel = QtWidgets.QLabel()
        self.avgVoltageLabel.setText("0V")
        label_layout.addRow(QtWidgets.QLabel("Avg. voltage: "), self.avgVoltageLabel)

        # Control buttons for serial
        serial_control_layout = QtWidgets.QFormLayout()
        self.serialPortInput = QtWidgets.QLineEdit(self.serialPort)
        self.serialPortInput.setAlignment(QtCore.Qt.AlignRight)
        self.serialSpeedInput = QtWidgets.QLineEdit(str(self.serialSpeed))
        self.serialSpeedInput.setValidator(QtGui.QIntValidator())
        self.serialSpeedInput.setAlignment(QtCore.Qt.AlignRight)
        serial_control_layout.addRow(QtWidgets.QLabel("Serial port"), self.serialPortInput)
        serial_control_layout.addRow(QtWidgets.QLabel("Speed"), self.serialSpeedInput)

        self.btnSerialToggle = QtWidgets.QPushButton("Open serial")
        self.btnSerialToggle.clicked.connect(self.serialButtonClick)
        serial_control_layout.addRow(self.btnSerialToggle)

        left_column_layout.addStretch()
        left_column_layout.addLayout(serial_control_layout)

        # Sweep settings
        sweep_layout = QtWidgets.QFormLayout()

        self.btnSweepStart = QtWidgets.QPushButton("Sweep start")
        self.btnSweepStart.clicked.connect(self.startSweep)

        self.btnSweepStop = QtWidgets.QPushButton("Sweep stop")
        self.btnSweepStop.clicked.connect(self.stopSweep)
        self.btnSweepStop.setEnabled(False)

        start_sweep_row = QtWidgets.QHBoxLayout()
        self.sweepStartInput = QtWidgets.QLineEdit(str(self.sweepStart / 10))
        self.sweepStartInput.setMaximumSize(QSize(50, 16777215))
        self.sweepStartInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepStartInput.setValidator(QtGui.QDoubleValidator(0.0, 24999.9, 1))
        start_sweep_row.addWidget(self.sweepStartInput)
        start_sweep_row.addWidget(QtWidgets.QLabel("μA"))
        sweep_layout.addRow(QtWidgets.QLabel("Sweep start: "), start_sweep_row)

        end_sweep_row = QtWidgets.QHBoxLayout()
        self.sweepEndInput = QtWidgets.QLineEdit(str(self.sweepEnd / 10))
        self.sweepEndInput.setMaximumSize(QSize(50, 16777215))
        self.sweepEndInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepEndInput.setValidator(QtGui.QDoubleValidator(0.1, 25000.0, 1))
        end_sweep_row.addWidget(self.sweepEndInput)
        end_sweep_row.addWidget(QtWidgets.QLabel("μA"))
        sweep_layout.addRow(QtWidgets.QLabel("Sweep end: "), end_sweep_row)

        step_sweep_row = QtWidgets.QHBoxLayout()
        self.sweepStepInput = QtWidgets.QLineEdit(str(self.sweepStep / 10))
        self.sweepStepInput.setMaximumSize(QSize(50, 16777215))
        self.sweepStepInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepStepInput.setValidator(QtGui.QDoubleValidator(0.1, 1000.0, 1))
        step_sweep_row.addWidget(self.sweepStepInput)
        step_sweep_row.addWidget(QtWidgets.QLabel("μA"))
        sweep_layout.addRow(QtWidgets.QLabel("Step size:"), step_sweep_row)

        time_sweep_row = QtWidgets.QHBoxLayout()
        self.sweepTimeInput = QtWidgets.QLineEdit(str(self.sweepInterval))
        self.sweepTimeInput.setMaximumSize(QSize(50, 16777215))
        self.sweepTimeInput.setAlignment(QtCore.Qt.AlignRight)
        self.sweepTimeInput.setValidator(QtGui.QIntValidator())
        time_sweep_row.addWidget(self.sweepTimeInput)
        time_sweep_row.addWidget(QtWidgets.QLabel("ms"))
        sweep_layout.addRow(QtWidgets.QLabel("Time steps:"), time_sweep_row)

        sweep_layout.addRow(self.btnSweepStart)
        sweep_layout.addRow(self.btnSweepStop)

        bottomRightLayout = QtWidgets.QHBoxLayout()
        bottomRightLayout.addLayout(left_column_layout)
        bottomRightLayout.addLayout(self.btnLayout)
        bottomRightLayout.addLayout(sweep_layout)

        self.layout.addLayout(bottomRightLayout, 1, 1)

        # Set up buffers for data storage
        self.x = numpy.arange(samplesToStore)
        self.dropSamples = RingBuffer(samplesToStore)
        self.currentSamples = RingBuffer(samplesToStore)
        self.currentSetSamples = RingBuffer(samplesToStore)
        self.currentErrorSamples = RingBuffer(samplesToStore)

        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update)

        self.sweepTimer = QTimer()
        self.sweepTimer.setInterval(self.sweepInterval)
        self.sweepTimer.timeout.connect(self.sweep)

        # self.timer2 = QTimer()
        # self.timer2.setInterval(5000)
        # self.timer2.timeout.connect(self.randomDAC)
        # self.timer2.start(5000)

    def serialButtonClick(self):
        if (self.serial.is_open):
            self.stopSerial()
        else:
            self.startSerial()
        return

    def startSerial(self):
        self.serialPort=self.serialPortInput.text()
        self.serialSpeed=int(self.serialSpeedInput.text())
        try:
            self.serial = serial.Serial(self.serialPort, self.serialSpeed, timeout=5)
        except serial.SerialException as exc:
            print("Opening serial port failed: " + str(exc))
            return
        self.btnSerialToggle.setText("Close serial")
        self.serial.readline()
        self.serial.readline()
        self.serial.timeout = 0.05
        self.timer.start(100)

    def stopSerial(self):
        self.timer.stop()
        self.serial.close()
        self.btnSerialToggle.setText("Open serial")

    def createButtons(self):
        self.btnIncrease = QtWidgets.QPushButton('+0.1 μA')
        self.btnIncrease10 = QtWidgets.QPushButton('+1 μA')
        self.btnIncrease100 = QtWidgets.QPushButton('+10 μA')
        self.btnDecrease = QtWidgets.QPushButton('-0.1 μA')
        self.btnDecrease10 = QtWidgets.QPushButton('-1 μA')
        self.btnDecrease100 = QtWidgets.QPushButton('-10 μA')
        self.btnIncrease.clicked.connect(lambda: self.nudge(1))
        self.btnIncrease10.clicked.connect(lambda: self.nudge(10))
        self.btnIncrease100.clicked.connect(lambda: self.nudge(100))
        self.btnDecrease.clicked.connect(lambda: self.nudge(-1))
        self.btnDecrease10.clicked.connect(lambda: self.nudge(-10))
        self.btnDecrease100.clicked.connect(lambda: self.nudge(-100))
        self.btnLayout = QtWidgets.QFormLayout()
        self.btnLayout.addWidget(self.btnIncrease100)
        self.btnLayout.addWidget(self.btnIncrease10)
        self.btnLayout.addWidget(self.btnIncrease)
        self.btnLayout.addWidget(self.btnDecrease)
        self.btnLayout.addWidget(self.btnDecrease10)
        self.btnLayout.addWidget(self.btnDecrease100)
        self.btnLayout.addWidget(QtWidgets.QSplitter())

    def update(self):
        self.readADC()
        self.voltagePlot.plot(self.x, self.dropSamples.get(), clear=1, pen=3)
        self.currentPlot.plot(self.x, self.currentSamples.get(), clear=1, pen=2)
        self.currentErrorPlot.plot(self.x, self.currentErrorSamples.get(), clear=1, pen=1)

    def readADC(self):
        while (self.serial.in_waiting > 5):
            line = self.serial.readline()
            line = line.decode('ascii')

            self.currentSetSamples.append(int(line.split(';')[0]) / 10)
            self.dropSamples.append(int(line.split(';')[1]) / 1000)
            self.currentSamples.append(int(line.split(';')[2]) / 10)
            self.currentErrorSamples.append((int(line.split(';')[2]) - int(line.split(';')[0])) / 10)

            self.setCurrentLabel.setText(str(int(line.split(';')[0]) / 10) + "μA")
            self.voltageLabel.setText(str(int(line.split(';')[1]) / 1000) + "V")
            self.currentLabel.setText(str(int(line.split(';')[2]) / 10) + "μA")
            self.avgVoltageLabel.setText("{0:.4f}".format(numpy.nanmean(self.dropSamples.get())) + "V")

            if (self.sweepEnabled):
                self.sweepValuesVolts.append(int(line.split(';')[1]) / 1000)
                self.sweepValuesCurrent.append(int(line.split(';')[2]) / 10)
                self.sweepValues.append((int(line.split(';')[1]) / 1000, int(line.split(';')[2]) / 10))
        return

    def writeDAC(self, data):
        serdata = ("S" + str(data) + '\n').encode('ascii')
        self.serial.write(serdata)
        return

    def randomDAC(self):
        self.writeDAC(random.randint(100, 2000))
        return

    def nudge(self, amount=1):
        self.current += amount
        self.writeDAC(self.current)
        return

    def sweep(self):
        if (self.sweepEnabled):
            self.current += self.sweepStep
            if (self.current > self.sweepEnd):
                self.stopSweep()
                self.current = self.sweepEnd
            self.writeDAC(self.current)
        return

    def startSweep(self):
        self.sweepValuesVolts = []
        self.sweepValuesCurrent = []
        self.sweepValues = []

        self.sweepStart = int(10 * float(self.sweepStartInput.text()))
        self.sweepEnd = int(10 * float(self.sweepEndInput.text()))
        self.sweepStep = int(10 * float(self.sweepStepInput.text()))
        self.sweepInterval = int(self.sweepTimeInput.text())

        self.current = self.sweepStart
        self.writeDAC(self.current)
        self.sweepEnabled = True
        self.btnSweepStart.setEnabled(False)
        self.btnSweepStop.setEnabled(True)
        self.sweepTimer.start(self.sweepInterval)
        return

    def stopSweep(self):

        self.sweepEnabled = False
        self.sweepTimer.stop()
        a = numpy.array(self.sweepValues, [('volts', float), ('current', float)])
        a.sort(order=['volts', 'current'])
        pg.plot(a['volts'], a['current'], clear=1, pen=1)
        self.btnSweepStop.setEnabled(False)
        self.btnSweepStart.setEnabled(True)
        return


app = QtWidgets.QApplication([])

w = MyApp()

w.show()

sys.exit(app.exec_())
