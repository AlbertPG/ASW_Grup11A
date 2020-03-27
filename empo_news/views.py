from datetime import date

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

from empo_news.models import Contribution, User
from django.urls import reverse
from empo_news.forms import SubmitFor

def submit(request):
    form = SubmitForm()
    submit_response = request.POST

    if submit_response.get('submit_button'):
        contribution = Contribution(None, 'Albert', submit_response.get('title'), 1, date.today(), submit_response.get('url'),
                                    None, 0)
        contribution.save()
        return HttpResponseRedirect(reverse('empo_news:main_page_logged'))

    context = {
        'form': form,
    }
    return render(request, 'empo_news/submit.html', context)

  
def main_page(request):
    most_points_list = Contribution.objects.order_by('-points')[:29]
    context = {
        "list": most_points_list,
        "user": User(username="Pepe05")
    }
    return render(request, 'empo_news/main_page_logged.html', context);


def new_page(request):
    most_recent_list = Contribution.objects.order_by('-publication_time')[:29]
    context = {
        "list": most_recent_list,
        "user": User(username="Pepe05"),
        "highlight": "new"
    }
    return render(request, 'empo_news/main_page_logged.html', context);


def not_implemented(request):
    return HttpResponse('View not yet implemented');
