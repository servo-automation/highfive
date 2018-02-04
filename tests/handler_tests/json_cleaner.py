# Separator used for pretty printing dirty file paths.
NODE_SEP = ' -> '


class NodeMarker(object):
    '''
    This wrapper object marks a node when it gets indexed i.e., when `__getitem__`
    is called on a node.

    Since this wraps itself over *all* nodes in a dict, the methods of the actual values in the
    nodes would be inaccessible. So, if we wanna make use of some method, then we implement
    it in this object.
    '''

    def __init__(self, node, root=None):
        self._root = root
        self._node = node        # actual value
        self._is_used = False    # marker

    def mark(self):
        self._is_used = True
        root = self._root
        # Mark all the way up to root (if it's not been done already).
        while root and not root._is_used:
            root._is_used = True
            root = root._root

    def get_object(self, obj):
        return obj._node if hasattr(obj, 'mark') else obj

    # The following methods blindly assume that the method is supported by the
    # underlying type (i.e., exceptions should be handled explicitly)

    def get(self, key, default=None):
        return self[key] if self._node.get(key) else default

    def lower(self):
        return str(self).lower()

    def encode(self, encoding):
        return self._node.encode(encoding)

    def split(self, *args):
        return str(self).split(*args)

    # If you access the element in the usual way, then "bam!" - it will be marked as used!
    def __getitem__(self, key):
        self._node[key].mark()
        return self._node[key]

    def __setitem__(self, key, val):
        self._node[key] = visit_nodes(val)

    def __hash__(self):
        return self._node.__hash__()

    def __iter__(self):
        return iter(self._node)

    def __nonzero__(self):          # It's `__bool__` in Python 3
        return bool(self._node)

    def __eq__(self, other):
        return self._node == self.get_object(other)

    def __ne__(self, other):
        return self._node != self.get_object(other)

    def __add__(self, other):
        return self._node + self.get_object(other)

    def __mod__(self, other):
        return self._node % self.get_object(other)

    def __contains__(self, other):
        # Since string is also a sequence in python, we shouldn't iterate
        # over it and index with the individual characters
        if isinstance(self._node, str) or isinstance(self._node, unicode):
            return other in self._node

        for idx, thing in enumerate(self._node):
            if thing == self._node:
                if isinstance(self._node, list):
                    self._node[idx].mark()
                else:
                    self._node[thing].mark()
                return True
        return False

    def __str__(self):
        return str(self._node)

    def __int__(self):
        return int(self._node)


class JsonCleaner(object):
    '''
    Object to keep track of used nodes in JSON. This wraps around the actual JSON object, and this
    should be passed around instead of the JSON object itself. Once this object has been utilized,
    call `clean` to remove the unused nodes from the JSON.
    '''

    def __init__(self, json_obj):
        self.unused = 0
        self.json = self._visit_nodes(json_obj)
        self._assign_roots(self.json)


    def _visit_nodes(self, node):
        '''This recursively visits each node in a tree and converts them to a `NodeMarker` object'''

        if hasattr(node, 'mark'):
            return node     # it's already a NodeMarker
        if hasattr(node, '__iter__'):
            iterator = xrange(len(node)) if isinstance(node, list) else node
            for thing in iterator:
                node[thing] = self._visit_nodes(node[thing])
        return NodeMarker(node)


    def _assign_roots(self, marker_node, root=None):
        '''
        We need the roots of each node, so that we can trace our way back to the root
        from a specific node (marking nodes along the way). Since `_visit_nodes` makes
        a pre-order traversal, it assigns `NodeMarker` to each node from inside-out,
        which makes it difficult to assign roots. So, we do another traversal to store
        the references of the root nodes.
        '''

        node = marker_node._node
        if hasattr(node, '__iter__'):
            iterator = xrange(len(node)) if isinstance(node, list) else node
            for thing in iterator:
                self._assign_roots(node[thing], marker_node)
        marker_node._root = root


    def clean(self, warn=True):
        '''
        Recursively traverses the tree and removes the unused nodes. This should be the only
        function to be called publicly. If `warn` flag is enabled, then this prints the unused
        nodes as they're removed.
        '''

        return self._filter_nodes(self.json, warn)

    def _filter_nodes(self, marker_node, warn, path=''):
        if marker_node._is_used:
            node = marker_node._node
            if hasattr(node, '__iter__'):
                # it's either 'list' or 'dict' when it comes to JSONs
                removed = 0
                iterator = xrange(len(node)) if isinstance(node, list) \
                    else node.keys()

                for thing in iterator:
                    new_path = path + str(thing) + NODE_SEP
                    # since lists maintain order, once we pop them,
                    # we decrement their indices as their length is reduced
                    if isinstance(node, list):
                        thing -= removed
                    node[thing] = self._filter_nodes(node[thing], warn, new_path)

                    if node[thing] == ():
                        self.unused += 1
                        if warn:
                            new_path = new_path.strip(NODE_SEP)
                            print 'unused node at "%s"' % new_path
                        node.pop(thing)
                        removed += 1
            return node
        return ()
