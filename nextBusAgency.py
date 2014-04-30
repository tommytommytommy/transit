import datetime
import numpy
import os
import pickle
import re
import time
import urllib

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
    sBeginStopTag = '  <stop tag='
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

    # load all directions for bus route (nRouteNumber)
    #   inputs
    #   outputs
    def _loadAllDirectionsForRoute(self, nRouteNumber):

        sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')

        log = open(self.sDirectory + sFilename, 'r')
        lDirections = pickle.load(log)
        log.close()

        return lDirections


    # load bus stops for the current route and direction
    #
    #   inputs
    #       nRouteNumber: the line name that NextBus uses to identify the desired route
    #       nRouteDirection: the bus route's direction
    #
    #   outputs
    #       a list of all stops along bus line (nRouteNumber) headed in direction (nRouteDirection)
    def _loadStops(self, nRouteNumber, nRouteDirection):

        sFilename = ('route_' + str(nRouteNumber) +
                     '_direction_' + str(nRouteDirection) + '.txt')
        log = open(self.sDirectory + sFilename, 'r')
        lStops = pickle.load(log)
        log.close()

        # return all stops, but start from the second element because the first element (at index 0) is the
        # name of this direction
        return lStops[1:]


    # get predictions for a particular line
    #   routeNumber: the line name that NextBus uses to identify the desired route
    #   stops: the stop IDs to look up predictions for
    #
    # output
    #   a tuple with the following format: [mData, lStops, lTripTags, lVehicleNumbers]
    #       mData: a 2D numpy array that stores current predictions
    #       each row of mData represents a bus trip and each column represents a stop
    #       lStops: a list of tuples containing stop numbers and names along the route [stopNumber, stopName]
    #       lTripTags: a list of bus trips
    #       lVehicleNumbers: a list of active buses
    def _getPredictions(self, nRouteNumber, nRouteDirection):

        lStops = self._loadStops(nRouteNumber, nRouteDirection)
        lStopNumbers = [i[0] for i in lStops]

        # create URL string for multiple stops
        sStops = ''

        # iterate through a list the of stop numbers to create the NextBus query
        for stopID in lStopNumbers:
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

        nDataColumns = len(lStopNumbers)
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
                nColumnIndex = lStopNumbers.index(stopTag)

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
    #	    sDirectory/route_#_direction_#.txt: a pickle list of stops for each direction of this route (1 file/direction)
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
        if (bFileExists == False | bUpdatedToday == False):

            # declare arrays
            lRouteConfiguration = []
            lDirections = []

            # track the number of directions for this route
            nRouteDirection = 0

            sRoute = '&r=' + str(nRouteNumber)
            try:
                urlHandle = urllib.urlopen(self.sUrlNextbus + self.sCommandGetStops
                                           + self.sAgency + sRoute + self.sFlags)
            except urllib.error.URLError, e:
                print e.code
                urlHandle.close()
                return

            # construct array of stops
            fhGeneralRoute = open(self.sDirectory + 'route_' + str(nRouteNumber) + '.txt', 'w')
            lStopNames = {}

            for lines in urlHandle.readlines():

                # Write all lines to a general log file
                fhGeneralRoute.writelines(lines)
                pattern = re.split('"', lines)

                # Create a dictionary of stops and stop names
                if re.search('<stop tag="', lines) and re.search('\s*title="', lines):
                    searchIndex = pattern.index('<stop tag=') + 1
                    sStopNumber = pattern[searchIndex]

                    searchIndex = pattern.index(' title=') + 1
                    sStopName = pattern[searchIndex]
                    lStopNames[sStopNumber] = sStopName

                if re.search('^<direction', lines):

                    # Create a direction-specific file to hold the stops for this route/direction
                    sFilename = ('route_' + str(nRouteNumber) +
                                 '_direction_' + str(nRouteDirection) + '.txt')
                    fhSpecificDirection = open(self.sDirectory + sFilename, 'w')

                    # Save the direction "variable" for a look-up table
                    searchIndex = pattern.index(self.sDirectionTag) + 1
                    sDirection = pattern[searchIndex]

                    # Save the human-readable direction title
                    searchIndex = pattern.index(self.sTitle) + 1
                    sDirectionTitle = pattern[searchIndex]
                    lRouteConfiguration = [sDirectionTitle]

                    lDirections.append([sDirection, sDirectionTitle])

                elif re.search('^</direction', lines):

                    # Complete writing for this direction
                    pickle.dump(lRouteConfiguration, fhSpecificDirection)
                    fhSpecificDirection.close()
                    lRouteConfiguration = []
                    nRouteDirection += 1

                elif re.search('^  <stop', lines):
                    searchIndex = pattern.index(self.sBeginStopTag) + 1
                    sStop = pattern[searchIndex]
                    lRouteConfiguration.append([sStop, lStopNames[sStop]])

                else:
                    continue

            # Write out direction "variables" table to a file
            sFilename = ('route_' + str(nRouteNumber) + '_directionsTable.txt')
            fhDirectionsTable = open(self.sDirectory + sFilename, 'w')
            pickle.dump(lDirections, fhDirectionsTable)

            # Close all file handles
            fhDirectionsTable.close()
            fhGeneralRoute.close()
            urlHandle.close()

        else:
            lDirections = self._loadAllDirectionsForRoute(nRouteNumber)

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
    #   returns a dictionary of route directions for nRouteNumber
    #   each dictionary entry contains the following tuple:
    #   [nEpochTime, mData, lStops, lTripTags, lVehicleNumbers, nEpochTime]
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
        lRouteDirections = self._getRouteConfiguration(nRouteNumber)
        lDirectionsOnly = [i[0] for i in lRouteDirections]
        lDirectionTitlesOnly = [i[1] for i in lRouteDirections]

        # Get (nRouteNumber)'s vehicle locations
        mLocationData = self._pollNextBusLocations(nRouteNumber)

        # create a dictionary to store data for return
        dBusData = {}

        for sDirection in lDirectionsOnly:

            # translate direction name to an index variable
            nRouteDirection = lDirectionsOnly.index(sDirection)

            # query for predictions on this bus route/direction
            mData, lStops, lTripTags, lVehicleNumbers = self._getPredictions(nRouteNumber, nRouteDirection)
            lStopNumbers = [i[0] for i in lStops]

            # determine how many total bus trips are stored inside mData
            nTotalTripCount = len(lTripTags)

            # obtain the current epoch time in seconds
            nEpochTime = int(time.time())

            # store results to the dictionary
            dBusData[lDirectionTitlesOnly[nRouteDirection]] = [nEpochTime, mData, lStops, lTripTags, lVehicleNumbers]

            if self.bPrintLogs:

                # create directories if necessary
                sDate = datetime.datetime.fromtimestamp(nEpochTime).strftime("%Y.%m.%d")
                sDataDirectory = (self.sDirectory + 'route_' + str(nRouteNumber) + '/' + sDate + '/')

                if not os.path.exists(sDataDirectory):
                    os.makedirs(sDataDirectory)


                # write out data to log files
                for nTripTagIndex in range(nTotalTripCount):

                    sFilename = (sDate + '_route_' + str(nRouteNumber)
                                 + '_direction_' + str(nRouteDirection)
                                 + '_trip_' + lTripTags[nTripTagIndex] + '.txt')

                    log = open(sDataDirectory + sFilename, 'a')

                    log.write(str(nEpochTime) + ',')
                    log.write(str(lVehicleNumbers[nTripTagIndex]) + ',')
                    log.write(lTripTags[nTripTagIndex] + ',')
                    log.write(nRouteNumber + ',')
                    log.write(str(nRouteDirection) + ',')

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

                    log.write(str(nLatitude) + ',' + str(nLongitude) + ','
                              + str(nTimeSinceLastUpdate) + ',' + str(nHeading) + ',')

                    listData = mData[nTripTagIndex, :].tolist()

                    # print comma separated predictions
                    # terminate the last prediction with a line return
                    for nDataIndex, nPrediction in enumerate(listData):
                        if nDataIndex == len(listData) - 1:
                            log.write(lStopNumbers[nDataIndex] + ',' + str(nPrediction) + '\n')
                        else:
                            log.write(lStopNumbers[nDataIndex] + ',' + str(nPrediction) + ',')

                    log.close()

        return dBusData
