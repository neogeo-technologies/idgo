from django import forms
from django.contrib.auth.models import User
from django.db import transaction, IntegrityError

from idgo_admin.models import Dataset
from idgo_admin.exceptions import ErrorOnDeleteAccount


class UserDeletActionForm(forms.Form):

    def setting_new_related_user(self, user):
        raise NotImplementedError

    def delete_user_account(self, user):
        raise NotImplementedError

    def delete_controller(self, deleted_user, new_user, related_datasets):

        if not related_datasets:
            return self.delete_user_account(deleted_user)

        if not new_user:
            error_message = str("Selectionnez un utilisateur de remplacement")
            self.add_error(None, error_message)
        try:
            self.setting_new_related_user(deleted_user, new_user)
        except:
            raise ErrorOnDeleteAccount

    # def save(self, deleted_user, new_user, impacted_datasets):
    #     if not impacted_datasets:
    #         self.delete_related_datasets(deleted_user)
    #
    #     try:
    #         new_user = self.setting_new_related_user(deleted_user)
    #     except:
    #         raise ErrorOnDeleteAccount
    #     return new_user


class DeleteForm(UserDeletActionForm):

    new_user = forms.ModelChoiceField(
        User.objects.all(),
        empty_label="Selectionnez un utilisateur",
        label="Comptes utilisateur auquel seront affectés les jeux de donnés orphelins",
        required=True,
        widget=None,
        initial=None,
        help_text="Choisissez un nouvel utilisateur auquel seront affectés les jeux de données de l'utilisateur supprimé",
        to_field_name=None,
        limit_choices_to=None)

    confirm = forms.BooleanField(
        label="Cocher pour confirmer la suppression de ce compte. ",
        required=True, initial=False)

    def __init__(self, *args, **kwargs):
        self.included = kwargs.pop('include', {})
        super().__init__(*args, **kwargs)
        if not self.included['related_datasets']:
            self.fields['new_user'].required = False
        if self.included['user_id']:
            self.fields['new_user'].queryset = User.objects.exclude(id=self.included['user_id']).exclude(is_active=False)
        else:
            self.fields['new_user'].queryset = User.objects.filter(is_active=True)

    @transaction.atomic
    def setting_new_related_user(self, user, new_user):
        try:
            with transaction.atomic():
                Dataset.objects.filter(editor=user).update(editor=new_user)
                user.delete()
        except IntegrityError:
            raise

    def delete_user_account(self, deleted_user):
        if not Dataset.objects.filter(editor=deleted_user).exists():
            deleted_user.delete()
