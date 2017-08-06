import string

class Stop:

    id = None
    name = None
    latitude = None
    longitude = None
    predictions = None

    def __init__(self, id=None, name=None, latitude=None, longitude=None, predictions=None):
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.predictions = predictions if predictions is not None else []

    def __str__(self):
        try:
            predictions = string.join([str(x) for x in self.predictions], ', ')
            return "Stop %s" % string.join((self.id, self.name, self.latitude, self.longitude, predictions), ', ')

        except TypeError as e:
            print "Stop print error: %s" % e
            return "Stop %s" % string.join((self.id, self.name, self.latitude, self.longitude), ', ')

    def addPrediction(self, prediction):
        self.predictions.append(prediction)

    def clearPredictions(self):
        self.predictions = []