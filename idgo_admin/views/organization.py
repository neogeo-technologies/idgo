from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from idgo_admin.exceptions import ExceptionsHandler
from idgo_admin.exceptions import ProfileHttp404
from idgo_admin.forms.organization import OrganizationForm as Form
from idgo_admin.models import Dataset
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Organisation
from idgo_admin.models import Profile
from idgo_admin.shortcuts import on_profile_http404
from idgo_admin.shortcuts import render_with_info_profile
from idgo_admin.shortcuts import user_and_profile


decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


@method_decorator(decorators, name='dispatch')
class ThisOrganisation(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id):
        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id, is_active=True)
        data = {
            'id': instance.id,
            'name': instance.name,
            # 'logo': instance.logo and instance.logo.url,
            'type': instance.organisation_type,
            'jurisdiction':
                instance.jurisdiction and instance.jurisdiction.name or '',
            'address': instance.address,
            'postcode': instance.postcode,
            'city': instance.city,
            'phone': instance.org_phone,
            'website': instance.website,
            'email': instance.email,
            'description': instance.description,
            'members': [{
                'username': item.user.username,
                'full_name': item.user.get_full_name(),
                'is_member': item.organisation.id == id and True or False,
                'is_contributor': LiaisonsContributeurs.objects.filter(
                    profile=item, organisation__id=id) and True or False,
                'is_referent': LiaisonsReferents.objects.filter(
                    profile=item, organisation__id=id) and True or False,
                'datasets_count': len(Dataset.objects.filter(organisation=id, editor=item.user)),
                'profile_id': profile.id
                } for item in Profile.objects.filter(
                    Q(organisation=id),
                    Q(liaisonscontributeurs__organisation=id),
                    Q(liaisonsreferents__organisation=id))]}

        return JsonResponse(data=data, safe=False)


@method_decorator(decorators, name='dispatch')
class CreateOrganisation(View):

    template = 'idgo_admin/editorganization.html'
    namespace = 'idgo_admin:edit_organization'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request):
        user, profile = user_and_profile(request)

        context = {'form': Form(include={'user': user})}

        return render_with_info_profile(
            request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request):
        user, profile = user_and_profile(request)

        form = Form(request.POST, request.FILES,
                    include={'user': user})

        if not form.is_valid():
            raise Exception

        context = {'form': form}

        form.handle_me(request)

        return render_with_info_profile(request, self.template, context=context)

@method_decorator(decorators, name='dispatch')
class EditThisOrganisation(View):

    template = 'idgo_admin/editorganization.html'
    namespace = 'idgo_admin:edit_organization'

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, id):
        user, profile = user_and_profile(request)

        context = {
            'id': id,
            'form': Form(
                instance=get_object_or_404(Organisation, id=id),
                include={'user': user, 'id': id})}

        return render_with_info_profile(
            request, self.template, context=context)

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def post(self, request, id):
        user, profile = user_and_profile(request)

        instance = get_object_or_404(Organisation, id=id)

        form = Form(request.POST, request.FILES,
                    instance=instance, include={'user': user, 'id': id})

        if not form.is_valid():
            raise Exception

        context = {'id': id, 'form': form}

        form.handle_me(request, id=id)

        return render_with_info_profile(request, self.template, context=context)


@method_decorator(decorators, name='dispatch')
class AllOrganisations(View):

    @ExceptionsHandler(ignore=[Http404], actions={ProfileHttp404: on_profile_http404})
    def get(self, request, *args, **kwargs):
        user, profile = user_and_profile(request)

        organizations = [{
            'pk': item.pk,
            'name': item.name,
            'rattachement': item == profile.organisation,
            'contributeur': item in Organisation.objects.filter(liaisonscontributeurs__profile=profile),
            'subordinates': item in Organisation.objects.filter(liaisonsreferents__profile=profile),
            } for item in Organisation.objects.all()]

        return render_with_info_profile(
            request, 'idgo_admin/all_organizations.html',
            context={'organizations': organizations})
