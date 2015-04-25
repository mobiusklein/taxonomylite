'''
A simple one-file solution for those times when you want to check if one organism is
a descended from another, but don't need a full phylogenetic tree manipulation library
like DendroPy, PyCogent, or ETE.

The library is just a single file that depends only upon the standard library.
You can easily embed it in another library by copying this script.
'''

import sqlite3
import tarfile

from os import remove
from urllib2 import urlopen


def _strip_tab(name):
    return name.replace('\t', '')

#: The default location to download taxonomy information from
SOURCE_URL = "ftp://ftp.ncbi.nih.gov/pub/taxonomy/taxdump.tar.gz"
#: The separator used to tokenize the in-database lineage string
SEP_TOKEN = "!!"


def _from_ftp(url=SOURCE_URL):
    if url is not None:
        with open("taxdump.tar.gz", 'wb') as outhandle:
            outhandle.writelines(urlopen(url))
    with tarfile.open("taxdump.tar.gz", 'r:gz') as tarchive:
        tarchive.extract("names.dmp")
        tax2name = {}

        for line in open("names.dmp"):
            tax_id, name, unique_name, name_class, _ = map(_strip_tab, line.split("|"))
            if name_class == "scientific name":
                tax2name[tax_id] = unique_name if name == "" else name
        remove("names.dmp")
        tarchive.extract("nodes.dmp")

        for line in open("nodes.dmp"):
            parts = map(_strip_tab, line.split("|"))
            tax_id, parent_tax_id, rank = parts[:3]
            name = tax2name[tax_id]
            yield tax_id, name, parent_tax_id, rank
        remove("nodes.dmp")


class Taxonomy(object):
    """Operate on taxonomic hierarchies downloaded from the NCBI Taxonomy database
    using a compact SQLite database.

    Parameters
    ----------
    store_path: str
        Path to the sqlite database containing the hierarchies


    Attributes
    ----------
    connection: sqlite3.Connection
        The underlying connection to the sqlite database
    """
    @classmethod
    def from_source(cls, store_path='taxonomy.db', url=SOURCE_URL):
        """Construct a new :class:`Taxonomy` instance and associated database file
        from source data downloaded from NCBI's FTP servers.

        If `url` is :const:`None`, then it will look for the source information in the
        current directory at the name "taxdump.tar.gz".


        Parameters
        ----------
        store_path: str
            Path to construct the database at. Defaults to "taxonomy.db" in the current
            directory
        url: str
            The URL to download the taxonomy information from. Defaults to :data:`SOURCE_URL`

        Returns
        -------
        :class:`Taxonomy`
        """
        store = cls(store_path)
        store._init_schema()
        store.executemany('INSERT INTO taxonomy VALUES (?,?,?,?,"");', _from_ftp(url))
        store._construct_lineage()
        store._init_index()
        store.commit()
        return store

    def __init__(self, store_path):
        self.store_path = store_path
        self.connection = sqlite3.connect(store_path)

    def _init_schema(self):
        self.execute('DROP TABLE IF EXISTS taxonomy')
        self.execute('''CREATE TABLE taxonomy (taxa_id INTEGER PRIMARY KEY,
                                               taxa_name VARCHAR(50),
                                               parent_taxa INTEGER,
                                               rank VARCHAR(20),
                                               lineage VARCHAR(200));''')
        self.commit()

    def _init_index(self):
        self.execute('''CREATE INDEX IF NOT EXISTS taxname ON taxonomy(taxa_name);''')
        self.execute('''CREATE INDEX IF NOT EXISTS parent_id ON taxonomy(parent_taxa);''')
        self.commit()

    def _construct_lineage(self):
        tax2lineage = {}
        for row in self.execute("SELECT * FROM taxonomy"):
            lineage = self.lineage(row[0])
            tax2lineage[row[0]] = SEP_TOKEN + SEP_TOKEN.join(map(str, lineage)) + SEP_TOKEN

        self.executemany("UPDATE taxonomy SET lineage = ?2 WHERE taxa_id = ?1;", tax2lineage.iteritems())

    def execute(self, stmt, args=""):
        """Execute raw SQL against the underlying database.

        See :meth:`sqlite3.Connection.execute`
        """
        return self.connection.execute(stmt, args)

    def executemany(self, stmt, args=""):
        return self.connection.executemany(stmt, args)

    def close(self):
        """Close the underlying database connection.

        See :meth:`sqlite3.Connection.close`
        """
        self.connection.close()

    def commit(self):
        """Save pending changes to the underlying database

        See :meth:`sqlite3.Connection.commit`
        """
        self.connection.commit()

    def name_to_tid(self, name):
        """Translates a scientific name `name` string into its equivalent taxonomic id number

        Parameters
        ----------
        name: str
            A scientific name like "Homo sapiens"

        Returns
        -------
        tid: int
        """
        result = self.execute(
            "SELECT taxa_id FROM taxonomy WHERE taxa_name = ?", (name,)).fetchone()
        if result is not None:
            result = result[0]
        return result

    def tid_to_name(self, tid):
        """Translates a taxonomic id number `tid` into its equivalent scientific name

        Parameters
        ----------
        tid: int
            A taxonomic id number like 9606
        Returns
        -------
        name: str
            A scientific name like "Homo sapiens"
        """

        tid = (tid,)
        result = self.execute(
            "SELECT taxa_name FROM taxonomy WHERE taxa_id = ?", tid).fetchone()
        if result is not None:
            result = result[0]
        return result

    def is_parent(self, child_tid, parent_tid):
        """Test if `parent_tid` is a parent taxa of `child_tid`

        Parameters
        ----------
        child_tid: int
        parent_tid: int

        Returns
        -------
        bool
        """
        parent_tid = "%!" + str(parent_tid) + "!%"
        child_tid = child_tid
        try:
            self.execute('''SELECT taxa_id FROM taxonomy WHERE taxa_id = ?
                                                         AND lineage LIKE ?''',
                         (child_tid, parent_tid)).next()
            return True
        except StopIteration:
            return False

    def is_child(self, child_tid, parent_tid):
        """Test if `child_tid` is a child taxa of `parent_tid`

        Parameters
        ----------
        child_tid: int
        parent_tid: int

        Returns
        -------
        bool
        """
        return self.is_parent(parent_tid, parent_tid)

    def lineage(db, tid):
        """Construct the taxonomic "path" from `tid` to the root of the
        phylogenetic hierarchy

        Parameters
        ----------
        tid: int

        Returns
        -------
        list of ints
        """
        path = []
        path.append(tid)
        while tid != 1:
            tid = db.parent(tid)
            if tid is None:
                break
            path.append(tid)
        return path[::-1]

    def children(self, tid, deep=False):
        """Retrieve all child taxonomic id numbers of `tid`. If `deep` is `True`, retrieve all descendants

        Parameters
        ----------
        tid: int
        deep: bool
            Retrieve all descendants, not just direct children

        Returns
        -------
        list of ints
        """
        tid = (tid,)
        children = []
        if deep:
            tid = ("%!" + str(tid[0]) + "!%",)
            for row in self.execute("SELECT taxa_id FROM taxonomy WHERE lineage LIKE ?", tid):
                children.append(row[0])
        else:
            for row in self.execute("SELECT taxa_id FROM taxonomy WHERE parent_taxa = ?", tid):
                children.append(row[0])
        return children

    def parent(self, tid):
        """Extract the taxonomic id number of the parent of `tid`

        Parameters
        ----------
        tid: int

        Returns
        -------
        int
        """
        tid = (tid,)
        parent = self.execute("SELECT parent_taxa FROM taxonomy WHERE taxa_id = ?", tid).fetchone()
        return parent if parent is None else parent[0]

    def siblings(self, tid):
        """Extract the taxonomic id numbers of the siblings (same parent) of `tid`

        Parameters
        ----------
        tid: int

        Returns
        -------
        list of ints
        """
        parent = self.parent(tid)
        siblings = self.children(parent)
        siblings.remove(tid)
        return siblings

    def relatives(self, tid, degree=1):
        """Retrieve relatives of `tid` out to `degree` steps removed

        Parameters
        ----------
        tid: int
        degree: int

        Returns
        -------
        list of ints
        """
        relatives = []
        parent = self.parent(tid)
        relatives.append(parent)
        children = self.children(tid)
        relatives.extend(children)
        next_taxon = tid
        for i in range(degree-1):
            siblings = self.siblings(next_taxon)
            children_next_taxon = []
            for item in children:
                grandchildren = self.children(item)
                children_next_taxon = children_next_taxon + grandchildren
            children = children_next_taxon + siblings
            relatives = relatives + children
            next_taxon = parent
            parent = self.parent(parent)
            relatives.append(parent)
        return relatives