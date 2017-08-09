# Introduction
This Python module polls NextBus (http://www.nextbus.com) for real-time bus
arrival predictions. The NextBus XML manual is located at 
http://www.nextbus.com/xmlFeedDocs/NextBusXMLFeed.pdf.

This Python contains basic classes to house transit agency data such as Line, Direction, Bus, and Stop. Transit data is organized in the following data structure:

<pre>
TransitAgency
    Line
        Direction A
        Direction B
            Stop 1
            Stop 2
            Stop 3
                Prediction 1
                Prediction 2
</pre>
                
# Testing/Usage
`test.py` contains a simple test file that shows how to instantiate the NextBus module and then poll for real time predictions.
