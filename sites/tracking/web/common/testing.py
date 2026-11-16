"""Test helpers."""

import fnmatch


class FakeRedis:
    """The few Redis commands the publisher uses, in memory. A pipeline runs its commands on execute()."""

    def __init__(self):
        self.data = {}
        self.published = []

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = str(value)

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)

    def publish(self, channel, message):
        self.published.append((channel, str(message)))

    def scan_iter(self, pattern):
        return [key for key in list(self.data) if fnmatch.fnmatchcase(key, pattern)]

    def pipeline(self, transaction=True):
        return _Pipeline(self)


class _Pipeline:
    def __init__(self, client):
        self.client, self.calls = client, []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, args))

    def execute(self):
        for name, args in self.calls:
            getattr(self.client, name)(*args)
        self.calls = []
