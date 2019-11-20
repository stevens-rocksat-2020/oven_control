import time

from graphing import GraphWindow
from serial_connection import Controller
from oven.oven_pb2 import OvenStatus as OvenStatusProto
import threading


# def update_data():
#     i = 0
#     j = 0
#     while True:
#         time.sleep(1/30)
#         g.add_data((i, j))
#         i += 1
#         j += 2
#         if i > 1000:
#             i = 0
#         if j > 1000:
#             j = 0

class Main:
    def __init__(self):
        self.controller = Controller(self.add_data_helper)
        self.graph_window = GraphWindow(self.controller)
        self.controller.config_callback = self.graph_window.config_data

        self.serial_thread = threading.Thread(target=self.controller.read_loop)
        self.serial_thread.start()

    def event_loop(self):
        self.graph_window.event_loop()

    def add_data_helper(self, data: OvenStatusProto):
        self.graph_window.add_data(data)



if __name__ == '__main__':
    m = Main()
    m.event_loop()
