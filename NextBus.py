import datetime
import os
import pickle
import time
import urllib
from lxml import etree

try:
    import MySQLdb
except ImportError:
    import pymysql as MySQLdb

from TransitAgency import TransitAgency

class NextBus (TransitAgency):

    # default local data directory
    sDirectory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/')

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

        if sDirectory:
            self.sDirectory = sDirectory

        if sAgency:
            self.sAgency = str('&a=' + sAgency)

    # get predictions for a particular line
    #   nRouteNumber: the line name that NextBus uses to identify the desired route
    #   sRouteDirection: the route direction to return predictions for
    #
    # output
    #   returns a dictionary with predictions for each active trip/stop
    def _getPredictions(self, nRouteNumber, sRouteDirection):

        routeConfiguration = self._getRouteConfiguration(nRouteNumber)
        lStops = routeConfiguration['directions'][sRouteDirection]['stops']

        # create URL string for multiple stops
        sStops = ''

        # iterate through a list the of stop numbers to create the NextBus query
        for stopID in lStops:
            sStops = sStops + '&stops=' + nRouteNumber + '|' + stopID

        try:
            fhPredictions = urllib.urlopen(self.sUrlNextbus
                                           + self.sCommandMultiplePredictions
                                           + self.sAgency
                                           + sStops)

            xml = fhPredictions.read()
            fhPredictions.close()

            root = etree.fromstring(xml)

            # Instantiate a matrix to store predictions data for each trip
            output = {}

            # process stop predictions
            for element in root.findall('predictions'):

                try:
                    stopTag = element.attrib['stopTag']
                    routeTag = element.attrib['routeTag']

                    for elementA in element.findall('direction'):
                        for elementB in elementA.findall('prediction'):

                            try:
                                direction = elementB.attrib['dirTag']
                                vehicle = elementB.attrib['vehicle']

                                arrivalInEpochTime = int(float(elementB.attrib['epochTime']) / 1000)
                                tripTag = elementB.attrib['tripTag']

                                try:
                                    output[tripTag]['predictions'][stopTag] = arrivalInEpochTime

                                except:
                                    output[tripTag] = {
                                        'route': routeTag,
                                        'direction': direction,
                                        'vehicle': vehicle,
                                        'predictions': {stopTag: arrivalInEpochTime}
                                    }

                            except (KeyError, AttributeError) as e:
                                continue

                except KeyError as e:
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
    #       returns a list of all directions and stops associated with bus (nRouteNumber)
    def _getRouteConfiguration(self, nRouteNumber):

        # if the data directory does not exist, create it
        if not os.path.exists(self.sDirectory):
            os.makedirs(self.sDirectory)

        sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')
        sFilename = os.path.join(self.sDirectory, sFilename)

        try:
            bFileExists = os.path.isfile(sFilename)
            bUpdatedToday = (datetime.date.today() == datetime.date.fromtimestamp(os.path.getmtime(sFilename)))

        except OSError:
            bFileExists = False
            bUpdatedToday = False

        # configuration files are only updated once a day
        if bFileExists is False or bUpdatedToday is False:

            # declare arrays
            lDirections = {}
            stops = {}

            sRoute = '&r=' + str(nRouteNumber)
            try:
                urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandGetStops
                                           + self.sAgency + sRoute + self.sFlags)
                xml = urlHandle.read()
                urlHandle.close()

            except urllib.error.URLError, e:
                print e.code
                urlHandle.close()
                return

            root = etree.fromstring(xml)

            for elementA in root:
                if elementA.tag == 'route':
                    for elementB in elementA:

                        if elementB.tag == 'stop':
                            stopID = elementB.attrib['tag']
                            stops[stopID] = {}
                            for (key, value) in elementB.attrib.items():
                                stops[stopID][key] = value

                        if elementB.tag == 'direction':
                            sBusDirection = elementB.attrib['tag']
                            lDirections[sBusDirection] = {'stops': []}
                            for (key, value) in elementB.attrib.items():
                                lDirections[sBusDirection][key] = value

                            for elementC in elementB:
                                lDirections[sBusDirection]['stops'].append(elementC.attrib['tag'])

            # Write out direction "variables" table to a file
            sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')
            sFilename = os.path.join(self.sDirectory, sFilename)
            fhDirectionsTable = open(sFilename, 'w')
            pickle.dump({'directions': lDirections, 'stops': stops}, fhDirectionsTable)
            fhDirectionsTable.close()

            return {'directions': lDirections, 'stops': stops}

        # route information is cached, so just restore it
        else:
            log = open(sFilename, 'r')
            lDirections = pickle.load(log)
            log.close()
            return lDirections


    # poll NextBus for vehicle locations
    #
    # inputs
    #   nRouteNumber: the line name that NextBus uses to identify the desired route
    #
    # outputs
    #   returns a dictionary of current locations for active buses
    def _pollNextBusLocations(self, nRouteNumber):

        # Set epochTime to zero so that NextBus gives the last 15 minutes worth of updates
        # (the 15 minute window is a NextBus default parameter when nHistory = 0...)
        nHistory = 0

        # Get vehicle locations
        try:
            urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandVehicleLocations + self.sAgency
                                   + self.sRoute + str(nRouteNumber)
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
                output[element.attrib['id']] = {
                    'route': element.attrib['routeTag'],
                    'direction': element.attrib['dirTag'],
                    'latitude': element.attrib['lat'],
                    'longitude': element.attrib['lon'],
                    'secondsSinceLastUpdate': element.attrib['secsSinceReport'],
                    'heading': element.attrib['heading']
                }

            except KeyError as e:
                continue

        return output

    # pollNextBus
    # this function polls NextBus for stop predictions for a specific route and direction
    #
    # inputs
    #    nRouteNumber: the route number to query NextBus for
    #
    # outputs
    #   returns a dictionary of trips and prediction times with the following format:
    #   {
    #       bus_unique_string: {
    #           epochTime
    #           vehicleID
    #           tripID
    #           route
    #           direction
    #           latitude (current)
    #           longitude (current)
    #           secondsSinceLastUpdate
    #           heading
    #           predictions (a dictionary of stops and prediction times in seconds)
    #       }
    #   }
    def poll(self, nRouteNumber):

        # Get bus (nRouteNumber)'s directions
        lRouteDirections = self._getRouteConfiguration(nRouteNumber)['directions']

        # Get (nRouteNumber)'s vehicle locations
        mLocationData = self._pollNextBusLocations(nRouteNumber)

        # create a dictionary to store data for return
        output = {}

        for sDirection in lRouteDirections.keys():

            # query for predictions on this bus route/direction
            mData = self._getPredictions(nRouteNumber, sDirection)

            # obtain the current epoch time in seconds
            nEpochTime = int(time.time())

            for tripTag, data in mData.iteritems():

                sFilename = ('route_' + str(nRouteNumber)
                             + '_direction_' + str(sDirection)
                             + '_trip_' + tripTag)

                vehicleID = data['vehicle']

                output[sFilename] = {
                    'epochTime': nEpochTime,
                    'vehicleID': vehicleID,
                    'tripID': tripTag,
                    'route': nRouteNumber,
                    'direction': data['direction']
                }

                try:
                    nLatitude = mLocationData[vehicleID]['latitude']
                    nLongitude = mLocationData[vehicleID]['longitude']
                    nTimeSinceLastUpdate = mLocationData[vehicleID]['secondsSinceLastUpdate']
                    nHeading = mLocationData[vehicleID]['heading']

                except KeyError:
                    nLatitude = -1
                    nLongitude = -1
                    nTimeSinceLastUpdate = -1
                    nHeading = -1

                output[sFilename]['latitude'] = nLatitude
                output[sFilename]['longitude'] = nLongitude
                output[sFilename]['timeSinceLastUpdate'] = nTimeSinceLastUpdate
                output[sFilename]['heading'] = nHeading
                output[sFilename]['predictions'] = mData[tripTag]['predictions']

        return output