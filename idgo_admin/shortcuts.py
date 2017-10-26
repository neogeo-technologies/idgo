from django.shortcuts import get_object_or_404
from django.shortcuts import render
from idgo_admin.models import AccountActions
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import LiaisonsReferents
from idgo_admin.models import Profile


def render_with_info_profile(request, template_name, context=None,
                             content_type=None, status=None, using=None):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    if not context:
        context = {}

    organization = (profile.organisation and profile.membership) and profile.organisation.name

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
        'is_referent': profile.referents.exists(),
        'is_contributor': profile.contributions.exists(),
        'is_admin': profile.is_admin,
        'organization': organization,
        'awaiting_rattachement': awaiting_rattachement,
        'contributions': contributions,
        'awaiting_contributions': awaiting_contributions,
        'subordinates': subordinates,
        'awaiting_subordinates': awaiting_subordinates})

    return render(request, template_name, context=context,
                  content_type=content_type, status=status, using=using)
