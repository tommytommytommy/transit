import nextBusAgency

### MAIN FUNCTION	

# data directory
sDirectory = "/Users/tommy/nextBus/"

# MBTA information
sAgency = "mbta"
vRouteNumber = ['1', '83']

# boolean for printing logs
bPrintLogs = True

# instantiate a NextBus object
nextBus = nextBusAgency.nextBusAgency(sDirectory, sAgency, bPrintLogs)

# iteratively poll for route predictions
for nRouteNumber in vRouteNumber:

    nextBus.pollNextBus(nRouteNumber)

exit()