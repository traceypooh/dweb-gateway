from .NameResolver import NameResolverDir, NameResolverFile
import sqlite3
from .miscutils import httpget
from .HashStore import LocationService, MimetypeService
import requests
import multihash
import base58


class DOI(NameResolverDir):
    """
    DOI is a class for Document Object Identifiers, an academic namespace
    typically of form   10.1234/abc123
    URL: `/xxx/doi/10.pub_id/pub_specific_id` (forwarded here by ServerGateway methods)

    Implements name resolution of the DOI namespace, via a sqlite database (provided by Brian Reynolds)

    Case insensitive, have some significant punctuation, but sometimes presented with insignificant punctuation

    Future Work
    * Build way to preload the hashstore with the hashes and URLs from the sqlite
    """
    # SQLITE="../data/idents_files_urls_sqlite"   # Old version in Python2 when working dir was "python"
    SQLITE="data/idents_files_urls_sqlite"

    def __init__(self, namespace, publisher, *identifier, **kwargs):
        """
        Creates the object

        :param namespace:
        :param publisher:   Publisher ID allocated by DOI.org, always of form 10.nnnn
        :param identifier:  Id for an academic article or resource, allocated by the publisher. Case insensitive, Alphanumeric plus a few (undefined) punctuation.
                            Its an array, because may be multiple fields seperated by /, can safely re-concatenate
        :param kwargs:      Any other args to the URL, ignored for now.
        """
        #Note if you dont have your own way of using sqlite I suggest SqliteWrap from https://github.com/mitra42/sqlite_models
        """
        Pseudo-code
        * Canonicalize pub_specific_id (lowercase, strip chars)
        * Look up in sqlite to find the [hash, location]* of the file (no need to retrieve it)
        * Convert hashes to multihashes
        * For each multihash: location_store(multihash, location)
        *   Create a DOIfile(..)
        *   self.push(DOIfile)
        """
        verbose=kwargs.get("verbose",False)
        if verbose: print("DOI.__init__",namespace,publisher,identifier)
        super(DOI,self).__init__(namespace, publisher, *identifier)
        if verbose: print("DOI.__init__ connecting to DB")
        db = sqlite3.connect(self.SQLITE)
        if verbose: print("DOI.__init__ connected to DB")
        self.doi = self.canonical(publisher, *identifier)    # "10.nnnn/xxxx/yyyy"
        self.metadata = {}
        if verbose: print("DOI.__init__ getting metadata for",self.doi)
        self.get_doi_metadata(verbose)
        if verbose: print("DOI.__init__ looking up",self.doi)
        sha1_list = list(db.execute('SELECT * FROM files_id_doi WHERE doi = ?;', [self.doi]))

        if verbose: print("DOI.__init__ iterating over",len(sha1_list),"rows")
        for row in sha1_list:
            _, the_sha1, _ = row
            files_metadata_list = list(db.execute('SELECT * FROM files_metadata WHERE sha1 = ?;', [the_sha1]))
            _, mimetype, size_bytes, md5 = files_metadata_list[0]
            urls_list = list(db.execute('SELECT * FROM urls WHERE sha1 = ?;', [the_sha1]))
            doifile = DOIfile({
                    'doi': self.doi,
                    'urls': [self.archive_url(url) for url in urls_list],
                    'mimetype': mimetype,
                    'size_bytes': size_bytes,
                    'md5': md5,
                    'sha1': the_sha1,
                })
            sha1_hash = doifile.metadata["sha1"]
            #sha1_binary_hash = sha1_hash.decode('hex') #Python2
            sha1_binary_hash = bytes.fromhex(sha1_hash) #Python3
            multihash_binary = multihash.encode(sha1_binary_hash, 0x11)
            multihash_base58 = base58.b58encode(bytes(multihash_binary))
            doifile.metadata["sha1multihash"] = multihash_base58
            print(multihash_base58)
            self.push(doifile)
            #sha256hash = multihashsha256_58(doifile.retrieve())
            #print("Saving location", multihash_base58, doifile.metadata["urls"][0]  )
            LocationService().set(multihash_base58, doifile.metadata["urls"][0],verbose=verbose)  #TODO-FUTURE find first url that matches the sha1
            MimetypeService().set(multihash_base58, doifile.metadata["mimetype"],verbose=verbose)
            # WE'd like to stroe the sha1, but havent figured out how to reverse the hex string to binary adnd then multihash
        if verbose: print("DOI.__init__ completing")

    @classmethod
    def archive_url(cls, row):
        """
        Take a tuple of sha-1 URL datetime and return a direct URL to file content
        Currently the sqlite database has URLs with an optional datetime column.
        If the url starts "https://archive.org/download/" then it's an item/file pointer, and there is no datetime.
        If the url starts with something else, it's a URL from wayback, and the datetime can be used to construct a
        "https://web.archive.org/web/<datetime>/<url>" URL. TODO: double-check that wayback gateway supports range-requests
        :return: url to file content
        """
        sha1, url, datetime = row
        if not datetime:
            return url
        else:
            return 'https://web.archive.org/web/{}/{}'.format(datetime, url)

    def push(self,doifile):
        """
        Add a DOIfile to a DOI -
        :return:    undefined
        """
        # Currently Nothing done here other than superclass adding to list.
        super(DOI, self).push(doifile)

    def content(self, verbose=False):
        #TODO replace with something that reads out fields of object
        return {'Content-type': 'application/json',
            'data': {
                "urls": [
                    doifile.metadata for doifile in self.files()
                ]
            }
        }

    @classmethod
    def canonical(cls, publisher, *identifier):
        """
        As a pre-mature heads up, the DOI format is sort of underspecified.
        It is case-insensitive (can be used in URLs, sometimes with encoding),
        but can have weird shit like whitespace.
        The vast majority are more "well behaved", but things like parentheses are common.
        They do always start with "10\.\d+\/" (aka, 10, period, numerical digits, slash)
        Brian says its a long-tail, the vast majority of correct DOI appear to be case insensitive alphanumeric with some allowed punctuation
        This will require lookin in the Sqlite (or asking Brian) to determine suitable characters for a OK DOI
        """
        #TODO convert this identifier into a canonicised form,
        #TDO check publisher is canonicised 10.nnnn
        return publisher.lower() + "/" + "/".join([i.lower() for i in identifier])


    def check_if_link_works(self, url, verbose=False):
        """
        See if a link is valid (i.e., returns a '200' to the HTML request).
        """
        if verbose:
            print("check_if_link_works",url)
        print("XXX@check_if_link_works - dummied out")
        #return True
        try:
            headers = {"accept": "*/*"}
            # This next link can fail, it follows a redirection and then can fail on th actual PDF, which isnt what we want cos we'll use a Archive URL
            request = requests.get(url, headers=headers)
        except Exception as e:
            print("Request failed XXX",e)
            raise e
        if verbose: print("result=", request.status_code)
        return request.status_code == 200


    def get_doi_metadata(self, verbose):
        """
        For a DOI, get metadata from doi.org about that file
        TODO: pick which fields want to analyze, e.g. 
        :return: metadata on the doi in json format
        """
        url = "http://dx.doi.org/" + self.doi
        headers = {"accept": "application/vnd.citationstyles.csl+json"}
        r = requests.get(url, headers=headers) # Note that with headers it wont redirect, without it will go to doc which may fail
        if verbose: print("get_doi_metadata returned:",r)
        if r.status_code == 200:
            self.metadata = r.json()
        # If dont get metadata, the rest of our info may still be valid

class DOIfile(NameResolverFile):
    """
    Class for one file
    """
    def __init__(self, metadata):
        super(NameResolverFile, self).__init__(metadata)
        self.metadata = metadata    # For now all in one dict

    def retrieve(self):
        return httpget(self.metadata["urls"][0]) #TODO-PYTHON3 will need changing

    def content(self):
        #TODO iterate over urls and find first matching hash
        return { "Content-type": self.metadata["mimetype"], "data": self.retrieve() }

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print('hey I expected a single doi!!')
        sys.exit(-1)
    doi = DOI("doi", *sys.argv[1].split('/'))

    for i in doi.files():
        print(i)
        print(i.content())
