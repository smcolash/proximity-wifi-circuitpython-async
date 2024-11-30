from output import Output

class Beacon (object):
    items = {}

    @classmethod
    def factory (cls, id, details):
        return Beacon (id, details['name'], details['output'], details['enabled'])

    def __init__ (self, macid, name, output, enabled):
        super ().__init__ ()

        if macid in self.items:
            raise Exception ('duplicate beacon')

        Beacon.items[macid] = self

        self.macid = macid
        self.name = name
        self.output = {}
        self.enabled = enabled

        for name in output:
            self.output[name] = Output.items[name]

