import os

from NextBus import NextBus

### MAIN FUNCTION	

# data directory
sDirectory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data/')

# MBTA information
sAgency = "mbta"
vRouteNumber = ['1', '83']

# instantiate a NextBus object
MBTA = NextBus(sDirectory, sAgency)

# iteratively poll for route predictions
for nRouteNumber in vRouteNumber:
    print MBTA.poll(nRouteNumber)

exit()