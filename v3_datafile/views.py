import re, os, sys, uuid, random, datetime, json, ldap
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext, loader
from django.contrib.auth.models import User
from django.utils import timezone
from django.forms.models import model_to_dict
from collections import OrderedDict
from sps.SPS import SPS
from artifactory.Artifactory import Artifactory

from django.contrib.auth.decorators import login_required, user_passes_test

def index(request):
    info = {}
    info['note'] = 'this is to test autocomplete in manifest diff tool'
    template = loader.get_template('my_manidiff/index.html')
    context = RequestContext(request, info)
    return HttpResponse(template.render(context))

def hello(request):
    info = {}
    info['note'] = 'this is to test autocomplete in manifest diff tool'
    template = loader.get_template('my_manidiff/index2.html')
    context = RequestContext(request, info)
    #return HttpResponse("hello world !")
    return HttpResponse(template.render(context))
###########################################
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
