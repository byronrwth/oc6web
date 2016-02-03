import re, os, sys, uuid, random, datetime, json, ldap, settings, xlwt
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template import RequestContext, loader
from django.contrib.auth.models import User
from django.utils import timezone
from django.forms.models import model_to_dict
from collections import OrderedDict
from sps.SPS import SPS
from artifactory.Artifactory import Artifactory
from django.core import serializers
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.cache import cache_page

from manifest.ManifestHandler import ManifestHandler
from manifest.Helper import isPathOrTag, normalizePathAndResultXML

"""
    This method is rendering the index page. Nothing else.
"""
def index(request):
    #info = {}
    #info['note'] = 'this is to test autocomplete in manifest diff tool'
    template = loader.get_template('my_manidiff/index.html')
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
    template = loader.get_template('my_manidiff/indexsearch.html')
    context = RequestContext(request, info)
    #return HttpResponse("hello world !")
    return HttpResponse(template.render(context))


'''
def query_xmm(request, response, param):
    content = {}
    content['versions'] = ['ABC', 'ABCD', '123','123124','asfaqweqgqwe']
    #return HttpResponse(content, content_type='text/html; charset=utf8')
    return HttpResponse(template.render(content))
'''

###########################################
def ajax(request):
###########################################

    context = {}
    action = request.POST.get('action', request.GET.get('action', '')).strip()

    if action == 'get_sps_tags':  
        '''
        # Grab the project name
        try:  
            project_id = int(request.POST.get('project_id', '0').strip())
            project_id = int(project_id)

            pname = Project.objects.get(pk=project_id).name

        except:
            context['error_msgs'] = ['Unable to find a project with an ID of "' + str(project_id) + '"']

        sps = SPS()
        sps.setUserHandle(request.user)
        products = sps.getProductsWithManifestMap()
        versions = []
        for name in products.keys():
            if name.upper().startswith(pname.upper()):
                temp = sps.getVersionsByProductId(products[name], name, days=60) # Only 'Released' versions
                for x in temp:
                    versions.append(x['VersionName'])
  
        versions.sort()
        versions.reverse()  # Newest first
        context['versions'] = versions
        '''
        
        # apps/my_manidiff
        myappdir = os.path.dirname(os.path.abspath(__file__))


        myfile = open(myappdir+"/data/product.txt")

        #print(myfile)
        str = myfile.read()
        myfile.close()
        context['versions'] = str.split()
        #print(context['versions'])

        return render(request, 'my_manidiff/ajax_sps_tags.html', context)


 
    else:
        return render(request, 'my_manidiff/ajax_text.html', {'error_msgs': 'Error: Unsupported action "' + str(action) + '"'})
