import string

class Direction:

    line = None
    id = None
    title = None

    stops = None

    # store stops in the order that they are added
    path = None

    def __init__(self, line=None, id=None, title=None, stops=None, path=None):
        self.line = line
        self.id = id
        self.title = title
        self.stops = stops if stops is not None else {}
        self.path = path if path is not None else []

    def __str__(self):
        stops = string.join([str(data) for stopID, data in self.stops.iteritems()], '; ')

        return "Line %s, Direction %s\n" \
               "Title: %s\n" \
               "Stops: %s" % (self.line, self.id, self.title, string.join([str(data) for busID, data in self.stops.iteritems()], ', '))

    def addStop(self, stop):
        self.stops[stop.id] = stop
        self.path.append(stop)