import string

class Line:

    # the name of the line; for example, '1'
    id = None

    # a dictionary of Direction objects describing directions for this line
    directions = None

    # a dictionary of active buses on this line
    buses = None

    def __init__(self, id=None, directions=None, buses=None):
        self.id = id
        self.directions = directions if directions is not None else {}
        self.buses = buses if buses is not None else {}

    def __str__(self):
        output = "Line: %s\n" \
                 "Directions: %s\n" % (self.id, string.join(self.directions.keys(), ', '))

        for direction, data in self.directions.iteritems():
            output += "%s\n" % data

        return output

    def addDirection(self, direction):
        self.directions[direction.id] = direction

    def getAvailableDirections(self):
        return self.directions.keys()

    def getStopsFor(self, sDirection):
        if sDirection not in self.directions:
            return KeyError
        else:
            return self.directions[sDirection].stops