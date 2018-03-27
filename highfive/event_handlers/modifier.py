class Modifier(object):
    '''
    Modifier object for contextual class modification. When it comes to python, there's no guarantee
    that users will always consent adults while monkey patching stuff. This can hurt later, because
    we don't know how much stuff we've patched along the way.

    For example, the API provider we have is a giant class with a lot of properties. If one handler
    changes a property in that object, then the other (downstream) handlers will be affected.
    In order to safely modify stuff, we make use of this class.

    Let's say we wanna add a comment to another repo, but we can't because the payload belongs to
    some other repo. Instead of monkey-patching the APIProvider, we use this to achieve the same:

    >>> with Modifier(api, owner='owner', repo='repo'):
    ...     api.post_comment('Booya!')

    This will change the 'owner' and 'repo' attributes within that particular context, and when we
    get out, the object is back to its old state.
    '''

    def __init__(self, object_, **kwargs):
        self.object_ = object_
        self.old_attrs = {}
        self.new_attrs = kwargs

        # Store the old values of new attribute keys
        for key, val in self.new_attrs.iteritems():
            old_value = getattr(self.object_, key, None)
            if old_value is not None:
                self.old_attrs[key] = old_value

    def __enter__(self):
        for key, val in self.new_attrs.iteritems():
            setattr(self.object_, key, val)
        return self.object_

    def __exit__(self, type, value, traceback):
        # Restore the old values
        for key in self.new_attrs.iterkeys():
            old_value = self.old_attrs.get(key)
            if old_value is not None:
                setattr(self.object_, key, old_value)
            else:
                delattr(self.object_, key)
