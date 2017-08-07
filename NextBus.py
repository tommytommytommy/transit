# Poll NextBus for real-time bus locations and predictions

import datetime
import os
import pickle
import urllib
from lxml import etree

try:
    import MySQLdb
except ImportError:
    import pymysql as MySQLdb

from TransitAgency import TransitAgency
from Bus import Bus
from Direction import Direction
from Line import Line
from Prediction import Prediction
from Stop import Stop

class NextBus (TransitAgency):

    # default local data directory
    sDirectory = None

    # HTTP interface for NextBus
    sUrlNextbus = 'http://webservices.nextbus.com/service/publicXMLFeed?'
    sAgency = '&a=mbta'
    sRoute = '&r='
    sStopId = '&stopId='
    sStop = '&stops='
    sFlags = '&terse'
    sTime = '&t='
    sCommandGetStops = 'command=routeConfig'
    sCommandPredictions = 'command=predictions'
    sCommandMultiplePredictions = 'command=predictionsForMultiStops'
    sCommandVehicleLocations = 'command=vehicleLocations'

    # initialization
    def __init__(self, sDirectory=None, sAgency=None):

        # call initializers for super classes
        TransitAgency.__init__(self)

        if sDirectory:
            self.sDirectory = sDirectory
        else:
            self.sDirectory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/')

        if sAgency:
            self.sAgency = str('&a=' + sAgency)

    # update predictions for a particular line/direction
    #
    # inputs
    #   nRouteNumber: the line name that NextBus uses to identify the desired route
    #   sRouteDirection: the route direction to return predictions for
    #
    # outputs
    #   returns an array of predictions for each direction
    def _getPredictions(self, nLine, sDirection):

        line = self.lines[nLine]
        dStops = line.getStopsFor(sDirection)

        # create URL string for multiple stops
        sStops = ''

        # iterate through a list of stop numbers to create the NextBus query
        # and clear any existing predictions
        for stopID, data in dStops.iteritems():
            sStops = sStops + '&stops=' + nLine + '|' + data.id

        output = {}

        try:
            fhPredictions = urllib.urlopen(self.sUrlNextbus
                                           + self.sCommandMultiplePredictions
                                           + self.sAgency
                                           + sStops)

            xml = fhPredictions.read()
            fhPredictions.close()

            root = etree.fromstring(xml)

            # process stop predictions
            for element in root.findall('predictions'):

                try:
                    stopTag = element.attrib['stopTag']
                    # routeTag = element.attrib['routeTag']

                    output[stopTag] = []

                    for elementA in element.findall('direction'):
                        for elementB in elementA.findall('prediction'):

                            try:
                                # direction = elementB.attrib['dirTag']
                                vehicle = elementB.attrib['vehicle']

                                arrivalInEpochTime = int(float(elementB.attrib['epochTime']) / 1000)
                                tripTag = elementB.attrib['tripTag']

                                try:
                                    prediction = Prediction(
                                        bus=line.buses[vehicle],
                                        tripID=tripTag, arrivalTime=arrivalInEpochTime
                                    )

                                    # dStops[stopTag].addPrediction(prediction)
                                    output[stopTag].append(prediction)

                                except:
                                    print "Could not add prediction for bus %s" % vehicle

                            except (KeyError, AttributeError) as e:
                                print "Could not get attribute: %s" % e
                                continue

                except KeyError:
                    continue

        except IOError:
            print("Could not open " + self.sUrlNextbus + self.sCommandMultiplePredictions + self.sAgency + sStops)

        return output

    # Get route configuration data
    #
    #   inputs
    #       nRouteNumber: the line name that NextBus uses to identify the desired route
    #
    #   outputs
    #       returns a Transit::Line object
    def _getLineConfiguration(self, nLine):

        # if the data directory does not exist, create it
        if not os.path.exists(self.sDirectory):
            os.makedirs(self.sDirectory)

        sFilename = ('route_' + str(nLine) + '_directionsTable.txt')
        sFilename = os.path.join(self.sDirectory, sFilename)

        try:
            bFileExists = os.path.isfile(sFilename)
            bUpdatedToday = (datetime.date.today() == datetime.date.fromtimestamp(os.path.getmtime(sFilename)))

        except OSError:
            bFileExists = False
            bUpdatedToday = False

        # configuration files are only updated once a day
        if bFileExists is False or bUpdatedToday is False:

            output = Line(id=nLine)

            sRoute = '&r=' + str(nLine)
            try:
                urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandGetStops
                                           + self.sAgency + sRoute + self.sFlags)
                xml = urlHandle.read()
                urlHandle.close()

            except urllib.error.URLError as e:
                print "Could not load configuration: %s" % e
                urlHandle.close()
                return

            lStops = {}

            root = etree.fromstring(xml)
            for elementA in root:
                if elementA.tag == 'route':
                    for elementB in elementA:

                        if elementB.tag == 'stop':
                            stopID = elementB.attrib['tag']

                            lStops[stopID] = Stop(
                                id=elementB.attrib['tag'],
                                name=elementB.attrib['title'],
                                latitude=elementB.attrib['lat'],
                                longitude=elementB.attrib['lon']
                            )

                        if elementB.tag == 'direction':
                            sBusDirection = elementB.attrib['tag']
                            route = Direction(line=nLine, id=sBusDirection, title=elementB.attrib['title'])

                            for elementC in elementB:
                                route.addStop(lStops[elementC.attrib['tag']])

                            output.addDirection(route)

            # Write out direction "variables" table to a file
            fhDirections = open(sFilename, 'wb')
            pickle.dump(output, fhDirections)
            fhDirections.close()

            return output

        # route information is cached, so just restore it
        else:
            fhDirections = open(sFilename, 'rb')
            output = pickle.load(fhDirections)
            fhDirections.close()
            return output


    # poll NextBus for vehicle locations
    #
    # inputs
    #   nLine: the line name that NextBus uses to identify the desired route
    #
    # outputs
    #   return an hash of Bus objects, keyed by their IDs
    def _pollNextBusLocations(self, nLine):

        # Set epochTime to zero so that NextBus gives the last 15 minutes worth of updates
        # (the 15 minute window is a NextBus default parameter when nHistory = 0...)
        nHistory = 0

        # Get vehicle locations
        try:
            urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandVehicleLocations + self.sAgency
                                   + self.sRoute + str(nLine)
                                   + self.sTime + str(nHistory))

            xml = urlHandle.read()
            urlHandle.close()

        except urllib.error.URLError, e:
            print e.code
            urlHandle.close()
            return

        output = {}

        root = etree.fromstring(xml)
        for element in root.findall('vehicle'):

            try:
                output[element.attrib['id']] = Bus(
                    id=element.attrib['id'],
                    line=element.attrib['routeTag'],
                    direction=element.attrib['dirTag'],
                    latitude=element.attrib['lat'],
                    longitude=element.attrib['lon'],
                    secondsSinceLastUpdate=element.attrib['secsSinceReport'],
                    heading=element.attrib['heading']
                )

            except KeyError as e:
                continue

        return output

    # pollNextBus
    # this function polls NextBus for stop predictions for a specific route and direction
    #
    # inputs
    #    nLine: the bus line number to query NextBus for
    def poll(self, nLine):

        # get bus (nLine)'s directions
        self.lines[nLine] = self._getLineConfiguration(nLine)

        # get (nLine)'s vehicle locations
        self.lines[nLine].buses = self._pollNextBusLocations(nLine)

        # update predictions
        for sDirection in self.lines[nLine].getAvailableDirections():

            # clear any existing predictions
            for stop in self.lines[nLine].directions[sDirection].stops.itervalues():
                stop.clearPredictions()

            predictions = self._getPredictions(nLine, sDirection)
            for stopID, data in predictions.iteritems():
                self.lines[nLine].directions[sDirection].stops[stopID] = data