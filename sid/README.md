
# SID

## Configuration

**Dans le fichier _settings.py_ de l'application :**

* Ajouter l'application :

    ```
    INSTALLED_APPS = [
        # ...
        'idgo_admin',
        'sid',
        # ...
    ]
    ```

* Ajouter le module d'authentification à la liste des Middleware dans le settings.py de l'application :

    ```
    MIDDLEWARE = [
        # ...
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'sid.auth.middleware.SidRemoteUserMiddleware',
        # ...
    ```

* Activer le module et indiquer l'attribut du HEADER

    ```
    OIDC_SETTED = True  # False par défaut
    HEADER_UID = 'OIDC_CLAIM_uid'  # Valeur par défaut
    ```


### Dans le fichier _urls.py_ de l'application


## Informations utiles


L'_username_ du modèle **User** de Django correspond à l'identifiant de l'agent/employée.

Le _slug_ du modèle **Organisation** de IDGO correspond à l'identifiant de l'organisme/la companie.


