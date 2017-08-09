import string

class Prediction:

    bus = None
    tripID = None
    arrivalTime = None

    def __init__(self, bus=None, tripID=None, arrivalTime=None):
        self.bus = bus
        self.tripID = tripID
        self.arrivalTime = arrivalTime

    def __str__(self):
        return "(bus %s, trip %s, arrival %s)" % (self.bus.id, self.tripID, self.arrivalTime)