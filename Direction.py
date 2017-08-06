import string

class Direction:

    line = None
    id = None
    stops = None
    title = None

    def __init__(self, line=None, id=None, title=None, stops=None):
        self.line = line
        self.id = id
        self.title = title
        self.stops = stops if stops is not None else {}

    def __str__(self):
        stops = string.join([str(data) for stopID, data in self.stops.iteritems()], '; ')

        return "Line %s, Direction %s\n" \
               "Title: %s\n" \
               "Stops: %s" % (self.line, self.id, self.title, string.join([str(data) for busID, data in self.stops.iteritems()], ', '))

    def addStop(self, stop):
        self.stops[stop.id] = stop