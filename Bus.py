import math
import string

class Bus ():

    id = None
    line = None
    direction = None
    latitude = None
    longitude = None
    secondsSinceLastUpdate = None
    heading = None

    def __init__(self, id=None, line=None, direction=None, latitude=None, longitude=None,
                 secondsSinceLastUpdate=None, heading=None):
        self.id = id
        self.line = line
        self.direction = direction
        self.latitude = latitude
        self.longitude = longitude
        self.secondsSinceLastUpdate = secondsSinceLastUpdate
        self.heading = heading

    def __dict__(self):
        # calculate vector
        headingLat = math.cos(self.heading) * 0.001
        headingLon = math.sin(self.heading) * 0.001

        return {
            'vehicleID': self.id,
            'lat': self.latitude,
            'lon': self.longitude,
            'heading': self.heading,
            'headingLat': headingLat,
            'headingLon': headingLon,
            'direction': self.direction,
            'secondsSinceLastUpdate': self.secondsSinceLastUpdate
        }

    def __str__(self):
        return "Bus %s" % string.join((self.id, self.line, self.direction, self.latitude, self.longitude), ', ')