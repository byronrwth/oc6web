#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from django.shortcuts import render, redirect
from django.template import RequestContext, loader
from django.http import HttpResponse, HttpResponseRedirect
from django.core import serializers
from sps.SPS import SPS
from django.views.decorators.cache import cache_page
from manifest.ManifestHandler import ManifestHandler
from manifest.Helper import isPathOrTag, normalizePathAndResultXML
import settings
import xlwt
import os
import datetime
import sys
import json
import ldap, settings

import re
from collections import OrderedDict, defaultdict
#import lib.lockfile as lockfile
#from rpc.lib.common import Ini
from whoosh.qparser import QueryParser
from whoosh.index import open_dir, create_in
from whoosh.fields import Schema, STORED, ID, KEYWORD, TEXT, NUMERIC, NGRAM, NGRAMWORDS
from whoosh.analysis import RegexAnalyzer
# for chinese support
#from whoosh.analysis import RegexAnalyzer

#WHOOSH_FOLDER =  os.path.join(dict(Ini.getconfig().items('ORCA_FSDB'))['indexfolder'], 'w_guisearch')


#try: os.makedirs(WHOOSH_FOLDER)
#except: pass



#schema = Schema(term=NGRAM(minsize=2, maxsize=20,stored=True, sortable=ranking_col), url=STORED(), description=STORED(), preview=STORED())



#we create the index from scratch at each app start, because it is cheaper than looking up if an entry exists
#but only in the productive mode, when starting in debug mode the index creation is skipped
#if not DEVEL_MODE: create_in(WHOOSH_FOLDER, schema)
#lookup when we've created the last index




'''
if not os.path.exists(os.path.join(settings.BASE_DIR, "apps/manifest/whooshindex/")):
#os.mkdir('whooshindex')
    os.makedirs(os.path.join(settings.BASE_DIR, "apps/manifest/whooshindex/")
'''

WHOOSH_FOLDER = os.path.join(settings.BASE_DIR, "apps/manifest/whooshindex/")
try: os.makedirs(WHOOSH_FOLDER)
except: print "whoosh folder already exist "

#print WHOOSH_FOLDER #=/local/chengxi/my_new_oc6web_checkout/webfe/apps/manifest/whooshindex/

#print settings.BASE_DIR #=/local/chengxi/my_new_oc6web_checkout/webfe

rex = RegexAnalyzer(ur"([\u4e00-\u9fa5])|(\w+(\.?\w+)*)")
schema = Schema(term=NGRAM(minsize=2, maxsize=20,stored=True), tag=STORED(), product=STORED(), url=STORED(), description=STORED(), preview=STORED())  # product= TEXT doesn't store !!

#try:
#    ix = open_dir(WHOOSH_FOLDER)
#except:
print "now create search index ! "
create_in(WHOOSH_FOLDER, schema)
ix = open_dir(WHOOSH_FOLDER)

stopwords = set(['of', 'by', 'the','in','for','a', 'and', 'or'])

stemming = {'running':'run', 'compound':'compounds', 'artstest':'arts test', 'chart':'graph', 'matrix':'matrice' , 'comparison':'vergleich', 'vs.': 'comparison', 'versus':'comparison',
    'created':'date', 'date':'day','month':'date','time':'date', 'passrate':'pass rate', 'failrate':'fail rate', 'pass':'fail', 'xmm7360':'7360'
    }

synonyms = (('feature','keywords'), ('sysdef','keywords'),('ccdef','keywords'), ('opticm', 'oc'))



"""
    This method is rendering the index page. Nothing else.
"""
def index(request):
    template = loader.get_template('manifest/index.html')
    context = RequestContext(request, {})
    return HttpResponse(template.render(context))

"""
    Provide access to detailed information.
    This method is called as an ajax callback from the main page.
"""
@cache_page(60*30)
def ajaxHandler(request, a, b, form):
    if form == 'table':
        return tableDiff(request, a, b)
    elif form == 'list':
        return fullDiff(request, a, b)
    elif form == 'json':
        return jsonDiff(request, a, b)
    elif form == 'excel':
        return excelDiff(request, a, b)

    template = loader.get_template('manifest/error-inner.html')
    context = RequestContext(request, {
                'error': 'This format is not supported. Please use of one: '+
                         '<b>table</b>, <b>list</b>, <b>excel</b> or <b>json</b>.'
              })
    return HttpResponse(template.render(context))

"""
    Provide Diff framework for main page.
    This loads the body and summary, but not the details.
"""
@cache_page(60*30)
def diff(request, file1, file2):
    param = {'file1': file1,
             'file2': file2 }

    if not file1 or not file2:
        summary = { "error": "Not able to generate diff without two parameters" }
        template = loader.get_template('manifest/error.html')
    elif not (isPathOrTag(file1) and isPathOrTag(file2)):
        summary = { "error": "Malformed parameter. Please cross check that the given input is a path or a string containing A-z, 0-9, _, -." }
        template = loader.get_template('manifest/error.html')
    else:
        mh = ManifestHandler()
        summary = mh.diff(file1, file2, { 'remote': False, 'full': False })
        param['summary'] = summary
        if summary.error:
            template = loader.get_template('manifest/error.html')
        else:
            template = loader.get_template('manifest/diff.html')

    context = RequestContext(request, param)
    return HttpResponse(template.render(context))


def fullDiff(request, file1, file2):

    if not file1 or not file2:
        summary = { "error": "Not able to generate diff without two parameters" }
        template = loader.get_template('manifest/error-inner.html')
    elif not (isPathOrTag(file1) and isPathOrTag(file2)):
        summary = { "error": "Malformed parameter. Please cross check that the given input is a path or a string containing A-z, 0-9, _, -." }
        template = loader.get_template('manifest/error-inner.html')
    else:
        mh = ManifestHandler()
        summary = mh.diffAdvanced(file1, file2, { 'remote': True, 'full': True, 'Gerrit': True })
        if summary.error:
            template = loader.get_template('manifest/error-inner.html')
        else:
            template = loader.get_template('manifest/diff-as-list.html')

    context = RequestContext(request, { 'file1': file1, 'file2': file2, 'summary': summary, 'format': 'list'})
    return HttpResponse(template.render(context))

@cache_page(60*30)
def tableDiff(request, file1, file2):
    if not file1 or not file2:
        summary = { "error": "Not able to generate diff without two parameters" }
        template = loader.get_template('manifest/error-inner.html')
    elif not (isPathOrTag(file1) and isPathOrTag(file2)):
        summary = { "error": "Malformed parameter. Please cross check that the given input is a path or a string containing A-z, 0-9, _, -." }
        template = loader.get_template('manifest/error-inner.html')
    else:
        mh = ManifestHandler()
        summary = mh.diffAdvanced(file1, file2, { 'remote': True, 'full': False, 'Gerrit': True })
        template = loader.get_template('manifest/diff-as-table.html')

    context = RequestContext(request, { 'file1': file1, 'file2': file2, 'summary': summary, 'format': 'table' })
    return HttpResponse(template.render(context))

@cache_page(60*30)
def jsonDiff(request, file1, file2):
    if not (file1 and file2 and isPathOrTag(file1) and isPathOrTag(file2)):
        summary = { "error": "Not able to generate diff without two valid parameters." }
    else:
        mh = ManifestHandler()
        summaryObj = mh.diff(file1, file2, { 'remote': True })
        summary = summaryObj.toJSON()

    return HttpResponse(summary, content_type="application/json")

@cache_page(60*30)
def excelDiff(request, file1, file2):
    template = loader.get_template('manifest/error.html')
    if not file1 or not file2:
        err = { "error": "Not able to generate diff without two parameters" }
        context = RequestContext(request, param)
        return HttpResponse(template.render(err))
    elif not (isPathOrTag(file1) and isPathOrTag(file2)):
        err = { "error": "Malformed parameter. Please cross check that the " +\
                         "given input is a path or a string containing A-z, 0-9, _, -." }
        context = RequestContext(request, param)
        return HttpResponse(template.render(err))

    mh = ManifestHandler()
    summary = mh.diffAdvanced(file1, file2, {
                    'remote': True,
                    'Gerrit': True,
                    'UTP': True,
                    'Orca': True,
                 })

    response = HttpResponse(content_type='application/ms-excel')
    name = '--'.join([os.path.basename(file1), os.path.basename(file2) ])
    response['Content-Disposition'] = 'attachment; filename={0}.xls'.format(name)
    wb = xlwt.Workbook(encoding='utf-8')
    wsChanged = wb.add_sheet("Changes with UTP")
    wsChanged2= wb.add_sheet("Changes without UTP")

    styleTableHeader = xlwt.XFStyle()
    styleTableHeader.font.bold = True

    styleTableCell = xlwt.XFStyle()
    styleTableCell.alignment.wrap = 1

    #
    # Handling "Changed"
    # -------------------------------------------------------------
    if summary.changes:
        row_num1 = 0
        row_num2 = 0
        columns = [
            ('UTP', 'UTP', 3600, None), #"https://utpreloaded.rds.intel.com/CqUtpSms/?Id={0}"),
            ('title', 'UTP Headline', 20000, None),
            ('p_lev1_name', 'Project', 3000, None),
            ('cq_state', 'UTP Status', 3000, None),
            #('subject', 'Commit Message', 20000, None),
            ('author', 'Committed by', 4000, None),
            ('hash', 'Commit Hash', 9000, None), #"https://opticm6.rds.intel.com/r/#/q/{0},n,z"),
            ('date', 'Commit Date', 3500, None),
            ('repo', 'Commit Repo', 6000, None),
            ('branch', 'Commit Branch', 6000, None),
            ('integration_tag', 'Integration Tag', 6000, None),
            ('integration_date', 'Integration Date', 3500, None),
        ]

        for col_num in xrange(len(columns)):
            wsChanged.write(row_num1, col_num, columns[col_num][1], styleTableHeader)
            wsChanged2.write(row_num2, col_num, columns[col_num][1], styleTableHeader)
            # set column width
            wsChanged.col(col_num).width = columns[col_num][2]
            wsChanged2.col(col_num).width = columns[col_num][2]

        changeDict = summary.changes
        for (repo, changes) in changeDict.iteritems():
            for c in changes:
                if 'UTP' in c and len(c['UTP']) > 0:
                    utp_list = c['UTP']
                    sheet = wsChanged
                    row_num = row_num1
                    row_num1 += len(utp_list)
                else:
                    utp_list = ['']
                    sheet = wsChanged2
                    row_num = row_num2
                    row_num2 += len(utp_list)

                for utp in utp_list:
                  row_num += 1
                  for col_num in xrange(len(columns)):
                    col_name = columns[col_num][0]
                    if col_name == 'UTP':
                      text = utp
                    elif col_name in c:
                      text = c[ columns[col_num][0] ]
                      if col_name == 'date':
                          text = datetime.datetime.fromtimestamp(int(text)).strftime(settings.STRFTIME_FORMAT)
                      elif col_name == 'integration_date':
                          text = text.strftime(settings.STRFTIME_FORMAT)

                    elif col_name == 'repo':
                      text = repo
                    elif col_name == 'branch' and 'approvals' in c and 'branch' in c['approvals']:
                      text = c['approvals']['branch']
                    else:
                      text = '-'
                    sheet.write(row_num, col_num, text, styleTableCell)

    #
    # Handling "Added"
    # -------------------------------------------------------------
    if summary.added:
      wsAdded   = wb.add_sheet("Added Repos")
      row_num = 0
      col_num = 0
      columns = [
          (u"Added Repo Name", 10000),
      ]
      for col_num in xrange(len(columns)):
          wsAdded.write(row_num, col_num, columns[col_num][0], styleTableHeader)
          # set column width
          wsAdded.col(col_num).width = columns[col_num][1]

      for name in summary.added:
          row_num += 1
          wsAdded.write(row_num, 0, name, styleTableCell)

    #
    # Handling "Removed"
    # -------------------------------------------------------------
    if summary.removed:
      wsRemoved = wb.add_sheet("Removed Repos")
      row_num = 0
      col_num = 0
      columns = [
          (u"Removed Repo Name", 10000),
      ]
      for col_num in xrange(len(columns)):
          wsRemoved.write(row_num, col_num, columns[col_num][0], styleTableHeader)
          # set column width
          wsRemoved.col(col_num).width = columns[col_num][1]

      for name in summary.removed:
          row_num += 1
          wsRemoved.write(row_num, 0, name, styleTableCell)


    wb.save(response)
    return response

def getManifest(request, name):
    content = normalizePathAndResultXML(name)
    return HttpResponse(content, content_type="application/xml")


###########################################
'''
def indexsearch(request):
    info = {}
    info['note'] = 'index search html'
    template = loader.get_template('manifest/indexsearch.html')
    context = RequestContext(request, info)
    return HttpResponse(template.render(context))
'''
############ whoosh search #####################
class SearchIndex():

    keyw_index = defaultdict(list) #holding the mapping term->url
    splitter =  re.compile(r'\W+')
    collector = []

    def add_terms(self, keywords, tag, product, url, description, explanation=None):
        #print "adding_terms: keywords= ", keywords

        if type(keywords) == list:
            #print "keywords is list: "
            l = keywords
        elif type(keywords) == str:
            #print "keywords is str: "
            keywords = keywords.replace('_',' ')
            keywords = keywords.replace('.',' ')
            l = self.splitter.split(keywords)
        #else: raise Exception("Cannot add %s of type %s to search index. Must be string or list "%(str(keywords), type(keywords)))
        else:
            #print "keywords is text: "
            keywords = keywords.replace('_',' ')
            keywords = keywords.replace('.',' ')
            l = self.splitter.split(keywords)
            #print "l: ", l

        t = [t for t in l if t not in stopwords] #remove stopwords
        #print "t: "
        #print t

        t += list(set([ " ".join(s) for t in l for s in synonyms if t in s]))
        #print "t: "
        #print t

        terms = " ".join(l) + " " + " ".join(stemming[t] for t in l if t in stemming) #apply stemming
        #print "terms: ", terms #XMM7360 1604 3 1602   : including white spaces between !

        self.collector.append([terms, tag, product, url, description, explanation])

    def create_whoosh(self):
        print "creating_whoosh: "

        #initlock = lockfile.ThreadSafeFile(WHOOSH_FOLDER, '_init')
        thistime = datetime.datetime.now()
        dateformat = '%d-%m-%Y %H:%M:%S'
        create_index_flag = False
        #try:
        #    initlock.acquire(timeout=2)
        #except lockfile.LockTimeout:
        #    print "Lock timeout when trying to create whoosh index schema. Continuing without index creation"
        #    return
        #except lockfile.AlreadyLocked:
        #    print "Already locked. Continuing without index creation"
        #    return

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
                #print "index: Adding term %s,"%t[0]
                #print "index: Adding tag %s,"%t[1]
                #print "index: Adding product= %s,"%t[2]

                #writer.add_document(term=u"%s"%t[0], url=u"%s"%t[1], description=u"%s"%t[2])
                writer.add_document(term=u"%s"%t[0], tag=u"%s"%t[1], product=u"%s"%t[2], url=u"%s"%t[3], description=u"%s"%t[4])

            writer.commit()
            #we can free now the collector
            #self.collector = None
            self.collector = []  # None.append doesn't exist !

            #write creation time to lock file
            #initlock.write(datetime.datetime.strftime(thistime, '%d-%m-%Y %H:%M:%S'))
            #remove lock
        #initlock.release()

    def lookup(self, terms):
        print "looking_up terms: ", terms

        tarr = terms.split(" ")
        terms = " ".join(t for t in tarr if t not in stopwords)

        print "joined terms:", terms

        with ix.searcher() as src:
            query = QueryParser("term", ix.schema).parse(terms)
            results = src.search(query, limit=30)

            #print "results: ", results
            #for r in results:
            #    print "r: " , r

            """
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0815 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0702 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0602 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0504 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0402 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0306 ', 'description': u'None'}>
            r:  <Hit {'url': u'None', 'term': u'XMM7460 1607 2 0202 ', 'description': u'None'}>
            type of found:  <type 'list'>
            """
            #print r for r in results

            #print "test with ix.searcher().find: ", ix.searcher().find("term", "XMM7460")

            #print "test with ix.searcher().find: ", ix.searcher().find("keywords", u"XMM7460")

            #print "test with parse(\"xmm7460\"): ", src.search(QueryParser("term", ix.schema).parse("xmm7460"), limit=30)

            #print "test with parse(\"XMM7460\"): ", src.search(QueryParser("term", ix.schema).parse("XMM7460"), limit=30)

            #print "test with QueryParser keywords (\"XMM7460\"): ", src.search(QueryParser("keywords", ix.schema).parse("XMM7460"), limit=30)

            #return  [[r['url'],r['description']] for r in results]


            return  [[ r['tag'],r['product'] ] for r in results]
            #return
            # <Top 0 Results for Term('term', u'xmm7460') runtime=4.19616699219e-05>

            #return  [r for r in results]

    def user_choice(self, term, obj, username): #nutiu TDB: rank up the items which got selected by the user
        print "user_choice: "
        pass

searchindex = SearchIndex()

SEARCH_LIMIT = 100
###########################################
def ajax(request):
###########################################

    """
    test_writer = ix.writer()

    test_writer.add_document(term=u"XMM7660 1111 hello world 1111 xmm7360", product=u"XMM7560", url="", description="")

    test_writer.commit()
    results = ix.searcher().find("term", "world")

    print "test for whoosh, results: ",  results
    """
    ################################################
    max_spstags = 10
    context = {}



    productid = request.POST.get('productid').strip()
    print "request has productid: " , productid


    if len(productid) < 3: #7 : # not complete product id
        #print "productid too short ! "
        return render(request, 'manifest/ajax_sps_tags.html', [])

    action = request.POST.get('action', request.GET.get('action', '')).strip()

    if action == 'get_sps_tags' :

        #context['versions'] = []

        """
        #print " search index lookup productid: "
        product_list = ['7260', '7360', '7460', '7480', '7560', 'sofia_lte']
        for anyproduct in  product_list:
            match = re.search(anyproduct,  productid )
            if match != None:
                print "match to product: " , match.group(0)
                break
            else:
                print "not match with product: ", anyproduct
        """

        #?? reqproduct = match.group(0)

        temp = str(productid).upper()
        #print "searchindex.lookup(temp):", searchindex.lookup(temp) #searchindex.lookup(terms)

        # first search within whoosh index
        lookup = searchindex.lookup(temp)
        if len(lookup) > 0:
            context['versions'] = []  #empty list, not None, None.append doesn't exist

            for found in lookup:
                #print "type of found: ", type(found) # l
                #print " length of found: ", len(found)

                if found[0] != None:
                    #print "found[0] found:", found[0]
                    #print "found[1] found:", found[1]

                    #reqproduct = found[1]

                    context['versions'].append(found[0]) # Append indicator according to stat

            #print "lookup in whoosh: ", context['versions']

        #if searchindex.lookup(productid) == None:
        #if found['product'] == None:
        else : #len(lookup) == 0: no found in lookup

            reqproduct="xmm"

            product_list = ['7260', '7360', '7460', '7480', '7560', 'sofia_lte']

            for anyproduct in  product_list:
                match = re.search(anyproduct,  productid )
                if match != None:
                    print "match to product: " , match.group(0)
                    reqproduct = reqproduct + str(match.group(0))
                    print "reqproduct= ", reqproduct
                    break
                else:
                    print "not match with product: ", anyproduct

            if reqproduct is "xmm":
                return render(request, 'manifest/ajax_sps_tags.html', [])

            #keyid = str(productid).upper()
            keyid = str(reqproduct).upper() # xmm7360 to XMM7360
            print "now start to search sps with: ", keyid   # grep meaningful product keyword from input

            sps = SPS()
            sps.setUserHandle(request.user)
            #products = sps.getProductsWithManifestMap()


            #versions = sps.getVersionsByProductName(product_name, 30)
            # product, number of days
            #versions = sps.getVersionsByProductName("XMM7360", 12)
            versions = sps.getVersionsByProductName(keyid, 20)
            #print "versions: ", versions

            if versions != None:
                #context['latest'] = versions[0]['VersionName']

                context['versions'] = []
                count = 0
                #best = None
                for v in versions:
                    #print "v:", v
                    context['versions'].append(v['VersionName']) # Append indicator according to state:  +  "," + str(0 if v['isDraftVersion'] else 1))

                    if count < max_spstags:
                        searchindex.add_terms( keywords = v['VersionName'], tag=v['VersionName'], product = keyid, url=None,  description=None, explanation=None)
                        count = count +1

                    #if not best and not v['isDraftVersion']:
                    #    best = v['VersionName']

                #print "before create_whoosh, add terms to collector:"
                #print type(searchindex.collector) # list
                if len(searchindex.collector) == 0:
                    print " empty collector !"
                else:
                    #print "type of collector: ", type(searchindex.collector)
                    #print searchindex.collector
                    searchindex.create_whoosh();


                #print "after create_whoosh, collector should be None:", searchindex.collector

                if len(context['versions']) > max_spstags:
                    context['versions'] = context['versions'][:max_spstags]

        #print context
        ''' e.g.
        {'versions': [XMM7360_1604_3_1602, XMM7360_1604_3_1503, XMM7360_01.1605.10, XMM7360_1604_3_1415, XMM7360_1604_3_0903, XMM7360_1604_3_0802, XMM7360_1604_3_0703, XMM7360_1604_3_0602, XMM7360_1604_3_0555, XMM7360_1604_3_0402]}

        '''
        return render(request, 'manifest/ajax_sps_tags.html', context)
        #return HttpResponse(json.dumps(context), status=200, content_type="application/json")



    else:
        return render(request, 'manifest/ajax_text.html', {'error_msgs': 'Error: Unsupported action "' + str(action) + '"'})
