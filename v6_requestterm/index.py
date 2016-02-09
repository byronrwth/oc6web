from collections import OrderedDict, defaultdict
from lib.debug import DEBUG
from whoosh.qparser import QueryParser
from whoosh.index import open_dir, create_in
from whoosh.fields import Schema, STORED, ID, KEYWORD, TEXT, NUMERIC, NGRAM, NGRAMWORDS
from whoosh import columns 
from rpc.lib.common import Ini
import lib.lockfile as lockfile
import datetime
from flask import json
import os
WHOOSH_FOLDER =  os.path.join(dict(Ini.getconfig().items('ORCA_FSDB'))['indexfolder'], 'w_guisearch')
try: os.makedirs(WHOOSH_FOLDER)
except: pass
import re
from rpc.lib.model.abstract.obj import Jsonable, OBJLIST

ranking_col = columns.RefBytesColumn()
schema = Schema(term=NGRAM(minsize=2, maxsize=20,stored=True, sortable=ranking_col), url=STORED(), description=STORED(), preview=STORED())

#we create the index from scratch at each app start, because it is cheaper than looking up if an entry exists
#but only in the productive mode, when starting in debug mode the index creation is skipped
#if not DEVEL_MODE: create_in(WHOOSH_FOLDER, schema) 
#lookup when we've created the last index
d = WHOOSH_FOLDER

try:
    ix = open_dir(WHOOSH_FOLDER)
except:
    create_in(WHOOSH_FOLDER, schema)
    ix = open_dir(WHOOSH_FOLDER)

#noinspection PySetFunctionToLiteral
stopwords = set(['of', 'by', 'the','in','for','a', 'and', 'or']) #words to be excluded from the index
#Stemming is a method of providing users with the ability to execute a search on a word using an alternate grammatical form, such as tense and person. 
stemming = {'running':'run', 'compound':'compounds', 'artstest':'arts test', 'chart':'graph', 'matrix':'matrice' , 'comparison':'vergleich', 'vs.': 'comparison', 'versus':'comparison',
'created':'date', 'date':'day','month':'date','time':'date', 'passrate':'pass rate', 'failrate':'fail rate', 'pass':'fail'
}

synonyms = (('feature','keywords'), ('sysdef','keywords'),('ccdef','keywords'), ('opticm', 'oc'))

class SearchIndex():
    
    keyw_index = defaultdict(list) #holding the mapping term->url
    splitter =  re.compile(r'\W+')
    collector = []

    def add_terms(self, keywords, url, description, explanation=None):
        if type(keywords) == list:
            l = keywords
        elif type(keywords) == str:
            keywords = keywords.replace('_',' ')
            keywords = keywords.replace('.',' ')           
            l = self.splitter.split(keywords)
        else: raise Exception("Cannot add %s of type %s to search index. Must be string or list "%(str(keywords), type(keywords)))
        t = [t for t in l if t not in stopwords] #remove stopwords
        t += list(set([ " ".join(s) for t in l for s in synonyms if t in s]))
        terms = " ".join(l) + " " + " ".join(stemming[t] for t in l if t in stemming) #apply stemming
        self.collector.append([terms, url, description, explanation])
        
    def create_whoosh(self):
        initlock = lockfile.ThreadSafeFile(WHOOSH_FOLDER, '_init')
        thistime = datetime.datetime.now()
        dateformat = '%d-%m-%Y %H:%M:%S'
        create_index_flag = False
        try: 
            initlock.acquire(timeout=2)
        except lockfile.LockTimeout:
            print "Lock timeout when trying to create whoosh index schema. Continuing without index creation"
            return
        except lockfile.AlreadyLocked:
            print "Already locked. Continuing without index creation"                
            return
        try:
                last_creation = datetime.datetime.strptime(initlock.read(), dateformat) #deserialize 
                print "Last index creation: %s"%datetime.datetime.strftime(last_creation, '%d-%m-%Y %H:%M:%S')
                if (thistime - last_creation).total_seconds() > 4*60*60: #4 hours  
                        create_index_flag = True
                        print "Index older than 4 hours - will recreate"
                else: print "Index is fresh - will not recreate"
        except: create_index_flag = True #do the creation anyway, maybe initial condition
        if create_index_flag:
            create_in(WHOOSH_FOLDER, schema)
            print "Creating search index"
            
            writer = ix.writer()
            for t in self.collector:
                #print "index: Adding term %s"%t[0]
                writer.add_document(term=u"%s"%t[0], url=u"%s"%t[1], description=u"%s"%t[2])
            writer.commit()
            #we can free now the collector
            self.collector = None
            #write creation time to lock file
            initlock.write(datetime.datetime.strftime(thistime, '%d-%m-%Y %H:%M:%S'))
            #remove lock
        initlock.release()
    
    def lookup(self, terms): 
        tarr = terms.split(" ")
        terms = " ".join(t for t in tarr if t not in stopwords)
        with ix.searcher() as src:
            query = QueryParser("term", ix.schema).parse(terms)
            results = src.search(query, limit=30)
            return  [[r['url'],r['description']] for r in results]
    
    def user_choice(self, term, obj, username): #nutiu TDB: rank up the items which got selected by the user
        pass

searchindex = SearchIndex()

SEARCH_LIMIT = 100

@Jsonable('index')
class AjxIndexSrc():
    def search(s, terms=None):
        #DEBUG.append(terms)
        if not terms:
            try: terms = s.qdata['term']
            except: raise NoQueryEx()
        if len(terms) < 3: #avoid overloading the search engine if the query is too short
            
            return s    
        s.data =  OBJLIST('URLS',searchindex.lookup(terms))
        return s         