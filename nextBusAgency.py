import datetime
import numpy
import os
import pickle
import re
import time
import urllib
from lxml import etree

try:
    import MySQLdb
except ImportError:
    import pymysql as MySQLdb

class nextBusAgency:

    # local data storage parameters
    sDirectory = '~/'

    # boolean to indicate whether or not to save poll results
    bPrintLogs = False

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

    # NextBus strings
    sID = '<vehicle id='
    sRouteTag = ' routeTag='
    sStopTag = ' stopTag='
    sDirTag = ' dirTag='
    sVehicle = ' vehicle='
    sLatitude = ' lat='
    sLongitude = ' lon='
    sHeading = ' heading='
    sSecsSinceReport = ' secsSinceReport='
    sSecondsToNextArrival = ' seconds='
    sLastTime = '<lastTime time='
    sDirectionTitle = '  <direction title='
    sTitle = ' title='
    sDirectionTag = '<direction tag='
    sBeginStopTag = '<stop tag='
    sEpochTime = '  <prediction epochTime='
    sTripTag = ' tripTag='

    # initialization
    def __init__(self, sDirectory=None, sAgency=None, bPrintLogs=None):

        if sDirectory:
            self.sDirectory = sDirectory

        if sAgency:
            self.sAgency = str('&a=' + sAgency)

        if bPrintLogs:
            self.bPrintLogs = bPrintLogs

    # get predictions for a particular line
    #   nRouteNumber: the line name that NextBus uses to identify the desired route
    #   sRouteDirection: the route direction to return predictions for
    #
    # output
    #   a tuple with the following format: [mData, lStops, lTripTags, lVehicleNumbers]
    #       mData: a 2D numpy array that stores current predictions
    #       each row of mData represents a bus trip and each column represents a stop
    #       lStops: a list of tuples containing stop numbers and names along the route [stopNumber, stopName]
    #       lTripTags: a list of bus trips
    #       lVehicleNumbers: a list of active buses
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
    #       returns a list of all directions associated with bus (nRouteNumber)
    #
    #       this function also updates the following file on a daily basis:
    #	    sDirectory/route_#_directionsTable.txt: a pickle list of directions for this route
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
            bFileExists = 0
            bUpdatedToday = 0

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

        # route information was already cached, so just restore it
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
    #   returns a list of tuples with the following format:
    #       [lVehicleNumber, lVehicleLatitude, lVehicleLongitude, lTimeSinceLastUpdate, lHeading]
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
    #   returns a dictionary of trips, predictions time, and other prediction information
    def pollNextBus(self, nRouteNumber):

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

            # write out data to log files
            for tripTag, data in mData.iteritems():

                sFilename = ('_route_' + str(nRouteNumber)
                             + '_direction_' + str(sDirection)
                             + '_trip_' + tripTag + '.txt')

                output[sFilename] = {
                    'epochTime': nEpochTime,
                    'vehicleID': data['vehicle'],
                    'tripID': tripTag,
                    'route': nRouteNumber,
                    'direction': data['direction']
                }

                try:
                    vehicleID = data['vehicle']
                    nLatitude = mLocationData[vehicleID]['latitude']
                    nLongitude = mLocationData[vehicleID]['longitude']
                    nTimeSinceLastUpdate = mLocationData[vehicleID]['secondsSinceLastUpdate']
                    nHeading = mLocationData[vehicleID]['heading']

                except KeyError as e:
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
