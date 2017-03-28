from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import QTimer, QSize
import pyqtgraph as pg
import sys, random
import numpy
import serial
import threading

samplesToStore = 256
staticCalAddition = 2

class VBar(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


class HBar(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


class RingBuffer:
    def __init__(self, size):
        self.data = [0 for i in range(size)]

    def append(self, x):
        self.data.pop(0)
        self.data.append(x)

    def get(self):
        return self.data


# TODO: Popups for error
class MyApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.serialLock = threading.Lock()

        self.current = 0

        self.highVoltage = True
        self.highCurrent = False

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

        self.setWindowTitle("IV-grapher")

        self.createButtons()

        # 3 main window plots
        self.voltagePlot = pg.PlotWidget(title="Voltage drop")
        self.voltagePlot.setYRange(0, 21)
        self.voltagePlot.setLabel("left", text="Drop", units="V")

        self.currentPlot = pg.PlotWidget(title="Current")
        self.currentPlot.setYRange(0, 40000)
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

        self.resistanceLabel = QtWidgets.QLabel()
        self.resistanceLabel.setText("∞ Ω")
        label_layout.addRow(QtWidgets.QLabel("Equiv. resistance: "), self.resistanceLabel)

        self.avgVoltageLabel = QtWidgets.QLabel()
        self.avgVoltageLabel.setText("0V")
        label_layout.addRow(QtWidgets.QLabel("Average voltage: "), self.avgVoltageLabel)

        # Controls for high/low voltage and current
        scaling_control_layout = QtWidgets.QFormLayout()
        self.highVoltageInput = QtWidgets.QCheckBox("High voltage mode")
        self.highVoltageInput.setChecked(self.highVoltage)
        self.highVoltageInput.stateChanged.connect(self.highVoltageChange)
        self.highCurrentInput = QtWidgets.QCheckBox("High current mode")
        self.highCurrentInput.setChecked(self.highCurrent)
        self.highCurrentInput.stateChanged.connect(self.highCurrentChange)
        scaling_control_layout.addRow(self.highVoltageInput)
        scaling_control_layout.addRow(self.highCurrentInput)

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
        left_column_layout.addLayout(scaling_control_layout)
        left_column_layout.addWidget(HBar())
        left_column_layout.addLayout(serial_control_layout)

        # Sweep settings
        sweep_layout = QtWidgets.QFormLayout()

        self.btnSweepStart = QtWidgets.QPushButton("Sweep start")
        self.btnSweepStart.clicked.connect(self.startSweep)

        self.btnSweepStop = QtWidgets.QPushButton("Sweep stop")
        self.btnSweepStop.clicked.connect(self.stopSweep)
        self.btnSweepStop.setEnabled(False)

        self.sweepProgressBar = QtWidgets.QProgressBar()

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
        sweep_layout.addRow(self.sweepProgressBar)

        bottomRightLayout = QtWidgets.QHBoxLayout()
        bottomRightLayout.addLayout(left_column_layout)
        bottomRightLayout.addWidget(VBar())
        bottomRightLayout.addLayout(self.btnLayout)
        bottomRightLayout.addWidget(VBar())
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

    def highVoltageChange(self):
        if self.serial.is_open:
            if self.serialLock.acquire():
                self.highVoltage = self.highVoltageInput.isChecked()
                if (self.highVoltage):
                    self.serial.write('V'.encode('ascii'))
                else:
                    self.serial.write('v'.encode('ascii'))
                self.serialLock.release()
        else:
            showError("Serial port not open.","Please open serial port first.")
            self.highVoltageInput.setChecked(self.highVoltage)

    def highCurrentChange(self):
        if self.serial.is_open:
            if self.serialLock.acquire():
                self.highCurrent = self.highCurrentInput.isChecked()
                if (self.highCurrent):
                    self.serial.write('C'.encode('ascii'))
                else:
                    self.serial.write('c'.encode('ascii'))
                self.serialLock.release()
        else:
            showError("Serial port not open.", "Please open serial port first.")
            self.highCurrentInput.setChecked(self.highCurrent)

    def serialButtonClick(self):
        if (self.serial.is_open):
            self.stopSerial()
        else:
            self.startSerial()
        return

    def startSerial(self):
        if self.serialLock.acquire():
            self.serialPort=self.serialPortInput.text()
            self.serialSpeed=int(self.serialSpeedInput.text())
            try:
                self.serial = serial.Serial(self.serialPort, self.serialSpeed, timeout=5)
            except serial.SerialException as exc:
                showError("Opening serial port failed", "Tried to open " + self.serialPort + " and failed.", str(exc))
                return
            self.btnSerialToggle.setText("Close serial")
            self.serial.readline()
            self.serial.readline()
            self.serial.timeout = 0.05
            self.timer.start(100)
            self.serialLock.release()

    def stopSerial(self):
        if self.serialLock.acquire():
            self.timer.stop()
            self.serial.close()
            self.serialLock.release()
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
            linesplit = line.split(';')

            highVoltage = int(linesplit[3])
            highCurrent = int(linesplit[4])
            currentSet = (int(linesplit[0])+staticCalAddition)*(1+(99*highCurrent))/10
            voltageDrop = (int(linesplit[1])+staticCalAddition)*(1+(9*highVoltage))/1000
            currentRead = (int(linesplit[2])+staticCalAddition)*(1+(99*highCurrent))/10

            self.currentSetSamples.append(currentSet)
            self.dropSamples.append(voltageDrop)
            self.currentSamples.append(currentRead)
            self.currentErrorSamples.append(currentRead - currentSet)

            self.setCurrentLabel.setText(str(currentSet) + "μA")
            self.voltageLabel.setText(str(voltageDrop) + "V")
            self.currentLabel.setText(str(currentRead) + "μA")
            if (currentRead != 0):
                self.resistanceLabel.setText("{0:.2f}".format(voltageDrop/(currentRead/1_000_000)) + "Ω")
            else:
                self.resistanceLabel.setText("∞ Ω")
            self.avgVoltageLabel.setText("{0:.4f}".format(numpy.nanmean(self.dropSamples.get())) + "V")

            if (self.sweepEnabled):
                self.sweepValuesVolts.append(voltageDrop)
                self.sweepValuesCurrent.append(currentRead)
                self.sweepValues.append((voltageDrop, currentRead))
        return

    def writeDAC(self, data):
        # TODO: Data sanity on input
        serdata = ("S" + str(data) + '\n').encode('ascii')
        if self.serial.is_open:
            if self.serialLock.acquire(timeout=3):
                self.serial.write(serdata)
                self.serialLock.release()
            else:
                showError("Serial port locked.", "Could not acquire serial port lock within 3 seconds.")
        else:
            showError("Serial port not open.", "Please open serial port first.")
        return

    def randomDAC(self):
        self.writeDAC(random.randint(100, 2000))
        return

    def nudge(self, amount=1):
        # TODO: Limit to sensible ranges
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
            self.sweepProgressBar.setValue(self.current)
        return

    def startSweep(self):
        self.sweepValuesVolts = []
        self.sweepValuesCurrent = []
        self.sweepValues = []

        self.sweepStart = int(10 * float(self.sweepStartInput.text()))
        self.sweepEnd = int(10 * float(self.sweepEndInput.text()))
        self.sweepStep = int(10 * float(self.sweepStepInput.text()))
        self.sweepInterval = int(self.sweepTimeInput.text())
        # TODO: Check the data makes sense before starting

        self.current = self.sweepStart
        self.writeDAC(self.current)
        self.sweepEnabled = True
        self.btnSweepStart.setEnabled(False)
        self.btnSweepStop.setEnabled(True)
        self.sweepProgressBar.setMinimum(self.sweepStart)
        self.sweepProgressBar.setMaximum(self.sweepEnd)
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


def showError(errorheading, errortext, details=""):
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    msg.setWindowTitle(errorheading)
    msg.setText(errorheading)
    msg.setText(errortext)
    msg.setDetailedText(details)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)

    return msg.exec_()


app = QtWidgets.QApplication([])

w = MyApp()

w.show()

sys.exit(app.exec_())
