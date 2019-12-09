# Notes pour intégration

[] Ajouter sid_id pour les modèles Organisation et Profile:
```
# idgo_admin/models.py

    # Pour le moment on sait pas si on garde des TextField ou si on aura des uuid
    sid_id = models.TextField(
        verbose_name="Référence du socle identité",
        unique=True,
        db_index=True,
        blank=True,
        null=True,
        )
```

[] Modifier le modèle Organisation en changeant la longueur max des champs 'legal_name' et 'slug':
```
# idgo_admin/models.py

    legal_name = models.CharField(
        verbose_name="Dénomination sociale",
        max_length=255,
        unique=True,
        db_index=True,
    )

    slug = models.SlugField(
        verbose_name="Slug",
        max_length=255,
        unique=True,
        db_index=True,
    )
```

[] Les champs 'first_name' et 'last_name' du modèle User de Django sont limités à 30 char,
les données du stock sont limités à 255 char.

[] Switcher les imports: sid.models vers idgo_admin.models

[] Ajouter les dépendances pour connecter django à une base mysql:
(https://pypi.org/project/mysqlclient/)
```
$ sudo apt-get install python-dev default-libmysqlclient-dev
$ sudo apt-get install python3-dev
$ pip install mysqlclient
```

[] Router la base mysql de stock
```
# settings.py
DATABASES = {
    # ...
    'sid_stock': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': CHANGE_ME,
        'USER': CHANGE_ME,
        'HOST': CHANGE_ME,
        'PASSWORD': CHANGE_ME,
        'PORT': CHANGE_ME}
    # ...
```

[] Ajouter le middleware d'authentification
```
# settings.py
MIDDLEWARE = [
    # ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'sid.auth.middleware.SidRemoteUserMiddleware',
    # ...
```
