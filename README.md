# IDGO Admin

## Installation et configuration

Application initialement développée dans un environnement virtuel __Python 3.5__.

```shell
> cd /
/> mkdir idgo_venv
/> cd idgo_venv
/idgo_venv> pyvenv-3.5 ./
/idgo_venv> source bin/activate
(idgo_venv) /idgo_venv> cd /path/to/idgo
(idgo_venv) /idgo_venv> python setup.py
(idgo_venv) /idgo_venv>
```

_**TODO** : Création des fichiers de configuration, création des bases de données, etc._


### Installer MDEDIT

https://github.com/neogeo-technologies/mdedit

**MDedit** doit être installé dans le répertoire `static/libs/` de l'application __idgo_admin__.


### Utiliser le service d'autorisation d'accès à **Mapserver**

Configurer **Apache**

*   Ajouter dans le **VirtualHost** :

    ```
    RewriteEngine On
    RewriteMap anonymous_access "prg:/idgo_venv/idgo_admin/auth_ogc.py"

    RewriteCond %{HTTP:Authorization} ^$
    # ALORS ON VA VERS LE RESULTAT RENVOYE PAR REMAP
    RewriteRule (.*) ${anonymous_access:$1?%{QUERY_STRING}} [last,P,QSA]
    RewriteRule (.*) http://localhost/private$1 [P,QSA]
    ```

    Redirige vers http://localhost/public quand la ressource est accessible aux utilisateurs anonymes et que les _login / password_ ne sont pas renseignés en **BasicAuth**.

    Sinon, redirige vers http://localhost/private, qui vérifie les droits d'authentification et les autorisations.

*   Puis ajouter :

    ```
    <VirtualHost *:80>
        ServerName localhost

        ProxyRequests Off
        <Location /private>
            WSGIAuthUserScript /idgo_venv/idgo_admin/auth_ogc.py application-group=idgo.com
            WSGIApplicationGroup auth
            AuthType Basic
            AuthName "DataSud authentification"
            AuthBasicProvider wsgi
            Require valid-user

            ProxyPass http://mapserver/
            ProxyPassReverse http://mapserver/
        </Location>
        <Location /public>
            ProxyPass http://mapserver/
            ProxyPassReverse http://mapserver/
        </Location>
    </VirtualHost>
    ```

Utiliser le fichier **auth\_ogc.py**

Tester avec **pyresttest** :

```
> pip install pyresttest
> pyresttest test/test_auth_ogc.yml --url=https://ocs.dev.idgo.neogeo.fr
```
