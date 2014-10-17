from django.http import HttpResponse
from django.shortcuts import render

def index_page(request):
  return render(request, 'feilinn_demo/index.html', '')
