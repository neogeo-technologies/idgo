from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Profile
from idgo_admin.models import Resource


def render_with_info_profile(request, template_name, context=None,
                             content_type=None, status=None, using=None):

    user = request.user

    profile = get_object_or_404(Profile, user=user)

    if not context:
        context = {}

    organization = (profile.organisation and profile.membership) and profile.organisation

    try:
        action = AccountActions.objects.get(
            action='confirm_rattachement', profile=profile, closed__isnull=True)
    except Exception:
        awaiting_rattachement = None
    else:
        awaiting_rattachement = action.org_extras and action.org_extras.name

    contributions = \
        [[c.id, c.name] for c
            in LiaisonsContributeurs.get_contribs(profile=profile)]
    awaiting_contributions = \
        [[c.id, c.name] for c
            in LiaisonsContributeurs.get_pending(profile=profile)]
    subordinates = \
        [[c.id, c.name] for c
            in LiaisonsReferents.get_subordinates(profile=profile)]
    awaiting_subordinates = \
        [[c.id, c.name] for c
            in LiaisonsReferents.get_pending(profile=profile)]

    context.update({
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_membership': profile.membership,
        'is_referent': profile.referents.exists(),  # TODO: faire une methode
        'is_contributor': profile.contributions.exists(),   # TODO: faire une methode
        'is_admin': profile.is_admin,
        'organization': organization and organization.name,
        'organization_id': organization and organization.id,
        'awaiting_rattachement': awaiting_rattachement,
        'contributions': contributions,
        'awaiting_contributions': awaiting_contributions,
        'subordinates': subordinates,
        'awaiting_subordinates': awaiting_subordinates})

    return render(request, template_name, context=context,
                  content_type=content_type, status=status, using=using)


def get_object_or_404_extended(MyModel, user, include):
    res = None
    profile = get_object_or_404(Profile, user=user)
    instance = get_object_or_404(MyModel, **include)
    i_am_resource = (MyModel.__name__ == Resource.__name__)
    is_referent = instance.dataset.is_referent(profile) if i_am_resource else instance.is_referent(profile)
    is_editor = instance.dataset.editor == user if i_am_resource else instance.editor == user
    if profile.is_admin or is_referent or is_editor:
        res = instance


    # if MyModel.__name__ == Dataset.__name__:
    #     dataset = get_object_or_404(Dataset, **include)
    #     if profile.is_admin:
    #         res = dataset
    #     elif dataset.is_referent(profile):
    #         res = dataset
    #     # Si on veut donner acces aux contributeur
    #     # elif dataset.is_contributor(profile):
    #     #     res = dataset
    #     elif dataset.editor == user:
    #         res = dataset
    #
    # if MyModel.__name__ == Resource.__name__:
    #     resource = get_object_or_404(Resource, **include)
    #     if profile.is_admin:
    #         res = resource
    #     elif resource.dataset.is_referent(profile):
    #         res = resource
    #     # Si on veut donner acces aux contributeur
    #     # elif resource.dataset.is_contributor(profile):
    #     #     res = resource
    #     elif resource.dataset.editor == user:
    #         res = resource

    if not res:
        raise Http404('No %s matches the given query.' % MyModel.__name__)
    return res
