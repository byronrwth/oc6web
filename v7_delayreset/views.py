
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

'''
from whoosh.qparser import QueryParser
from whoosh.index import open_dir, create_in
from whoosh.fields import Schema, STORED, ID, KEYWORD, TEXT, NUMERIC, NGRAM, NGRAMWORDS

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
'''

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
def indexsearch(request):
    info = {}
    info['note'] = 'index search html'
    template = loader.get_template('manifest/indexsearch.html')
    context = RequestContext(request, info)
    #return HttpResponse("hello world !")
    return HttpResponse(template.render(context))


###########################################
def ajax(request):
###########################################
    max_spstags = 10
    context = {}
    #print "request: " , request
    #print "request.POST: " , request.POST

    #productid = request.POST.get('productid', request.GET.get('productid', '')).strip()
    productid = request.POST.get('productid').strip()
    #print "request has productid: " , productid

    if len(productid) < 3 : # not complete product id 
        print "productid too short ! "
        return render(request, 'manifest/ajax_sps_tags.html', [])

    action = request.POST.get('action', request.GET.get('action', '')).strip()

    if action == 'get_sps_tags' :  

        #context['versions'] = []
        
        keyid = str(productid).upper() # xmm7360 to XMM7360 
        #print "now start to search sps with: ", keyid

        sps = SPS()
        sps.setUserHandle(request.user)
        products = sps.getProductsWithManifestMap()

        #print  products
        '''
        {XMM7460_DPC: 63873, SOFIA_3G: 54272, XMM7272: 62421, ICE7360: 57653, MODEM_DELIVERY_ICE7360: 63768, IA7360: 64000, SOFIA_LTE_ES30_BU: 62330, XMM7360_BU: 62050, XMM7360_V1: 62445, BUTTER_SFLTE: 59430, ICE7360_FB_RFDEV3: 60999, ASU_SF_3GR_MAINT: 61610, ICE7360_FB_PROTO1: 62504, ICE7360_FB_EVT: 65315, SOFIA_LTE: 55571, SOFIA_LTE_M: 63178, SOFIA_LTE_DSDS_BU: 62172, XMM7360_DSDS_3G3G: 62011, ICE7360_FB_PROTO2: 64496, XMM7360_LWA_SW_MODEM: 64777, VZN_SF_LTE: 62521, XMM7360: 56615, XMM7360_ES1_BU: 59266, XMM7360_XG726_BU: 58476, ASU_SF_LTE: 58984, IA7360_SW_MODEM: 64009, MWR_SF_LTE: 61850, FJU_SF_LTE: 59849, ASU_SF_3GR_M: 64801, XMM7480: 63068, SOFIA_LTE_2: 57566, XMM7360_XG726: 57797, SOFIA_LTE_MTBF: 62144, ASU_SF_3GR_CUST_ES2: 62168, MOD_7272M: 61961, ICE7360_FB_PREPROTOMLB: 62092, XMM7560: 63924, XMM7360_LWA: 64521, XMM7460: 53301, ASU_SF_3GR_CUST: 62074}

        '''

        #versions = sps.getVersionsByProductName(product_name, 30)
        # product, number of days
        #versions = sps.getVersionsByProductName("XMM7360", 12) 
        versions = sps.getVersionsByProductName(keyid, 20) 

        #print versions
        '''
        [(Version1){
            VersionId = "43956741"
            VersionName = "XMM7360_1604_3_1602"
            State = "Released"
            ReleaseDate = 2016-01-27 00:00:00
            IsDraftVersion = "Y"
            isDraftVersion = True
            weekNum = "1604"
            isNewWeek = True
            isTarget = False
        }, 
        ......
        '''

        if versions != None:
            #context['latest'] = versions[0]['VersionName']
            context['versions'] = []
            #best = None
            for v in versions:
                context['versions'].append(v['VersionName']) # Append indicator according to state:  + "," + str(0 if v['isDraftVersion'] else 1))
                
                #if not best and not v['isDraftVersion']:
                #    best = v['VersionName']

            if len(context['versions']) > max_spstags:
                context['versions'] = context['versions'][:max_spstags]

        #settings.BASE_DIR = webfe
        #myappdir = os.path.dirname(os.path.abspath(__file__))
        '''
          context['versions'] should be real SPS tags, temporarily saved in product.txt 
        '''
        return render(request, 'manifest/ajax_sps_tags.html', context)
        #return HttpResponse(json.dumps(context), status=200, content_type="application/json")

        
        ''' this is using temp product.txt 
        myappdir = os.path.join(settings.BASE_DIR, "apps/manifest/data/");
        


        myfile = open(myappdir+"product.txt")

        #print(myfile)
        str = myfile.read()
        myfile.close()
        context['versions'] = str.split()
        #print(context['versions'])

        return render(request, 'manifest/ajax_sps_tags.html', context)
        '''

 
    else:
        return render(request, 'manifest/ajax_text.html', {'error_msgs': 'Error: Unsupported action "' + str(action) + '"'})
