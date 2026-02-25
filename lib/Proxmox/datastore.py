class ProxmoxDatastores:
    def __init__(self):
        pass


class ProxmoxDatastore:
    def __init__(self, config):
        self.used = config["used"]
        self.type = config["type"]
        self.avail = config["avail"]
        self.total = config["total"]
        self.active = config["active"]
        self.shared = config["shared"]
        self.content = config["content"]
        self.storage = config["storage"]
        self.avail_test = config["avail"]
        self.used_fraction = config["used_fraction"]

    def __str__(self):
        return f"<ProxmoxDatastore storage={self.storage};type={self.type} >"
