# from django.conf import settings
# from django.contrib.auth.models import User
# from django.core.mail import send_mail
# from django.urls import reverse


# Metaclasses:


class StaticClass(type):
    def __call__(cls):
        raise TypeError(
            "'{0}' static class is not callable.".format(cls.__qualname__))


class Singleton(type):

    __instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        # else:
        #     cls._instances[cls].__init__(*args, **kwargs)
        return cls.__instances[cls]


# Methods:


# def send_validation_mail(request, reg):
#
#     from_email = 'idgo@neogeo-technologies.fr'
#     subject = 'Validation de votre inscription sur le site IDGO'
#     message = '''
# Bonjour {first_name} {last_name} ({username}),
#
# Pour valider votre inscription, veuillez cliquer sur le lien suivant : {url}
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(
#         first_name=reg.user.first_name,
#         last_name=reg.user.last_name,
#         username=reg.user.username,
#         url=request.build_absolute_uri(
#             reverse('profiles:confirmation_mail',
#                     kwargs={'key': reg.activation_key})))
#
#     send_mail(subject=subject, message=message,
#               from_email=from_email, recipient_list=[reg.user.email])
#
#
# def send_confirmation_mail(first_name, last_name, username, email):
#     # TODO a remplacer par model Mail.confirmation_user_mail
#     from_email = settings.DEFAULT_FROM_EMAIL
#     subject = 'Confirmation de votre inscription sur le site IDGO'
#     message = '''
# Bonjour {first_name} {last_name} ({username}),
#
# Nous confirmons votre inscription sur le site IDGO.
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(
#         first_name=first_name, last_name=last_name, username=username)
#
#     send_mail(subject=subject, message=message,
#               from_email=from_email, recipient_list=[email])
#
#
# def send_affiliate_request(request, reg):
#     # TODO a remplacer par model Mail.affiliate_request_to_administrators_with_new_org
#     # TODO a remplacer par model Mail.affiliate_request_to_administrators_with_old_org
#     from_email = settings.DEFAULT_FROM_EMAIL
#     subject = 'Un utilisateur demande son rattachement à une organisation'
#
#     if reg.profile_fields['is_new_orga']:
#         message = '''
# Bonjour,
#
# Un nouvel utilisateur ({username}, {user_mail}) demande le rattachement
# à l'organisation qu'il a également créée:
#
# Veuillez vérifier les données renseignées avant de valider son inscription:
# *   Nom de l'organisation : {organisation_name}
# *   Adresse URL de l'organisation : {website}
#
# Veuillez cliquer sur le lien suivant afin de valider son inscription, la
# création de la nouvelle organisation et pour activer son compte : {url}
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(
#             username=reg.user.username,
#             user_mail=reg.user.email,
#             organisation_name=reg.profile_fields['organisation'],
#             website=reg.profile_fields['new_website'],
#             url=request.build_absolute_uri(
#                 reverse('profiles:activation_admin',
#                         kwargs={'key': reg.affiliate_orga_key})))
#
#     else:
#         message = '''
# Bonjour,
#
# Un nouvel utilisateur ({username}, {user_mail}) demande le rattachement à
# l'organisation : {organisation_name}.
#
# Veuillez cliquer sur ce lien afin de valider son inscription
# et activer son compte : {url}
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(
#             username=reg.user.username,
#             user_mail=reg.user.email,
#             organisation_name=reg.profile_fields['organisation'],
#             url=request.build_absolute_uri(
#                 reverse('profiles:activation_admin',
#                         kwargs={'key': reg.affiliate_orga_key})))
#
#     send_mail(
#         subject=subject, message=message, from_email=from_email,
#         recipient_list=[usr.email for usr
#                         in User.objects.filter(is_staff=True, is_active=True)])
#
#
# def send_affiliate_confirmation(profile):
#     # TODO a remplacer par model Mail.affiliate_confirmation_to_user
#     from_email = settings.DEFAULT_FROM_EMAIL
#     subject = 'Confirmation de votre rattachement organisation'
#     message = '''
# Bonjour,
#
# Votre demande de rattachement à l'organisation {organisation} a été validée.
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(organisation=profile.organisation.name)
#
#     send_mail(subject=subject, message=message,
#               from_email=from_email, recipient_list=[profile.user.email])
#
#
# def send_publish_request(request, publish_request):
#     # TODO a remplacer par model Mail.publish_request_to_administrators
#     from_email = settings.DEFAULT_FROM_EMAIL
#     subject = ('Un utilisateur requiert un statut de'
#                'contributeur pour une organisation')
#     message = '''
# Bonjour,
#
# Un nouvel utilisateur ({username}, {mail}) a fait une demande
# de contribution pour l'organisation {organisation}.
#
# Veuillez cliquer sur le lien suivant pour valider sa demande : {url}
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(
#         username=publish_request.user.username,
#         mail=publish_request.user.email,
#         organisation=publish_request.organisation.name,
#         url=request.build_absolute_uri(
#             reverse('profiles:publish_request_confirme',
#                     kwargs={'key': publish_request.pub_req_key})))
#
#     send_mail(
#         subject=subject, message=message, from_email=from_email,
#         recipient_list=[usr.email for usr
#                         in User.objects.filter(is_staff=True, is_active=True)])
#
#
# def send_publish_confirmation(publish_request):
#     # TODO a remplacer par model Mail.publish_confirmation_to_user
#     # TODO: replace w/ "publish_request.organisation.email"
#     from_email = settings.DEFAULT_FROM_EMAIL
#     subject = ('Confirmation de votre inscription en tant'
#                'que contributeur pour une organisation')
#     message = '''
# Bonjour,
#
# Votre demande de contribution pour l'organisation {organisation} a été validé.
#
# Ceci est un message automatique. Merci de ne pas y répondre.
# '''.format(organisation=publish_request.organisation.name)
#
#     send_mail(subject=subject, message=message, from_email=from_email,
#               recipient_list=[publish_request.user.email])
