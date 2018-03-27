class Modifier(object):
    def __init__(self, object_, **kwargs):
        self.object_ = object_
        self.old_attrs = {}
        self.new_attrs = kwargs

        for key, val in self.new_attrs.iteritems():
            old_value = getattr(self.object_, key, None)
            if old_value is not None:
                self.old_attrs[key] = old_value

    def __enter__(self):
        for key, val in self.new_attrs.iteritems():
            setattr(self.object_, key, val)
        return self.object_

    def __exit__(self, type, value, traceback):
        for key in self.new_attrs.iterkeys():
            old_value = self.old_attrs.get(key)
            if old_value is not None:
                setattr(self.object_, key, old_value)
            else:
                delattr(self.object_, key)
