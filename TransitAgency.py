# An abstract class for transit agencies with real-time location and prediction information

import abc

class TransitAgency:

    name = None
    lines = None

    def __init__(self, name):
        self.name = name
        self.lines = {}

    @abc.abstractmethod
    def poll(self, nLine):
        pass

    def getActiveBuses(self):
        output = []

        for lineID, line in self.lines.iteritems():
            for busID, bus in line.buses.iteritems():
                output.append(bus)

        return output