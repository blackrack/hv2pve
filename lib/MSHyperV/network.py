from typing import List, Dict, Any


class Network:
    def __init__(self, network: Dict[str, Any], index: int):
        self.mac_address: str = network.get("MacAddress", "")
        self.switch_id: str = network.get("SwitchId", "")
        self.vlan_id: int = network.get("VLANID", 0)
        self.index: int = index

        self.MacAddress = self.mac_address
        self.SwitchId = self.switch_id
        self.index: int = index
        self.vlanid = self.vlan_id

    def __repr__(self):
        return f"Network(index={self.index}, mac_address='{self.mac_address}', " f"switch_id='{self.switch_id}', vlan_id={self.vlan_id})"


class Networks:

    def __init__(self):
        self.index: int = 0
        self.networks: List[Network] = []

    def add(self, network: Network):
        self.networks.append(network)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index < len(self.networks):
            network: Network = self.networks[self.index]
            self.index += 1
            return network
        else:
            raise StopIteration
