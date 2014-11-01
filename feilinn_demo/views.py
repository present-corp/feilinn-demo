from django.template.loader import get_template
from django.template import Context, Template, RequestContext
from django.http import HttpResponse
from django.shortcuts import render, render_to_response
from feilinn_demo.models import Post
import datetime

def index_page(request):
  return render(request, 'feilinn_demo/index.html', '')

def index(request):
    if request.method == 'POST':
       # save new post
       title = request.POST['title']
       content = request.POST['content']

       post = Post(title=title)
       post.last_update = datetime.datetime.now() 
       post.content = content
       post.save()

    # Get all posts from DB
    posts = Post.objects 
    return render_to_response('feilinn_demo/index_s.html', {'Posts': posts},
                              context_instance=RequestContext(request))


def update(request):
    id = eval("request." + request.method + "['id']")
    post = Post.objects(id=id)[0]
    
    if request.method == 'POST':
        # update field values and save to mongo
        post.title = request.POST['title']
        post.last_update = datetime.datetime.now() 
        post.content = request.POST['content']
        post.save()
        template = 'feilinn_demo/index_s.html'
        params = {'Posts': Post.objects} 

    elif request.method == 'GET':
        template = 'feilinn_demo/update.html'
        params = {'post':post}
   
    return render_to_response(template, params, context_instance=RequestContext(request))
                              

def delete(request):
    id = eval("request." + request.method + "['id']")

    if request.method == 'POST':
        post = Post.objects(id=id)[0]
        post.delete() 
        template = 'feilinn_demo/index_s.html'
        params = {'Posts': Post.objects} 
    elif request.method == 'GET':
        template = 'feilinn_demo/delete.html'
        params = { 'id': id } 

    return render_to_response(template, params, context_instance=RequestContext(request))
