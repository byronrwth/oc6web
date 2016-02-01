from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext, loader


def index(request):
    info = {}
    info['note'] = 'this is to test autocomplete in manifest diff tool'
    template = loader.get_template('my_manidiff/index.html')
    context = RequestContext(request, info)
    return HttpResponse(template.render(context))

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

        context['versions'] = [
      "XMM7360_01.1511.00",
      "XMM7360_01.1511.01",
      "XMM7360_01.1511.02",
      "XMM7360_01.1515.00",
      "XMM7360_01.1515.01",
      "XMM7360_01.1515.02",
      "XMM7360_01.1521.00",
      "XMM7360_01.1521.01",
      "XMM7360_01.1525.00",
      "XMM7360_01.1525.01",
      "XMM7360_01.2051.00",
      "XMM7360_01.5061.01",
      "XMM7460_01.1511.00",
      "XMM7460_01.1511.01",
      "XMM7460_01.1511.02",
      "XMM7460_01.1515.00",
      "XMM7460_01.1515.01",
      "XMM7460_01.1515.02",
      "XMM7460_01.1521.00",
      "XMM7460_01.1521.01",
      "XMM7460_01.1525.00",
      "XMM7460_01.1525.01",
      "XMM7460_01.2051.00",
      "XMM7460_01.5061.01",
      "XMM7480_01.1511.00",
      "XMM7480_01.1511.01",
      "XMM7480_01.1511.02",
      "XMM7480_01.1515.00",
      "XMM7480_01.1515.01",
      "XMM7480_01.1515.02",
      "XMM7480_01.1521.00",
      "XMM7480_01.1521.01",
      "XMM7480_01.1525.00",
      "XMM7480_01.1525.01",
      "XMM7480_01.2051.00",
      "XMM7480_01.5061.01"  
        ]
        return render(request, 'my_manidiff/ajax_sps_tags.html', context)


 
    else:
        return render(request, 'my_manidiff/ajax_text.html', {'error_msgs': 'Error: Unsupported action "' + str(action) + '"'})
