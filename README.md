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


### Paramètres additionnels du `settings.py`


#### Paramètres obligatoire

* **CKAN_API_KEY**

* **CKAN_STORAGE_PATH**

* **CKAN_URL**

* **DATABASES**

* **DEFAULT_FROM_EMAIL**

* **DEFAULTS_VALUES**

* **DOMAIN_NAME**

* **EXTRACTOR_URL**

* **EXTRACTOR_URL_PUBLIC**

* **FTP_DIR**

* **FTP_SERVICE_URL**

* **GEONETWORK_URL**

* **LOGIN_URL**

* **LOGOUT_URL**

* **MAPSERV_STORAGE_PATH**

* **TERMS_URL**

* **OWS_URL_PATTERN**

* **OWS_PREVIEW_URL**

Utiliser les futurs paramètres de l'application **idgo-geographic-layer** :

* **IDGO_GEOGRAPHIC_LAYER_DB_TYPE**

* **IDGO_GEOGRAPHIC_LAYER_DB_PORT**

* **IDGO_GEOGRAPHIC_LAYER_DB_HOST**

* **IDGO_GEOGRAPHIC_LAYER_DB_NAME**

* **IDGO_GEOGRAPHIC_LAYER_DB_USERNAME**

* **IDGO_GEOGRAPHIC_LAYER_DB_PASSWORD**

* **IDGO_GEOGRAPHIC_LAYER_MRA_URL**

* **IDGO_GEOGRAPHIC_LAYER_MRA_USERNAME**

* **IDGO_GEOGRAPHIC_LAYER_MRA_PASSWORD**

Utiliser les futurs paramètres de l'application **idgo-geographic-layer** :

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_TYPE**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_TYPE**

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_HOST**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_HOST**

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_PORT**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_PORT**

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_NAME**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_NAME**

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_USERNAME**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_USERNAME**

* **IDGO_GEOGRAPHIC_LAYER_MRA_DB_PASSWORD**

    Valeur par défaut: **IDGO_GEOGRAPHIC_LAYER_DB_PASSWORD**


#### Paramètres optionnels

Cf. `./idgo_admin/__init__.py`


### Installer OWSLib [IMPORTANT]

Récupérer et installer la dernière version Neogeo patchée, par ex. :

```shell
(idgo_venv) /idgo_venv> pip install -e git+https://github.com/neogeo-technologies/OWSLib.git@idgo/0.17.1.patch200520#egg=OWSLib
```


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
            AuthName "User authentication"
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
