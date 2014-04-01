import nextBusAgency

### MAIN FUNCTION	

# data directory
sDirectory = "./"

# MBTA information
sAgency = "mbta"
vRouteNumber = ['1', '83']

# boolean for printing logs
bPrintLogs = True

# instantiate a NextBus object
nextBus = nextBusAgency.nextBusAgency(sDirectory, sAgency, bPrintLogs)

# iteratively poll for route predictions
for nRouteNumber in vRouteNumber:

    # this will log NextBus data to sDirectory specified above
    nextBus.pollNextBus(nRouteNumber)

exit()