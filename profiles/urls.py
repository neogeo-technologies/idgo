from django.conf.urls import url

from profiles.views import add_user, activation, delete_user, update_user, login_view, logout_view
                           # update_user
                           # delete_user_id, delete_user,
                           # register,
                           # activation, new_activation_link

urlpatterns = [
    url(r"^login/?$", login_view, name="login"),
    url(r"^logout/?$", logout_view, name="logout"),
    url(r"^add/?$", add_user, name="add_user"),
    url(r"^activate/(?P<key>.+)/?$", activation,  name="activation"),
    url(r"^del/?$", delete_user, name="delete"),
    url(r"^account/?$", update_user, name="account")
]
