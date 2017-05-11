from django.conf.urls import url

from profiles.views import add_user, activation, delete_user, update_user, login
                           # update_user
                           # delete_user_id, delete_user,
                           # register,
                           # activation, new_activation_link

urlpatterns = [
    url(r"^login/?$", login, name="login"),
    url(r"^add/?$", add_user, name="add_user"),
    url(r"^activate/(?P<key>.+)/?$", activation,  name="activation"),
    url(r"^update_user/?$", update_user, name="update_user"),
    url(r"^del//?$", delete_user, name="del"),
    # url(r"^register/?$", register, name="register"),
    # url(r"^new-activation-link/(?P<user_id>\d+)/$", new_activation_link,  name="new_activation_link"),
]
