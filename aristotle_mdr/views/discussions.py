from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _

from django.http import Http404

from aristotle_mdr import models as MDR
from aristotle_mdr import forms as MDRForms
from aristotle_mdr import perms

from aristotle_mdr.models import DiscussionPost

#imports CBV
from django.views.generic import DeleteView, TemplateView, ListView, View, FormView, UpdateView
from django.utils.decorators import method_decorator

class All(TemplateView):
    # Show all discussions for all of a users workgroups
    template_name = "aristotle_mdr/discussions/all.html"
    
    """
    I put the decorator on urls.py, just in case to
    sign a pattern, use this in the controller:

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(All, self).dispatch(request, *args, **kwargs)
    """    

    def get(self, request, *args, **kwargs): 
        context = super(All, self).get_context_data(*args, **kwargs)
        context['discussions'] = self.request.user.profile.discussions

        return render(request, self.template_name, context)

class Workgroup(TemplateView):
    template_name = "aristotle_mdr/discussions/workgroup.html"
    # Show all discussions for a workgroups 
    def get(self, request, *args, **kwargs): 
        context = super(Workgroup, self).get_context_data(*args, **kwargs)
        
        wg = get_object_or_404(MDR.Workgroup, pk=self.kwargs['wgid'])
        
        if not perms.user_in_workgroup(request.user, wg):
            raise PermissionDenied
        
        context['workgroup'] = wg
        context['discussions'] = wg.discussions.all()

        return render(request, self.template_name, context)



class Post(TemplateView):
    template_name = "aristotle_mdr/discussions/post.html"
    
    def get(self, request, *args, **kwargs): 
        context = super(Post, self).get_context_data(*args, **kwargs)

        post = get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])
        
        if not perms.user_in_workgroup(request.user, post.workgroup):
            raise PermissionDenied
    
        comment_form = MDRForms.discussions.CommentForm(initial={
            'post': self.kwargs['pid']
            })

        context['workgroup'] = post.workgroup
        context['post'] = post
        context['comment_form'] = comment_form

        return render(request, self.template_name, context)

class Toggle_post(TemplateView):

    def get(self, request, *args, **kwargs):
        context = super(Toggle_post, self).get_context_data(*args, **kwargs)

        pid = self.kwargs['pid']

        post = get_object_or_404(MDR.DiscussionPost, pk=pid)
        
        if not perms.user_can_alter_post(request.user, post):
            raise PermissionDenied

        post.closed = not post.closed

        post.save()

        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))

class New(FormView):
    def post(self, request, *args, **kwargs): 
         # If the form has been submitted...
        form = MDRForms.discussions.NewPostForm(request.POST, user=request.user)  # A form bound to the POST data
        if form.is_valid():
            # process the data in form.cleaned_data as required
            new = MDR.DiscussionPost(
                workgroup=form.cleaned_data['workgroup'],
                title=form.cleaned_data['title'],
                body=form.cleaned_data['body'],
                author=request.user,
            )
            new.save()
            new.relatedItems = form.cleaned_data['relatedItems']
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[new.pk]))

        return render(request, "aristotle_mdr/discussions/new.html", {"form": form})    

    def get(self, request, *args, **kwargs):
        initial = {}
        if request.GET.get('workgroup'):
            if request.user.profile.myWorkgroups.filter(id=request.GET.get('workgroup')).exists():
                initial={'workgroup': request.GET.get('workgroup')}
            else:
                # If a user tries to navigate to a page to post to a workgroup they aren't in, redirect them to the regular post page.
                return HttpResponseRedirect(reverse("aristotle:discussionsNew"))
            if request.GET.getlist('item'):
                workgroup = request.user.profile.myWorkgroups.get(id=request.GET.get('workgroup'))
                items = request.GET.getlist('item')
                initial.update({'relatedItems': workgroup.items.filter(id__in=items)})

        form = MDRForms.discussions.NewPostForm(user=request.user, initial=initial)

        return render(request, "aristotle_mdr/discussions/new.html", {"form": form})



class New_comment(FormView):
    def post(self, request, *args, **kwargs):
        post = get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])

        if not perms.user_in_workgroup(request.user, post.workgroup):
            raise PermissionDenied
        if post.closed:
            messages.error(request, _('This post is closed. Your comment was not added.'))
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))
        
        form = MDRForms.discussions.CommentForm(request.POST)
        
        if form.is_valid():
            new = MDR.DiscussionComment(
                post=post,
                body=form.cleaned_data['body'],
                author=request.user,
            )
            new.save()
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[new.post.pk]) + "#comment_%s" % new.id)
        else:
            return render(request, "aristotle_mdr/discussions/new.html", {"form": form})

    def get(self, request, *args, **kwargs): 
        # It makes no sense to "GET" this comment, so push them back to the discussion
        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))



class Delete_comment(DeleteView):
    model = MDR.DiscussionComment

    def get_success_url(self):
        success_url = lazy(reverse, self)('aristotle:discussionsPost', args=self.kwargs['cid'])        

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if queryset is None:
                queryset = self.get_queryset()

        comment = get_object_or_404(MDR.DiscussionComment, pk=self.kwargs['cid'])

        return comment

    def delete(self, request, *args, **kwargs):    
        comment = get_object_or_404(MDR.DiscussionComment, pk=self.kwargs['cid'])        
        post = comment.post
        
        if not comment or not post:
            raise Http404

        if not perms.user_can_alter_comment(request.user, comment):
            raise PermissionDenied

        comment.delete()

        return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))



class Delete_post(DeleteView):
    model = MDR.DiscussionPost

    def get_object(self, queryset=None):
        post = get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])
        return post

    def delete(self, request, *args, **kwargs):
        post = get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])
        workgroup = post.workgroup

        if not perms.user_can_alter_post(request.user, post):
            raise PermissionDenied
        
        post.comments.all().delete()
        post.delete()

        return HttpResponseRedirect(reverse("aristotle:discussionsWorkgroup", args=[workgroup.pk]))
    
    def get_success_url(self):
        post = get_object_or_404(MDR.DiscussionPost, pk=self.kwargs['pid'])
        workgroup = post.workgroup

        return HttpResponseRedirect(reverse("aristotle:discussionsWorkgroup", args=[workgroup.pk]))

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)



def edit_comment(request, cid):
    comment = get_object_or_404(MDR.DiscussionComment, pk=cid)
    post = comment.post
    if not perms.user_can_alter_comment(request.user, comment):
        raise PermissionDenied
    if request.method == 'POST':
        form = MDRForms.discussions.CommentForm(request.POST)
        if form.is_valid():
            comment.body = form.cleaned_data['body']
            comment.save()
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[comment.post.pk]) + "#comment_%s" % comment.id)
    else:
        form = MDRForms.discussions.CommentForm(instance=comment)

    return render(request, "aristotle_mdr/discussions/edit_comment.html", {
        'post': post,
        'comment_form': form})


@login_required
def edit_post(request, pid):
    post = get_object_or_404(MDR.DiscussionPost, pk=pid)
    if not perms.user_can_alter_post(request.user, post):
        raise PermissionDenied
    if request.method == 'POST':  # If the form has been submitted...
        form = MDRForms.discussions.EditPostForm(request.POST)  # A form bound to the POST data
        if form.is_valid():
            # process the data in form.cleaned_data as required
            post.title = form.cleaned_data['title']
            post.body = form.cleaned_data['body']
            post.save()
            post.relatedItems = form.cleaned_data['relatedItems']
            return HttpResponseRedirect(reverse("aristotle:discussionsPost", args=[post.pk]))
    else:
        form = MDRForms.discussions.EditPostForm(instance=post)
    return render(request, "aristotle_mdr/discussions/edit.html", {"form": form, 'post': post})
