from django.shortcuts import get_object_or_404
from django.shortcuts import render
from idgo_admin.models import LiaisonsContributeurs
from idgo_admin.models import Profile


def render_with_info_profile(request, template_name, context=None,
                             content_type=None, status=None, using=None):

    user = request.user
    profile = get_object_or_404(Profile, user=user)

    if not context:
        context = {}

    context.update({
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_membership': profile.membership,
        'is_referent': profile.referents.exists(),
        'is_contributor': profile.contributions.exists(),
        'is_admin': profile.is_admin,
        'organization': (profile.membership) and profile.organisation.name,
        'contributions': None,
        'awaiting_contributions': [c.name for c in LiaisonsContributeurs.get_pending(profile=profile)]})

    return render(request, template_name, context=context,
                  content_type=content_type, status=status, using=using)
