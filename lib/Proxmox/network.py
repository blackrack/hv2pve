class ProxmoxNetworkCart:
    def __init__(self, typeNetCard, bridge, macaddr):
        self.typeNetCard = typeNetCard
        self.bridge = bridge
        self.macaddr = macaddr
        self.vlandid = 0

    def setVlan(self, id):
        self.vlandid = id

    def __str__(self):
        output = f"{self.typeNetCard},bridge={self.bridge},macaddr={self.macaddr}"
        if self.vlandid:
            output += f",tag={self.vlandid}"
        return output
