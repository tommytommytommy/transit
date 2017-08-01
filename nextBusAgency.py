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

    # load all directions and stops for bus route (nRouteNumber)
    def _loadAllDirectionsForRoute(self, nRouteNumber):

        sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')

        log = open(self.sDirectory + sFilename, 'r')
        lDirections = pickle.load(log)
        log.close()

        return lDirections


    # get predictions for a particular line
    #   nRouteNumber: the line name that NextBus uses to identify the desired route
    #   nRouteDirection: the route direction to return predictions for
    #
    # output
    #   a tuple with the following format: [mData, lStops, lTripTags, lVehicleNumbers]
    #       mData: a 2D numpy array that stores current predictions
    #       each row of mData represents a bus trip and each column represents a stop
    #       lStops: a list of tuples containing stop numbers and names along the route [stopNumber, stopName]
    #       lTripTags: a list of bus trips
    #       lVehicleNumbers: a list of active buses
    def _getPredictions(self, nRouteNumber, nRouteDirection):

        routeConfiguration = self._loadAllDirectionsForRoute(nRouteNumber)
        lStops = routeConfiguration['directions'][nRouteDirection]['stops']

        # create URL string for multiple stops
        sStops = ''

        # iterate through a list the of stop numbers to create the NextBus query
        for stopID in lStops:
            sStops = sStops + '&stops=' + nRouteNumber + '|' + stopID

        # create lists to store trip IDs, vehicle numbers, and to buffer the XML data
        lTripTags = []
        lVehicleNumbers = []
        fhPredictionsB = []

        try:
            fhPredictions = urllib.urlopen(self.sUrlNextbus
                                           + self.sCommandMultiplePredictions
                                           + self.sAgency
                                           + sStops)

            for lines in fhPredictions.readlines():

                # store NextBus's XML reply in a buffer
                fhPredictionsB.append(lines)

                # extract predictions for the busses at this stop
                if re.search('^  <prediction ', lines):

                    pattern = re.split('"', lines)

                    vehicleIndex = pattern.index(self.sVehicle) + 1
                    vehicle = pattern[vehicleIndex]

                    tripTagIndex = pattern.index(self.sTripTag) + 1
                    tripTag = pattern[tripTagIndex]

                    # if the current trip tag does not exist already, add it and the associated
                    # vehicle to the tracking lists
                    try:
                        lTripTags.index(tripTag)

                    # if this trip tag already exists, do nothing
                    except ValueError:
                        lTripTags.append(tripTag)
                        lVehicleNumbers.append(vehicle)

                else:
                    continue

            fhPredictions.close()

        except IOError:
            print("Could not open " + self.sUrlNextbus + self.sCommandMultiplePredictions + self.sAgency + sStops)

        # Instantiate a matrix to store predictions data for each trip
        nTotalTripCount = len(lTripTags)

        nDataColumns = len(lStops)
        mData = numpy.ones((nTotalTripCount, nDataColumns), dtype=int) * -1

        # process stop predictions
        for lines in fhPredictionsB:

            # skip these elements
            if re.search('^<\?xml', lines):
                continue

            # extract the route number
            elif re.search('^<predictions', lines):
                pattern = re.split('"', lines)
                routeTagIndex = pattern.index(self.sRouteTag) + 1
                routeTag = pattern[routeTagIndex]

                stopTagIndex = pattern.index(self.sStopTag) + 1
                stopTag = pattern[stopTagIndex]

            # extract the direction
            elif re.search('^  <direction ', lines):
                pattern = re.split('"', lines)
                directionIndex = pattern.index(self.sDirectionTitle) + 1
                direction = pattern[directionIndex]

            # extract predictions for the busses at this stop
            elif re.search('^  <prediction ', lines):
                pattern = re.split('"', lines)
                vehicleIndex = pattern.index(self.sVehicle) + 1
                vehicle = pattern[vehicleIndex]

                arrivalInEpochTimeIndex = pattern.index(self.sEpochTime) + 1
                arrivalInEpochTime = int(float(pattern[arrivalInEpochTimeIndex]) / 1000)

                # if the current trip tag does not exist already, add it to the list
                tripTagIndex = pattern.index(self.sTripTag) + 1
                tripTag = pattern[tripTagIndex]

                nRowIndex = lTripTags.index(tripTag)
                nColumnIndex = lStops.index(stopTag)

                mData[nRowIndex, nColumnIndex] = arrivalInEpochTime

            else:
                continue

        return [mData, lStops, lTripTags, lVehicleNumbers]


    # Get route configuration data
    #
    #   inputs
    #       nRouteNumber: the line name that NextBus uses to identify the desired route
    #
    #   outputs
    #       returns a list of all directions associated with bus (nRouteNumber)
    #
    #       this function also updates the following files on a daily basis:
    #       sDirectory/route_#.txt: full XML data from NextBus
    #	    sDirectory/route_#_directionsTable.txt: a pickle list of directions for this route
    def _getRouteConfiguration(self, nRouteNumber):

        # if the data directory does not exist, create it
        if not os.path.exists(self.sDirectory):
            os.makedirs(self.sDirectory)

        sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')

        try:
            bFileExists = os.path.isfile(self.sDirectory + sFilename)
            bUpdatedToday = (datetime.date.today() == datetime.date.fromtimestamp(os.path.getmtime(self.sDirectory + sFilename)))

        except OSError:
            bFileExists = 0
            bUpdatedToday = 0

        # configuration files are only updated once a day
        # if bFileExists == False | bUpdatedToday == False:
        if True:

            # declare arrays
            lRouteConfiguration = []
            lDirections = {}
            stops = {}

            # track the number of directions for this route
            nRouteDirection = 0

            sRoute = '&r=' + str(nRouteNumber)
            try:
                urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandGetStops
                                           + self.sAgency + sRoute + self.sFlags)
                xml =  urlHandle.read()

            except urllib.error.URLError, e:
                print e.code
                urlHandle.close()
                return

            # save the XML file
            fhGeneralRoute = open(self.sDirectory + 'route_' + str(nRouteNumber) + '.txt', 'w')
            fhGeneralRoute.writelines(xml)

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
            fhDirectionsTable = open(self.sDirectory + sFilename, 'w')
            pickle.dump({'directions': lDirections, 'stops': stops}, fhDirectionsTable)

            # Close all file handles
            fhDirectionsTable.close()
            urlHandle.close()

            return {'directions': lDirections, 'stops': stops}

        else:
            return self._loadAllDirectionsForRoute(nRouteNumber)



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
        fhVehicleLocations = urllib.urlopen(self.sUrlNextbus + self.sCommandVehicleLocations + self.sAgency
                                   + self.sRoute + str(nRouteNumber)
                                   + self.sTime + str(nHistory))

        lVehicleNumber = []
        lVehicleLatitude = []
        lVehicleLongitude = []
        lTimeSinceLastUpdate = []
        lHeading = []

        for lines in fhVehicleLocations.readlines():

            if re.search('^<vehicle ', lines):

                # Vehicle number
                pattern = re.split('"', lines)
                searchIndex = pattern.index(self.sID) + 1
                nVehicleNumber = pattern[searchIndex]

                # Vehicle direction string
                # pattern = re.split('"', lines)
                # try:
                #     searchIndex = pattern.index(self.sDirTag) + 1
                # except ValueError:
                #     searchIndex = -1
                #
                # if searchIndex != -1:
                #     vehicleDirection = pattern[searchIndex]
                # else:
                #     vehicleDirection = -1

                # Vehicle latitude
                pattern = re.split('"', lines)
                searchIndex = pattern.index(self.sLatitude) + 1
                nVehicleLatitude = pattern[searchIndex]

                # Vehicle longitude
                pattern = re.split('"', lines)
                searchIndex = pattern.index(self.sLongitude) + 1
                nVehicleLongitude = pattern[searchIndex]

                # seconds since last location update for this vehicle
                pattern = re.split('"', lines)
                searchIndex = pattern.index(self.sSecsSinceReport) + 1
                nVehicleSecondsSinceLastUpdate = pattern[searchIndex]

                # heading
                pattern = re.split('"', lines)
                searchIndex = pattern.index(self.sHeading) + 1
                nHeading = pattern[searchIndex]

                # save results
                lVehicleNumber.append(nVehicleNumber)
                lVehicleLatitude.append(nVehicleLatitude)
                lVehicleLongitude.append(nVehicleLongitude)
                lTimeSinceLastUpdate.append(nVehicleSecondsSinceLastUpdate)
                lHeading.append(nHeading)

            else:
                continue

        fhVehicleLocations.close()

        return [lVehicleNumber, lVehicleLatitude, lVehicleLongitude, lTimeSinceLastUpdate, lHeading]


    # pollNextBus
    # this function polls NextBus for stop predictions for a specific route and direction
    #
    # inputs
    #    nRouteNumber: the route number to query NextBus for
    #    sDirection: the specific direction of (nRouteNumber) to query NextBus for
    #
    # outputs
    #   returns a dictionary of trips; each trip entry contains a tuple in the same format as the CSV file
    #
    #   if bPrintLogs is true, this function will also print all results to the following files:
    #    sDirectory/route_#_directionsTable.txt is a pickle list of the directions for this route
    #    sDirectory/route_#_direction_#.txt is a pickle list of stops for this specific route/direction
    #    sDirectory/route_#.txt is the NextBus XML configuration file for this route
    #    sDirectory/route_#/date/date_route_#_direction_#_trip_#.txt is a
    #       comma separated file containing prediction data for each bus in the following format:
    #       [epochTime, vehicleID, tripID, route, direction, latitude, longitude, timeSinceLastUpdate, heading,
    #        [stop1, relativePrediction1, ... stopN, relativePredictionN]]

    def pollNextBus(self, nRouteNumber):

        # Get bus (nRouteNumber)'s directions
        lRouteDirections = self._getRouteConfiguration(nRouteNumber)['directions']
        lDirectionsOnly = lRouteDirections.keys()

        # Get (nRouteNumber)'s vehicle locations
        mLocationData = self._pollNextBusLocations(nRouteNumber)

        # create a dictionary to store data for return
        dBusData = {}

        for sDirection in lDirectionsOnly:

            # query for predictions on this bus route/direction
            mData, lStops, lTripTags, lVehicleNumbers = self._getPredictions(nRouteNumber, sDirection)

            # determine how many total bus trips are stored inside mData
            nTotalTripCount = len(lTripTags)

            # obtain the current epoch time in seconds
            nEpochTime = int(time.time())

            # create directories if necessary
            sDate = datetime.datetime.fromtimestamp(nEpochTime).strftime("%Y.%m.%d")
            sDataDirectory = (self.sDirectory + 'route_' + str(nRouteNumber) + '/' + sDate + '/')

            if self.bPrintLogs and not os.path.exists(sDataDirectory):
                os.makedirs(sDataDirectory)

            # write out data to log files
            for nTripTagIndex in range(nTotalTripCount):

                sFilename = (sDate + '_route_' + str(nRouteNumber)
                             + '_direction_' + str(sDirection)
                             + '_trip_' + lTripTags[nTripTagIndex] + '.txt')

                if self.bPrintLogs:
                    log = open(sDataDirectory + sFilename, 'a')

                dBusData[sFilename] = {}

                if self.bPrintLogs:
                    log.write(str(nEpochTime) + ',')
                    log.write(str(lVehicleNumbers[nTripTagIndex]) + ',')
                    log.write(lTripTags[nTripTagIndex] + ',')
                    log.write(nRouteNumber + ',')
                    log.write(str(sDirection) + ',')

                dBusData[sFilename] = {
                    'epochTime': nEpochTime,
                    'vehicleID': lVehicleNumbers[nTripTagIndex],
                    'tripID': lTripTags[nTripTagIndex],
                    'route': nRouteNumber,
                    'direction': sDirection
                }

                # dBusData[sFilename].extend((nEpochTime,
                #                             lVehicleNumbers[nTripTagIndex],
                #                             lTripTags[nTripTagIndex],
                #                             nRouteNumber,
                #                             sDirection))

                try:
                    nLocationIndex = mLocationData[0].index(lVehicleNumbers[nTripTagIndex])
                except ValueError:
                    nLocationIndex = -1

                if nLocationIndex != -1:
                    nLatitude = mLocationData[1][nLocationIndex]
                    nLongitude = mLocationData[2][nLocationIndex]
                    nTimeSinceLastUpdate = mLocationData[3][nLocationIndex]
                    nHeading = mLocationData[4][nLocationIndex]

                else:
                    nLatitude = -1
                    nLongitude = -1
                    nTimeSinceLastUpdate = -1
                    nHeading = -1

                if self.bPrintLogs:
                    log.write(str(nLatitude) + ',' + str(nLongitude) + ','
                              + str(nTimeSinceLastUpdate) + ',' + str(nHeading) + ',')

                dBusData[sFilename]['latitude'] = nLatitude
                dBusData[sFilename]['longitude'] = nLongitude
                dBusData[sFilename]['timeSinceLastUpdate'] = nTimeSinceLastUpdate
                dBusData[sFilename]['heading'] = nHeading
                dBusData[sFilename]['predictions'] = {}

                # dBusData[sFilename].extend((nLatitude, nLongitude, nTimeSinceLastUpdate, nHeading))

                listData = mData[nTripTagIndex, :].tolist()

                # print comma separated predictions
                # terminate the last prediction with a line return
                for nDataIndex, nPrediction in enumerate(listData):

                    if self.bPrintLogs and nDataIndex == len(listData) - 1:
                        log.write(lStops[nDataIndex] + ',' + str(nPrediction) + '\n')

                    elif self.bPrintLogs:
                        log.write(lStops[nDataIndex] + ',' + str(nPrediction) + ',')

                    # dBusData[sFilename].extend((lStops[nDataIndex], nPrediction))
                    dBusData[sFilename]['predictions'][lStops[nDataIndex]] = nPrediction

                if self.bPrintLogs:
                    log.close()

        return dBusData
