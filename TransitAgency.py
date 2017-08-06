import abc

class TransitAgency:

    @abc.abstractmethod
    def poll(self, nRouteNumber):
        pass