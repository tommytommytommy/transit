# An abstract class for transit agencies with real-time location and prediction information

import abc

class TransitAgency:

    lines = None

    def __init__(self):
        self.lines = {}

    @abc.abstractmethod
    def poll(self, nLine):
        pass