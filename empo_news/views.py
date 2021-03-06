import base64
from datetime import datetime

from django.contrib.auth import logout as do_logout
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from rest_framework import viewsets, renderers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from empo_news.APIKeyManager import APIKeyManager
from empo_news.errors import UrlAndTextFieldException, UrlIsTooLongException, TitleIsTooLongException, \
    NotFoundException, ForbiddenException, UnauthenticatedException, ConflictException, ContributionUserException, \
    InvalidQueryParametersException, UrlCannotBeModifiedException
from empo_news.forms import SubmitForm, CommentForm, UserUpdateForm
from empo_news.models import Contribution, UserFields, Comment
from empo_news.permissions import KeyPermission
from empo_news.serializers import ContributionSerializer, UrlContributionSerializer, AskContributionSerializer, \
    CommentSerializer, UserFieldsSerializer


def get_domain(url):
    return url.split('www.')[1].split('/')[0]


def submit(request):
    form = SubmitForm()

    if request.method == 'POST':
        form = SubmitForm(request.POST)

        if form.is_valid():
            contribution = Contribution(user=request.user, title=form.cleaned_data['title'],
                                        publication_time=datetime.today(), text='')
            if form.cleaned_data['url'] and SubmitForm.valid_url(form.cleaned_data['url']):
                url_split = form.cleaned_data['url'].split('/')
                if url_split[0] == "http:" or url_split[0] == "https:":
                    domain_split = url_split[2].split('.')
                    if domain_split[0] != "www":
                        partial_url = form.cleaned_data['url'].split('//')
                        actual_url = partial_url[0] + "//www." + partial_url[1]
                    else:
                        actual_url = form.cleaned_data['url']
                else:
                    domain_split = form.cleaned_data['url'].split('.')
                    if domain_split[0] != "www":
                        actual_url = "http://www." + form.cleaned_data['url']
                    else:
                        actual_url = "http://" + form.cleaned_data['url']

                contribution.url_domain = get_domain(actual_url)
                contribution.url = actual_url

                try:
                    contribution_same_url = Contribution.objects.get(url=actual_url)
                    return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contribution_same_url.id))
                except Contribution.DoesNotExist:
                    pass

                """try:
                    contribution_url = Contribution.objects.get(url=contribution.url)
                    return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contribution_url.id))
                except Contribution.DoesNotExist:
                    pass """
            else:
                contribution.text = form.cleaned_data['text']
            contribution.save()
            contribution.user_likes.add(request.user)
            contribution.save()

            return HttpResponseRedirect(reverse('empo_news:main_page'))

    context = {
        'form': form
    }
    return render(request, 'empo_news/submit.html', context)


def main_page(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    contributions = Contribution.objects.filter(comment__isnull=True)
    update_show(contributions.order_by('-points'), request.user.id, pg * 30)
    most_points_list = contributions.filter(show=True).order_by('-points')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_points_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_points_list,
        "user": request.user,
        "path": "main_page",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/main_page.html', context)


def new_page(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    contributions = Contribution.objects.filter(comment__isnull=True)
    update_show(contributions.order_by('-publication_time'), request.user.id, pg * 30)
    most_recent_list = contributions.filter(show=True).order_by('-publication_time')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_recent_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_recent_list,
        "user": request.user,
        "path": "new_page",
        "highlight": "new",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/main_page.html', context)


def submitted(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    user_id = request.GET.get('username', "")
    if not User.objects.filter(username=user_id).exists():
        return HttpResponse('No such user')
    base_list = User.objects.get(username=user_id).contribution.filter(comment__isnull=True)

    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('&')[0]
    list_start = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_start = 0

    submitted_list = base_list.order_by('publication_time')[list_start:(pg * 30)]
    more = len(base_list.all()) > (pg * 30)
    for contribution in submitted_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()

    context = {
        "list": submitted_list,
        "user": request.user,
        "mine": (request.user.username == user_id),
        "path": "submitted",
        "submitted_id": user_id,
        "highlight": "submitted",
        "more": more,
        "next_page": base_path + "&pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/submitted.html', context)


def likes_submit(request, view, id, pg, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id)
    if UserFields.objects.filter(user=contribution.user).count() == 0:
        userFields = UserFields(user=contribution.user, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                minaway=180, delay=0)
        userFields.save()
    if contribution.user_likes.filter(id=request.user.id).exists():
        contribution.user_likes.remove(request.user)
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) - 1)
    else:
        contribution.user_likes.add(request.user)
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) + 1)
    contribution.points = contribution.total_likes()
    contribution.save()
    if pg == 1:
        return HttpResponseRedirect(reverse('empo_news:' + view) + '?id=' + id)
    return HttpResponseRedirect(reverse('empo_news:' + view) + '?id=' + id + '&pg=' + str(pg))


def likes(request, view, pg, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id)
    if UserFields.objects.filter(user=contribution.user).count() == 0:
        userFields = UserFields(user=contribution.user, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                minaway=180, delay=0)
        userFields.save()
    if contribution.user_likes.filter(id=request.user.id).exists():
        contribution.user_likes.remove(request.user)
        contribution.points = contribution.points - 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) - 1)
    else:
        contribution.user_likes.add(request.user)
        contribution.points = contribution.points + 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) + 1)
    contribution.points = contribution.total_likes()
    contribution.save()
    if pg == 1:
        return HttpResponseRedirect(reverse('empo_news:' + view))
    return HttpResponseRedirect(reverse('empo_news:' + view) + '?pg=' + str(pg))


def likes_reply(request, contribution_id, comment_id, path):
    comment = get_object_or_404(Comment, id=comment_id)
    if UserFields.objects.filter(user=comment.user).count() == 0:
        userFields = UserFields(user=comment.user, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                minaway=180, delay=0)
        userFields.save()
    if comment.user_likes.filter(id=request.user.id).exists():
        comment.user_likes.remove(request.user)
        comment.points = comment.points - 1
        UserFields.objects.filter(user=comment.user).update(
            karma=getattr(UserFields.objects.filter(user=comment.user).first(), 'karma', 1) - 1)
    else:
        comment.user_likes.add(request.user)
        comment.points = comment.points + 1
        UserFields.objects.filter(user=comment.user).update(
            karma=getattr(UserFields.objects.filter(user=comment.user).first(), 'karma', 1) + 1)
    comment.points = comment.total_likes()
    comment.save()
    if path == "item":
        return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contribution_id) + '#' + str(comment_id))
    return HttpResponseRedirect(reverse('empo_news:addreply') + '?id=' + str(comment_id))


def likes_contribution(request, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id)
    if UserFields.objects.filter(user=contribution.user).count() == 0:
        userFields = UserFields(user=contribution.user, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                minaway=180, delay=0)
        userFields.save()
    if contribution.user_likes.filter(id=request.user.id).exists():
        contribution.user_likes.remove(request.user)
        contribution.points = contribution.points - 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) - 1)
    else:
        contribution.user_likes.add(request.user)
        contribution.points = contribution.points + 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) + 1)
    contribution.points = contribution.total_likes()
    contribution.save()
    return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contribution_id))


def likes_comment(request, comment_id, username):
    contribution = get_object_or_404(Contribution, id=comment_id)
    if UserFields.objects.filter(user=contribution.user).count() == 0:
        userFields = UserFields(user=contribution.user, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                minaway=180, delay=0)
        userFields.save()
    if contribution.user_likes.filter(id=request.user.id).exists():
        contribution.user_likes.remove(request.user)
        contribution.points = contribution.points - 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) - 1)
    else:
        contribution.user_likes.add(request.user)
        contribution.points = contribution.points + 1
        UserFields.objects.filter(user=contribution.user).update(
            karma=getattr(UserFields.objects.filter(user=contribution.user).first(), 'karma', 1) + 1)
    contribution.points = contribution.total_likes()
    contribution.save()
    return HttpResponseRedirect(reverse('empo_news:threads', kwargs={'username': username}))


def hide(request, view, pg, contribution_id):
    hide_for_user(request, contribution_id)
    if pg == 1:
        return HttpResponseRedirect(reverse('empo_news:' + view))
    return HttpResponseRedirect(reverse('empo_news:' + view, args=(pg,)))


def hide_no_page(request, view, contribution_id):
    hide_for_user(request, contribution_id)
    return HttpResponseRedirect(reverse('empo_news:' + view) + "?id=" + str(contribution_id))


def hide_for_user(request, contribution_id):
    contribution = get_object_or_404(Contribution, id=contribution_id)
    if contribution.user_id_hidden.filter(id=request.user.id).exists():
        contribution.user_id_hidden.remove(request.user)
        contribution.hidden = contribution.hidden - 1
    else:
        contribution.user_id_hidden.add(request.user)
        contribution.hidden = contribution.hidden + 1
    contribution.save()


def collapse(request, contribution_id, comment_id):
    hide_for_user(request, comment_id)
    return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contribution_id) + '#' + str(comment_id))


def logout(request):
    do_logout(request)
    return redirect('/')


def profile(request, username):
    karma = 0
    key = ''

    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    user_selected = User.objects.get(username=username)

    if UserFields.objects.filter(user=user_selected).count() == 0:
        user_fields = UserFields(user=user_selected, karma=1, about="", showdead=0, noprocrast=0, maxvisit=20,
                                 minaway=180, delay=0)

        user_fields.save()

        coding_string = get_coding_string(user_selected)
        encoded_string_bytes = base64.b64encode(coding_string.encode("utf-8"))
        key = str(encoded_string_bytes, "utf-8")
        hash_key = APIKeyManager.get_hash_key(key)

        user_fields.api_key = hash_key
        user_fields.save()
    else:
        user_fields = UserFields.objects.get(user=user_selected)
        coding_string = get_coding_string(user_selected)
        encoded_string_bytes = base64.b64encode(coding_string.encode("utf-8"))
        key = str(encoded_string_bytes, "utf-8")
    if not user_fields.showdead:
        posS = '0'
    else:
        posS = '1'

    if not user_fields.noprocrast:
        posN = '0'
    else:
        posN = '1'
    form = UserUpdateForm(
        initial={'email': user_selected.email, 'karma': user_fields.karma, 'about': user_fields.about,
                 'showdead': posS, 'noprocrast': posN, 'maxvisit': user_fields.maxvisit,
                 'minaway': user_fields.minaway, 'delay': user_fields.delay})

    if user_selected == request.user:
        if request.method == 'POST':
            form = UserUpdateForm(request.POST)

            if form.is_valid():
                UserFields.objects.filter(user=request.user).update(user=request.user, about=form.cleaned_data['about'],
                                                                    showdead=form.cleaned_data['showdead'],
                                                                    noprocrast=form.cleaned_data['noprocrast'],
                                                                    maxvisit=int(form.cleaned_data['maxvisit']),
                                                                    minaway=int(form.cleaned_data['minaway']),
                                                                    delay=int(form.cleaned_data['delay']))

                return HttpResponseRedirect(reverse('empo_news:user_page', kwargs={"username": user_selected.username}))
    context = {
        "form": form,
        "userSelected": user_selected,
        "userFields": user_fields,
        "karma": karma,
        "notBottom": True,
        "key": key
    }
    return render(request, 'empo_news/profile.html', context)


def get_coding_string(user_selected):
    coding_string = user_selected.username + user_selected.email
    username_length = len(user_selected.username)
    email_length = len(user_selected.email)
    if username_length > email_length:
        coding_string += str(username_length // email_length)
    else:
        coding_string += str(email_length // username_length)

    return coding_string


def increment_comments_number(contrib):
    contrib.comments += 1
    contrib.save()
    if contrib.parent is not None:
        increment_comments_number(contrib.parent)


def item(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    contrib_id = int(request.GET.get('id', -1))
    if Comment.objects.filter(id=contrib_id).count() > 0:
        contrib = Comment.objects.get(id=contrib_id)
    else:
        contrib = Contribution.objects.get(id=contrib_id)
    contrib_comments = Comment.objects.filter(contribution_id=contrib_id, parent__isnull=True) \
        .order_by('-publication_time')

    context = {
        "contribution": contrib,
        "comment_form": CommentForm(),
        "contrib_comments": contrib_comments,
        "karma": karma,
    }

    if request.method == 'GET':
        try:
            return render(request, 'empo_news/contribution.html', context)
        except Contribution.DoesNotExist:
            return HttpResponse('No such item.')
    elif request.method == 'POST':
        if not request.user.is_authenticated:
            href = "{% url 'social:begin' 'google-oauth2' %}?next={% url 'empo_news:addreply' %}?id={{ comment.id }}"
            return HttpResponseRedirect(
                reverse('social:begin', args={'google-oauth2', }) + '?next=' + reverse('empo_news:item')
                + '?id=' + str(contrib_id))
        comment_form = CommentForm(request.POST)

        if comment_form.is_valid():
            if contrib.get_class() == "Contribution":
                comment = Comment(user=request.user, contribution=contrib,
                                  publication_time=datetime.today(),
                                  text=comment_form.cleaned_data['comment'])
                comment.save()

                contrib.comments += 1
                contrib.save()
            else:
                comment = Comment(user=request.user, contribution=contrib.contribution, parent=contrib,
                                  publication_time=datetime.today(),
                                  text=comment_form.cleaned_data['comment'])
                comment.save()
                increment_comments_number(contrib)
                contrib.contribution.comments += 1
                contrib.contribution.save()

            return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contrib_id))
        else:
            return HttpResponseRedirect(reverse('empo_news:addcomment') + '?id=' + str(contrib_id))

    return HttpResponseRedirect(reverse('empo_news:main_page'))


def add_comment(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    contrib_id = int(request.GET.get('id', -1))
    contrib = Contribution.objects.get(id=contrib_id)
    context = {
        "contribution": contrib,
        "comment_form": CommentForm(),
        "karma": karma,
    }

    if request.method == 'GET':
        try:
            return render(request, 'empo_news/add_comment.html', context)
        except Contribution.DoesNotExist:
            return HttpResponse('No such item.')
    elif request.method == 'POST':
        comment_form = CommentForm(request.POST)

        if comment_form.is_valid():
            comment = Comment(user=request.user, contribution=contrib,
                              publication_time=datetime.today(),
                              text=comment_form.cleaned_data['comment'])
            comment.save()

            contrib.comments += 1
            contrib.save()
            return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(contrib_id))
        else:
            return HttpResponseRedirect(reverse('empo_news:addcomment') + '?id=' + str(contrib_id))

    return HttpResponseRedirect(reverse('empo_news:main_page'))


def update_show(all_contributions, userid, border):
    count_shown = 0
    i = 0
    length = len(all_contributions)
    while count_shown < border and i < length:
        contribution = all_contributions[i]
        if contribution.user_id_hidden.filter(id=userid).exists():
            contribution.show = False
        else:
            contribution.show = True
            count_shown += 1
        contribution.save()
        i += 1


def add_reply(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    comment_id = int(request.GET.get('id', -1))
    comment = Comment.objects.get(id=comment_id)
    context = {
        "comment": comment,
        "comment_form": CommentForm(),
        "karma": karma,
    }

    if request.method == 'GET':
        try:
            return render(request, 'empo_news/add_reply.html', context)
        except Contribution.DoesNotExist:
            return HttpResponse('No such item.')
    elif request.method == 'POST':
        comment_form = CommentForm(request.POST)

        if comment_form.is_valid():
            new_comment = Comment(user=request.user, contribution=comment.contribution, parent=comment,
                                  publication_time=datetime.today(),
                                  text=comment_form.cleaned_data['comment'])
            new_comment.save()

            increment_comments_number(comment)
            comment.contribution.comments += 1
            comment.contribution.save()
            return HttpResponseRedirect(reverse('empo_news:item') + '?id=' + str(new_comment.contribution.id)
                                        + '#' + str(new_comment.parent.id))

    return HttpResponseRedirect(reverse('empo_news:main_page'))


def threads(request, username):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    userSelected = User.objects.get(username=username)
    commentsUser = Comment.objects.filter(user=userSelected)
    context = {
        "userSelected": userSelected,
        "userComments": commentsUser,
        "karma": karma,
        "highlight": "threads",
    }
    return render(request, 'empo_news/user_comments.html', context)


def comments(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    most_recent_list = Comment.objects.all().order_by('-publication_time')[list_base:(pg * 30)]
    more = len(Comment.objects.all()) > (pg * 30)
    for contribution in most_recent_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_recent_list,
        "user": request.user,
        "path": "comments",
        "highlight": "comments",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/comments.html', context)


def ask_list(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    contributions = Contribution.objects.filter(comment__isnull=True, url__isnull=True)
    update_show(contributions.order_by('-points'), request.user.id, pg * 30)
    most_points_list = contributions.filter(show=True).order_by('-points')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_points_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_points_list,
        "user": request.user,
        "path": "ask_list",
        "highlight": "ask",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/main_page.html', context)


def show_list(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    contributions = Contribution.objects.filter(comment__isnull=True, title__startswith='Show EN: ')
    update_show(contributions.order_by('-points'), request.user.id, pg * 30)
    most_points_list = contributions.filter(show=True).order_by('-points')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_points_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_points_list,
        "user": request.user,
        "path": "show_list",
        "highlight": "show",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/main_page.html', context)


def update_show_hidden(all_contributions, userid, border):
    count_shown = 0
    i = 0
    length = len(all_contributions)
    while count_shown < border and i < length:
        contribution = all_contributions[i]
        if contribution.user_id_hidden.filter(id=userid).exists():
            contribution.show = True
            count_shown += 1
        else:
            contribution.show = False
        contribution.save()
        i += 1


def hidden(request, userid):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    selectedUser = User.objects.filter(id=userid).first()
    contributions = Contribution.objects.filter(comment__isnull=True)
    update_show_hidden(contributions.order_by('-points'), userid, pg * 30)
    most_points_list = contributions.filter(show=True).order_by('-points')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_points_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_points_list,
        "user": request.user,
        "path": "hidden",
        "highlight": "hidden",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
        "selectedUser": selectedUser,
    }
    return render(request, 'empo_news/main_page.html', context)


def unhide(request, view, pg, contribution_id, userid):
    contribution = get_object_or_404(Contribution, id=contribution_id)
    if contribution.user_id_hidden.filter(id=request.user.id).exists():
        contribution.user_id_hidden.remove(request.user)
        contribution.hidden = contribution.hidden - 1
    else:
        contribution.user_id_hidden.add(request.user)
        contribution.hidden = contribution.hidden + 1
    contribution.save()
    if pg == 1:
        return HttpResponseRedirect(reverse('empo_news:' + view, kwargs={'userid': userid}))
    return HttpResponseRedirect(reverse('empo_news:' + view, args=(pg,), kwargs={'userid': userid}, ))


def voted_submissions(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    contributions = Contribution.objects.filter(comment__isnull=True,
                                                user_likes__username__contains=request.user.username).exclude(
        user=request.user)
    update_show(contributions.order_by('-points'), request.user.id, pg * 30)
    most_points_list = contributions.filter(show=True).order_by('-points')[list_base:(pg * 30)]
    more = len(contributions.filter(show=True)) > (pg * 30)
    for contribution in most_points_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_points_list,
        "user": request.user,
        "path": "voted_submissions",
        "highlight": "voted_submissions",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/main_page.html', context)


def voted_comments(request):
    karma = 0
    if request.user.is_authenticated:
        karma = getattr(UserFields.objects.filter(user=request.user).first(), 'karma', 1)
    pg = int(request.GET.get('pg', 1))
    base_path = request.get_full_path().split('?')[0]
    list_base = ((pg - 1) * 30) + 1
    if pg < 1:
        return HttpResponseRedirect(base_path)
    elif pg == 1:
        list_base = 0

    comments = Comment.objects.filter(user_likes__username__contains=request.user.username).exclude(user=request.user)
    most_recent_list = comments.order_by('-publication_time')[list_base:(pg * 30)]
    more = len(comments) > (pg * 30)
    for contribution in most_recent_list:
        contribution.liked = not contribution.user_likes.filter(id=request.user.id).exists()
        contribution.save()
    context = {
        "list": most_recent_list,
        "user": request.user,
        "path": "voted_comments",
        "highlight": "voted_comments",
        "more": more,
        "next_page": base_path + "?pg=" + str(pg + 1),
        "page_value": pg,
        "base_loop_count": (pg - 1) * 30,
        "karma": karma,
    }
    return render(request, 'empo_news/comments.html', context)


def is_url_valid(url):
    return '.' in url


class ContributionsViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        contributions = Contribution.objects.filter(comment__isnull=True)
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_fields = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        username_filter = self.request.query_params.get('username', '')
        exclude_user_filter = self.request.query_params.get('exclude_user', '')
        show_en_filter = self.request.query_params.get('showEn', '')
        url_filter = self.request.query_params.get('url', '')
        ask_filter = self.request.query_params.get('ask', '')
        order_by_filter = self.request.query_params.get('orderBy', '')
        liked_filter = self.request.query_params.get('liked', '')
        hidden_filter = self.request.query_params.get('hidden', '')

        if (url_filter and ask_filter) or (username_filter and exclude_user_filter):
            raise InvalidQueryParametersException

        if username_filter:
            try:
                User.objects.get(username=username_filter)
            except User.DoesNotExist:
                raise NotFoundException
            contributions = contributions.filter(user__username=username_filter)

        if exclude_user_filter:
            try:
                User.objects.get(username=exclude_user_filter)
            except User.DoesNotExist:
                raise NotFoundException
            user_contributions = contributions.filter(user__username=exclude_user_filter)
            contributions = contributions.difference(user_contributions)

        if show_en_filter:
            contributions = contributions.filter(title__startswith="Show EN:")

        if url_filter:
            contributions = contributions.filter(url=url_filter)

        if ask_filter:
            contributions = contributions.filter(url__isnull=True)

        if order_by_filter:
            if order_by_filter == 'publication_time_asc':
                contributions = contributions.order_by('publication_time__year', 'publication_time__month',
                                                       'publication_time__day', 'publication_time__hour',
                                                       'publication_time__minute', 'publication_time__second')
            elif order_by_filter == 'publication_time_desc':
                contributions = contributions.order_by('-publication_time__year', '-publication_time__month',
                                                       '-publication_time__day', '-publication_time__hour',
                                                       '-publication_time__minute', '-publication_time__second')
            elif order_by_filter == 'title_asc':
                contributions = contributions.order_by('title')
            elif order_by_filter == 'title_desc':
                contributions = contributions.order_by('-title')
            elif order_by_filter == 'votes_asc':
                contributions = contributions.order_by('points')
            else:
                contributions = contributions.order_by('-points')

        contribution_list = []

        for contrib in contributions:
            contribution_map = get_basic_attributes_map(contrib, user_fields)
            adding = True

            if liked_filter or hidden_filter:
                adding = False

                if liked_filter and hidden_filter:
                    liked_result = liked_filter == 'true'
                    hidden_result = hidden_filter == 'true'

                    if liked_result and hidden_result and contribution_map['liked'] \
                            and not contribution_map['show']:
                        adding = True
                    elif not liked_result and hidden_result and not contribution_map['liked'] \
                            and not contribution_map['show']:
                        adding = True
                    elif liked_result and not hidden_result and contribution_map['liked'] \
                            and contribution_map['show']:
                        adding = True
                    elif not liked_result and not hidden_result and not contribution_map['liked'] \
                            and contribution_map['show']:
                        adding = True
                else:
                    if liked_filter and ((liked_filter == 'true' and contribution_map['liked'])
                                         or (liked_filter == 'false' and not contribution_map['liked'])):
                        adding = True
                    elif (hidden_filter == 'true' and not contribution_map['show']) \
                            or (hidden_filter == 'false' and contribution_map['show']):
                        adding = True

            if adding:
                contribution_list.append(contribution_map)

        return Response(contribution_list, status=status.HTTP_200_OK)

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def create_contribution(self, request, *args, **kwargs):
        title = self.request.data.get('title', '')
        url = self.request.data.get('url', '')
        text = self.request.data.get('text', '')
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        if len(title) > 80:
            raise TitleIsTooLongException

        if len(url) > 500:
            raise UrlIsTooLongException

        if url and text and is_url_valid(url):
            raise UrlAndTextFieldException

        domain = None

        if url:
            url_split = url.split('/')
            if url_split[0] == "http:" or url_split[0] == "https:":
                domain_split = url_split[2].split('.')
                if domain_split[0] != "www":
                    partial_url = url.split('//')
                    actual_url = partial_url[0] + "//www." + partial_url[1]
                else:
                    actual_url = url
            else:
                domain_split = url.split('.')
                if domain_split[0] != "www":
                    actual_url = "http://www." + url
                else:
                    actual_url = "http://" + url

            domain = get_domain(actual_url)

            try:
                actual_contribution = Contribution.objects.get(url=actual_url)
                return Response(get_basic_attributes_map(actual_contribution, user_field), status=status.HTTP_200_OK)
            except Contribution.DoesNotExist:
                contribution = Contribution(user=user_field.user, title=title, publication_time=datetime.today(),
                                            liked=True, show=True, url=actual_url, text=None)
                contribution.save()
        else:
            contribution = Contribution(user=user_field.user, title=title, publication_time=datetime.today(),
                                        liked=True, show=True, url=None, text=text)
            contribution.save()

        user_contributions = Contribution.objects.filter(user=user_field.user).order_by('-publication_time')
        contribution = user_contributions[0]

        contribution.user_likes.add(user_field.user)
        contribution.url_domain = domain
        contribution.save()

        return Response(get_basic_attributes_map(contribution, user_field), status=status.HTTP_201_CREATED)

    def get_serializer_class(self):
        if self.action == 'create':
            url = self.request.data.get('url', '')
            text = self.request.data.get('text', '')

            if url and is_url_valid(url):
                return UrlContributionSerializer
            elif text:
                return AskContributionSerializer

        return ContributionSerializer


class ContributionsIdViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    serializer_class = ContributionSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_fields = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        contribution_map = get_basic_attributes_map(contribution, user_fields)
        return Response(contribution_map, status=status.HTTP_200_OK)

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def delete_actual(self, request, *args, **kwargs):
        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        user = UserFields.objects.get(user_id=contribution.user.id)
        key = request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        if str(user.api_key) != str(api_key):
            raise ForbiddenException

        contribution.delete()

        if contribution.get_class() == 'Comment':
            contribution.contribution.points -= 1
            contribution.save()

        message = {'status': 204, 'message': 'Deleted'}
        return Response(message, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def update_actual(self, request, *args, **kwargs):
        title = self.request.query_params.get('title', '')
        text = self.request.query_params.get('text', '')
        key = self.request.META.get('HTTP_API_KEY', '')

        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        if len(title) > 80:
            raise TitleIsTooLongException

        contribution = Contribution.objects.get(id=kwargs.get('id'))

        if contribution.user != user_field.user:
            raise ForbiddenException

        if contribution.url is not None and text != '':
            raise UrlCannotBeModifiedException

        contribution.title = title
        contribution.text = text
        contribution.save()

        contribution_map = get_basic_attributes_map(contribution, user_field)
        return Response(contribution_map, status=status.HTTP_200_OK)


class VoteIdViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    serializer_class = ContributionSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def vote(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        for user_like in contribution.user_likes.all():
            if str(user_field.user.username) == str(user_like):
                raise ConflictException

        contribution.user_likes.add(user_field.user.id)
        contribution.points += 1
        contribution.save()

        response = {'status': 204, 'message': 'OK'}
        return Response(response, status=status.HTTP_204_NO_CONTENT)


class UnVoteIdViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    serializer_class = ContributionSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def unvote(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        if user_field.user == contribution.user:
            raise ContributionUserException

        found = False
        user_likes = contribution.user_likes.all()
        actual = 0

        while (not found and actual < len(user_likes)):
            found = str(user_likes[actual]) == str(user_field.user.username)
            actual += 1

        if not found:
            raise ConflictException

        contribution.user_likes.remove(user_field.user.id)
        contribution.points -= 1
        contribution.save()

        response = {'status': 204, 'message': 'OK'}
        return Response(response, status=status.HTTP_204_NO_CONTENT)


def show_childs(comment):
    comment.show = True
    comment.save()

    for child_comment in comment.comment_set.all():
        hide_childs(child_comment)


def hide_childs(comment):
    comment.show = False
    comment.save()

    for child_comment in comment.comment_set.all():
        hide_childs(child_comment)

class HideIdViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    serializer_class = ContributionSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def hide(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        for user_hidden in contribution.user_id_hidden.all():
            if str(user_field.user.username) == str(user_hidden):
                raise ConflictException

        contribution.user_id_hidden.add(user_field.user.id)
        contribution.hidden += 1
        contribution.save()

        try:
            comment = Comment.objects.get(id=contribution.id)
            hide_childs(comment)
        except Comment.DoesNotExist:
            pass

        response = {'status': 204, 'message': 'OK'}
        return Response(response, status=status.HTTP_204_NO_CONTENT)


class UnHideIdViewSet(viewsets.ModelViewSet):
    queryset = Contribution.objects.filter(comment__isnull=True)
    serializer_class = ContributionSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def unhide(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            contribution = Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        found = False
        user_hides = contribution.user_id_hidden.all()
        actual = 0

        while not found and actual < len(user_hides):
            found = str(user_hides[actual]) == str(user_field.user.username)
            actual += 1

        if not found:
            raise ConflictException

        contribution.user_id_hidden.remove(user_field.user.id)
        contribution.hidden -= 1
        contribution.save()

        try:
            comment = Comment.objects.get(id=contribution.id)
            show_childs(comment)
        except Comment.DoesNotExist:
            pass

        response = {'status': 204, 'message': 'OK'}
        return Response(response, status=status.HTTP_204_NO_CONTENT)


class CommentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        username_filter = self.request.query_params.get('username', '')
        exclude_user_filter = self.request.query_params.get('exclude_user', '')
        order_by_filter = self.request.query_params.get('orderBy', '')
        liked_filter = self.request.query_params.get('liked', '')
        hidden_filter = self.request.query_params.get('hidden', '')
        selected_comments = Comment.objects.all()

        if username_filter:
            try:
                user = User.objects.get(username=username_filter)
            except User.DoesNotExist:
                raise NotFoundException
            selected_comments = selected_comments.filter(user_id=user.id)

        if exclude_user_filter:
            try:
                User.objects.get(username=exclude_user_filter)
            except User.DoesNotExist:
                raise NotFoundException
            user_comments = selected_comments.filter(user__username=exclude_user_filter)
            selected_comments = selected_comments.difference(user_comments)

        if order_by_filter:
            if order_by_filter == 'publication_time_asc':
                selected_comments = selected_comments.order_by('publication_time')
            elif order_by_filter == 'publication_time_desc':
                selected_comments = selected_comments.order_by('-publication_time')
            elif order_by_filter == 'votes_asc':
                selected_comments = selected_comments.order_by('points')
            else:
                selected_comments = selected_comments.order_by('-points')

        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        comment_list = []

        for comment in selected_comments:
            comment_map = get_basic_attributes_map(comment, user_field)
            comment_map["contribution"] = comment.contribution.id
            comment_map["contribution_title"] = comment.contribution.title

            if comment.parent is not None:
                comment_map["parent"] = comment.parent.id

            adding = True

            if liked_filter or hidden_filter:
                adding = False

                if liked_filter and hidden_filter:
                    liked_result = liked_filter == 'true'
                    hidden_result = hidden_filter == 'true'

                    if liked_result and hidden_result and comment_map['liked'] \
                            and not comment_map['show']:
                        adding = True
                    elif not liked_result and hidden_result and not comment_map['liked'] \
                            and not comment_map['show']:
                        adding = True
                    elif liked_result and not hidden_result and comment_map['liked'] \
                            and comment_map['show']:
                        adding = True
                    elif not liked_result and not hidden_result and not comment_map['liked'] \
                            and comment_map['show']:
                        adding = True
                else:
                    if liked_filter and ((liked_filter == 'true' and comment_map['liked'])
                                         or (liked_filter == 'false' and not comment_map['liked'])):
                        adding = True
                    elif (hidden_filter == 'true' and not comment_map['show']) \
                            or (hidden_filter == 'false' and comment_map['show']):
                        adding = True

            if adding:
                comment_list.append(comment_map)

        return Response(comment_list)


class CommentIdViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        try:
            comment = Comment.objects.get(id=kwargs.get('commentId'))
        except Comment.DoesNotExist:
            raise NotFoundException

        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        comment_map = get_basic_attributes_map(comment, user_field)
        comment_map["contribution"] = comment.contribution.id
        comment_map["contribution_title"] = comment.contribution.title

        if comment.parent is not None:
            comment_map["parent"] = comment.parent.id

        return Response(comment_map)


def is_liked_by_user(contribution, user_id):
    try:
        contribution.user_likes.get(id=user_id)
        return True
    except User.DoesNotExist:
        return False


def is_shown_by_user(contribution, user_id):
    try:
        contribution.user_id_hidden.get(id=user_id)
        return False
    except User.DoesNotExist:
        return True


def get_basic_attributes_map(contribution, user_fields):
    dataMap = {
        'id': contribution.id,
        'title': contribution.title,
        'points': contribution.points,
        'publication_time': contribution.publication_time,
        'url': contribution.url,
        'text': contribution.text,
        'comments': contribution.comments,
        'user_id': contribution.user.username,
        'hidden': contribution.hidden,
        'liked': is_liked_by_user(contribution, user_fields.user.id),
        'show': is_shown_by_user(contribution, user_fields.user.id)
    }

    return dataMap


def apply_filters(comments_list, username_filter, order_by_filter):
    if username_filter:
        try:
            user = User.objects.get(username=username_filter)
        except User.DoesNotExist:
            raise NotFoundException
        comments_list = comments_list.filter(user_id=user.id)

    if order_by_filter:
        if order_by_filter == 'publication_time_asc':
            comments_list = comments_list.order_by('publication_time')
        elif order_by_filter == 'publication_time_desc':
            comments_list = comments_list.order_by('-publication_time')
        elif order_by_filter == 'votes_asc':
            comments_list = comments_list.order_by('points')
        else:
            comments_list = comments_list.order_by('-points')


def get_comment_map(comment, user_fields, username_filter, order_by_filter):
    comment_map = get_basic_attributes_map(comment, user_fields)
    comment_map["contribution_title"] = comment.contribution.title

    child_comment_list = []

    actual_comments = comment.comment_set.all()
    apply_filters(actual_comments, username_filter, order_by_filter)

    for child_comment in actual_comments:
        child_comment_list.append(get_comment_map(child_comment, user_fields, username_filter, order_by_filter))

    comment_map["comments_list"] = child_comment_list
    return comment_map


class ContributionCommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            Contribution.objects.get(id=kwargs.get('id'))
        except Contribution.DoesNotExist:
            raise NotFoundException

        contribution = Contribution.objects.get(id=kwargs.get('id'))
        contribution_map = get_basic_attributes_map(contribution, user_field)
        contribution_first_comments = Comment.objects.filter(contribution_id=kwargs.get('id'),
                                                             parent__isnull=True)

        username_filter = self.request.query_params.get('username', '')
        order_by_filter = self.request.query_params.get('orderBy', '')
        apply_filters(contribution_first_comments, username_filter, order_by_filter)

        comment_list = []
        for comment in contribution_first_comments:
            comment_list.append(get_comment_map(comment, user_field, username_filter, order_by_filter))

        contribution_map["comments_list"] = comment_list

        # return Response(CommentSerializer(contribution_comments, many=True).data)
        return Response(contribution_map)

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def create_comment(self, request, *args, **kwargs):
        text = self.request.data.get('text', '')
        parent_id = kwargs.get('id', '')
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_field = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        try:
            comment = Comment.objects.get(id=parent_id)
            contribution = comment.contribution
            contribution.comments += 1
            contribution.save()
            comment.comments += 1
            comment.save()

            parent = comment.parent
            while parent is not None:
                parent.comments += 1
                parent.save()
                parent = parent.parent
        except Comment.DoesNotExist:
            try:
                comment = None
                contribution = Contribution.objects.get(id=parent_id)
                contribution.comments += 1
                contribution.save()
            except Contribution.DoesNotExist:
                raise NotFoundException

        if (comment is None and contribution.user.id == user_field.user.id) \
                or (comment is not None and comment.user.id == user_field.user.id):
            raise ContributionUserException

        comment = Comment(user=user_field.user, title='', points=1, publication_time=datetime.today(),
                          comments=0, liked=True, show=True, url=None, text=text, contribution=contribution,
                          parent=comment)
        comment.save()
        comment.user_likes.add(user_field.user)
        comment.save()

        comment_map = get_basic_attributes_map(comment, user_field)
        comment_map["contribution"] = comment.contribution.id
        comment_map["contribution_title"] = comment.contribution.title

        if comment.parent is not None:
            comment_map["parent"] = comment.parent.id

        return Response(comment_map, status=status.HTTP_201_CREATED)


class ProfilesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserFields.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, methods=['put'], renderer_classes=[renderers.StaticHTMLRenderer])
    def update_actual(self, request, *args, **kwargs):
        about = self.request.query_params.get('about', '')
        email = self.request.query_params.get('email', '')
        showdead = self.request.query_params.get('showdead', '')
        noprocrast = self.request.query_params.get('noprocrast', '')
        maxvisit = self.request.query_params.get('maxvisit', '')
        minaway = self.request.query_params.get('minaway', '')
        delay = self.request.query_params.get('delay', '')

        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user_fields = UserFields.objects.get(api_key=api_key)
        except UserFields.DoesNotExist:
            raise UnauthenticatedException

        if about:
            user_fields.about = about

        if email:
            user_fields.email = email

        if showdead:
            user_fields.showdead = showdead == "true"

        if noprocrast:
            user_fields.noprocrast = noprocrast == "true"

        if maxvisit:
            user_fields.maxvisit = maxvisit

        if minaway:
            user_fields.minaway = minaway

        if delay:
            user_fields.delay = delay

        user_fields.save()

        return Response(UserFieldsSerializer(user_fields).data)


class ProfilesIdViewSet(viewsets.ModelViewSet):
    queryset = UserFields.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [KeyPermission]

    @action(detail=True, renderer_classes=[renderers.StaticHTMLRenderer])
    def get_actual(self, request, *args, **kwargs):
        key = self.request.META.get('HTTP_API_KEY', '')
        api_key = APIKeyManager.get_hash_key(key)

        try:
            user = User.objects.get(username=kwargs.get('username'))
        except User.DoesNotExist:
            raise NotFoundException

        user_fields = UserFields.objects.get(user_id=user.id)

        if str(user_fields.api_key) != str(api_key):
            data = {'username': user.username,
                    'date_joined': user.date_joined,
                    'karma': user_fields.karma,
                    'about': user_fields.about}
            return Response(data)

        return Response(UserFieldsSerializer(user_fields).data)
