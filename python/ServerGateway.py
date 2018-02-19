# encoding: utf-8
#from sys import version as python_version
import logging
from .config import config
from .miscutils import mergeoptions
from .ServerBase import MyHTTPRequestHandler, exposed
from .DOI import DOI
from .IPLD import IPLDdir, IPLDfile
from .Errors import ToBeImplementedException, NoContentException, TransportFileNotFound
#!SEE-OTHERNAMESPACE add new namespaces here and see other #!SEE-OTHERNAMESPACE
from .HashResolvers import ContentHash, Sha1Hex
from .LocalResolver import LocalResolverStore, LocalResolverFetch, LocalResolverList, LocalResolverAdd
from .Archive import AdvancedSearch, ArchiveItem
from .Btih import BtihResolver
from .LocalResolver import KeyValueTable

"""
For documentation on this project see https://docs.google.com/document/d/1FO6Tdjz7A1yi4ABcd8vDz4vofRDUOrKapi3sESavIcc/edit# 
"""


class DwebGatewayHTTPRequestHandler(MyHTTPRequestHandler):

    """
    Routes queries to handlers based on the first part of the URL for the output format,
    that routine will create an object by calling the constructor for the Namespace, and
    then do whatever is needed to generate the output format (typically calling a method on the created
    object, or invoking a constructor for that format.)

    GET '/outputformat/namespace/namespace_dependent_string?aaa=bbb,ccc=ddd'`

    Services exposed as "outputformat":
    /info           Returns data structure describing gateway
    /content        Return the content as interpreted for the namespace.
    /contenthash    Return the hash of the content

    outputformat:  Format wanted e.g. [IPLD](#IPLD) or [nameresolution](#nameresolution)
    namespace: is a extensible descripter for name spaces e.g. "doi"
    namespace-dependent-string: is a string, that may contain additional "/" dependent on the namespace.
    aaa=bbb,ccc=ddd are optional arguments to the name space resolver.
    _headers contains a dictioanry of HTTP headers, especially "range"

    Pseudo Code for each service
    * lookup namespace in a config table to get a class
    * Call constuctor on that class
    * obj = ConfigTable[namespace](namespace, namespace_dependent_string, aaa=bbb, ccc=ddd)
    * And convert to wanted output format by either
    * call a method on the class,  DOI(namespace, *args, **kwargs).contenthash()
    * or a constructor on another class passing the first e.g.  IPLD(DOI(namespace, *args, **kwargs)).content()
    * Encapsulate result as a dict to return via Server superclass
    *   { Content-type: result.contenttype, data: result.content() }

    Notes:
    *The namespace is passed to the specific constuctor since a single name resolver might implement multiple namespaces.

    Future Work:
    #TODO-STREAM Expand the ServerBase classes to support streams as a return from these routines
    """



    defaulthttpoptions = { "ipandport": ('localhost', 4244) }
    onlyexposed = True          # Only allow calls to @exposed methods
    expectedExceptions = (NoContentException,)     # List any exceptions that you "expect" (and dont want stacktraces for)

    namespaceclasses = {    # Map namespace names to classes each of which has a constructor that can be passed the URL arguments.
        #!SEE-OTHERNAMESPACE add new namespaces here and see other !SEE-OTHERNAMESPACE here and in clients
        "advancedsearch": AdvancedSearch,
        "archiveid": ArchiveItem,
        "doi": DOI,
        "contenthash": ContentHash,
        "sha1hex": Sha1Hex,
        "rawstore": LocalResolverStore,
        "rawfetch": LocalResolverFetch,
        "rawlist": LocalResolverList,
        "rawadd": LocalResolverAdd,
        "btih": BtihResolver,
        "table": KeyValueTable,
    }

    _voidreturn = {'Content-type': 'application/octet-stream', 'data': None }

    @classmethod
    def DwebGatewayHTTPServeForever(cls, httpoptions=None, verbose=False):
        """
        One instance of this will be created for each request, so don't override __init__()
        Initiate with something like: DwebGatewayHTTPRequestHandler.serve_forever()


        :return: Never Returns
        """
        httpoptions = mergeoptions(cls.defaulthttpoptions, httpoptions or {}) # Deepcopy to merge options
        logging.info("Starting server with options={0}".format(httpoptions))
        #any code needed once (not per thread) goes here.
        cls.serve_forever(ipandport=httpoptions["ipandport"], verbose=verbose)    # Uses defaultipandport

    @exposed    # Exposes this function for outside use
    def sandbox(self, foo, bar, **kwargs):
        # Changeable, just for testing HTTP etc, feel free to play with in your branch, and expect it to be overwritten on master branch.
        logging.debug("foo={} bar={}, kwargs={}".format(foo, bar,  kwargs))
        return { 'Content-type': 'application/json',
                 'data': { "FOO": foo, "BAR": bar, "kwargs": kwargs}
               }

    @exposed
    def info(self, **kwargs):   # http://.../info
        """
        Return info about this server
        The content of this may change, make sure to retain the "type" field.

        ConsumedBy:
            "type" consumed by status function TransportHTTP (in Dweb client library)
        Consumes:
        """
        return { 'Content-type': 'application/json',
                 'data': { "type": "gateway",
                           "services": [ ]}     # A list of names of services supported below  (not currently consumed anywhere)
               }

    # Create one of these for each output format, by default parse name and create object, then either
    # call a method on it, or create an output class.
    # Can throw Exception if "new" fails e.g. because file doesnt exist
    @exposed
    def content(self, namespace, *args, **kwargs):
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).content(verbose=verbose, _headers=self.headers)   # { Content-Type: xxx; data: "bytes" }

    @exposed
    def download(self, namespace, *args, **kwargs):
        # Synonym for "content" to match Archive API
        return self.content(namespace, *args, **kwargs)

    # Create one of these for each output format, by default parse name and create object, then either
    # call a method on it, or create an output class.
    @exposed
    def metadata(self, namespace, *args, **kwargs):
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).metadata(headers=True, verbose=verbose)   # { Content-Type: xxx; data: "bytes" }

    @exposed
    def contenthash(self, namespace, *args, **kwargs):
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).contenthash(verbose=verbose)

    @exposed
    def contenturl(self, namespace, *args, **kwargs):
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).contenturl(verbose=verbose)

    @exposed
    def void(self, namespace, *args, **kwargs):
        self.namespaceclasses[namespace].new(namespace, *args, **kwargs)
        return self._voidreturn

    ##### A group for handling webtorrent ########
    @exposed
    def torrent(self, namespace, *args, **kwargs):
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, transport="WEBTORRENT", wanttorrent=True, **kwargs).torrent(verbose=verbose, headers=True)

    @exposed
    def magnetlink(self, namespace, *args, **kwargs):
        # Get a magnetlink - only currently supported by btih - could (easily) be supported on ArchiveFile, ArchiveItem
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).magnetlink(verbose=verbose, headers=True)

    @exposed
    def thumbnail(self, namespace, *args, **kwargs):
        # Get a thumbnail image - required because https://archive.org/service/img/<itemid> has CORS issues
        verbose = kwargs.get("verbose")
        return self.namespaceclasses[namespace].new(namespace, *args, **kwargs).thumbnail(verbose=verbose, headers=True)

    ###### A group for handling Key Value Stores #########
    @exposed
    def set(self, namespace, *args, verbose=False, **kwargs):
        verbose = kwargs.get("verbose")
        self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).set(verbose=verbose, **kwargs)
        return self._voidreturn

    @exposed
    def get(self, namespace, *args, verbose=False, **kwargs):
        verbose = kwargs.get("verbose") # Also passed on to get in kwargs
        return self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).get(headers=True, verbose=verbose, **kwargs)

    @exposed
    def delete(self, namespace, *args, verbose=False, **kwargs):
        verbose = kwargs.get("verbose") # Also passed on to get in kwargs
        self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).delete(headers=True, verbose=verbose, **kwargs)
        return self._voidreturn

    @exposed
    def keys(self, namespace, *args, verbose=False, **kwargs):
        verbose = kwargs.get("verbose") # Also passed on to get in kwargs
        return self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).keys(headers=True, verbose=verbose, **kwargs)

    @exposed
    def getall(self, namespace, *args, verbose=False, **kwargs):
        verbose = kwargs.get("verbose") # Also passed on to get in kwargs
        return self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).getall(headers=True, verbose=verbose, **kwargs)

    #### A group for handling naming #####

    @exposed
    def name(self, namespace, *args, verbose=False, key=None, **kwargs):
        """
        This needs to catch the special case of /name/archiveid?key=xyz
        """
        verbose = kwargs.get("verbose")
        args = list(args)
        if key: args.append(key)              # Push key into place normally held by itemid in URL of archiveid/xyz
        return self.namespaceclasses[namespace].new(namespace, *args, verbose=verbose, **kwargs).name(headers=True, verbose=verbose, **kwargs)

    #### A group that breaks the naming convention####
    # urls of form https://gateway.dweb.me/archive.org/details/foo, conceptually to be moved to dweb.archive.org/details/foo
    @exposed
    def archive_org(self, *args, **kwargs):
        filename = config["directories"]["bootloader"]
        try:
            #if verbose: logging.debug("Opening {0}".format(filename))
            with open(filename, 'rb') as file:
                content = file.read()
            #if verbose: logging.debug("Opened")
        except IOError as e:
            raise TransportFileNotFound(file=filename)
        return  {'Content-type': 'text/html', 'data': content }

    #### A group for IPLD assuming we were sharding on server for IPFS - we arent since we use the local IPFS server so this is not complete #####
    @exposed
    def iplddir(self, namespace, *args, **kwargs):
        #TODO-IPLD This is not complete yet
        obj = self.namespaceclasses[namespace](namespace, *args, **kwargs)
        i = IPLDdir(obj)
        return i.content()

    def storeipld(self, namespace, *args, **kwargs):
        """
        Post a IPLD and store for a multihash
        XXXX THIS IS NOT USED, PROBABLY NEVER COMPLETED

        :param namespace:   Where to store this - must be "contenthash" currently
        :param args:
        :param kwargs:
        :return:
        """
        if namespace != "contenthash":
            raise ToBeImplementedException(name="POST_storeipld for namespace="+namespace)
        data = kwargs["data"]
        del kwargs["data"]
        obj = self.namespaceclasses[namespace](namespace, *args, **kwargs)  # Construct our local object
        IPLDfile.storeFromString(obj.multihash, data)   # Store IPLD and hash of IPLD
        return {} # Empty return, just success

    def storeipldhash(self, namespace, *args, **kwargs):
        """
        Post a IPLD and store for a multihash
        XXXX THIS IS NOT USED, PROBABLY NEVER COMPLETED

        :param namespace:   Where to store this - must be "contenthash" currently
        :param args:
        :param kwargs:
        :return:
        """
        if namespace != "contenthash":
            raise ToBeImplementedException(name="POST_storeipld for namespace="+namespace)
        data = kwargs["data"]   # multihash of IPLD that IPFS gateway has created
        del kwargs["data"]
        obj = self.namespaceclasses[namespace](namespace, *args, **kwargs)  # Construct our local object
        IPLDfile.storeFromHash(obj.multihash, data)   # Store IPLD and hash of IPLD
        return {} # Empty return, just success

if __name__ == "__main__":
    logging.basicConfig(filename='dweb_gateway.log', level=logging.DEBUG)
    DwebGatewayHTTPRequestHandler.DwebGatewayHTTPServeForever({'ipandport': ('localhost',4244)}, verbose=True) # Run local gateway

