from oven import oven_pb2 as comm
import serial
from serial.tools import list_ports
from cobs import cobs
from typing import Callable
import binascii

class Controller:

    def __init__(self, data_callback):
        self.data_callback: Callable[[comm.OvenStatus], None] = data_callback
        self.config_callback = lambda x: None
        self.connection = SerialConnection()
        self.connection.connect()

    def output(self, rx: comm.RxMicro):
        print(rx)
        self.connection.send_packet(rx)

    def set_oven_status(self, state: comm.OvenState):
        message = comm.RxMicro()
        message.ovenState = state
        self.output(message)

    def set_oven_configuration(self, config: comm.OvenConfiguration):
        message = comm.RxMicro()
        message.ovenConfiguration.CopyFrom(config)
        self.output(message)

    def set_target_temp(self, temp: float):
        message = comm.RxMicro()
        message.target.targetTemp = temp
        self.output(message)

    def input(self, tx: comm.TxMicro):
        if tx.HasField("ovenStatus"):
            self.data_callback(tx.ovenStatus)

        if tx.HasField("ovenConfiguration"):
            self.config_callback(tx.ovenConfiguration)
            # print("Oven configuration returned:\n", tx.ovenConfiguration)

    def read_loop(self):
        while True:
            self.input(self.connection.read_packet())


def get_serial_port():
    try:
        return list(filter(lambda x: x.serial_number == "F1A3B8CA51504C3750202020FF09250C",
                       list_ports.comports()))[0].device
    except IndexError:
        raise Exception("Port not found")


class SerialConnection:

    def __init__(self, serial_port=get_serial_port(), baud=115200):
        self.ser: serial.Serial = None
        self.serial_port = serial_port
        self.baud = baud

    def connect(self):
        self.ser = serial.Serial(self.serial_port, self.baud)

    def close(self):
        self.ser.close()

    def read_packet(self) -> comm.TxMicro:
        byte = self.ser.read()
        result = b''
        while byte != b'\x00':
            result += byte
            byte = self.ser.read()
        tx = comm.TxMicro()
        try:
            tx.ParseFromString(cobs.decode(result))
        except Exception:
            print(f"Could not decode message: {binascii.hexlify(result)})")

        return tx

    def send_packet(self, rx: comm.RxMicro):
        return self.ser.write(cobs.encode(rx.SerializeToString()) + b'\x00')


def serial_test():
    sc = SerialConnection()
    sc.connect()
    while True:
        print(sc.read_packet())


def controller_test():
    def callback_test(*kwargs):
        print(kwargs)

    c = Controller(callback_test)
    c.read_loop()


if __name__ == '__main__':
    controller_test()
