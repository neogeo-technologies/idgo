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

* **DATAGIS_DB**

* **DEFAULT_USER_ID**

* **DEFAULT_FROM_EMAIL**

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

* **MRA**

* **TERMS_URL**

* **OWS_URL_PATTERN**

* **OWS_PREVIEW_URL**


#### Paramètres optionnels


* **HREF_WWW**

    Valeur par défaut: `None`

* **CKAN_TIMEOUT**

    Valeur par défaut: `36000`

* **CSW_TIMEOUT**

    Valeur par défaut: `36000`

* **DCAT_TIMEOUT**

    Valeur par défaut: `36000`

* **DATAGIS_DB_SCHEMA**

    Valeur par défaut: `'public'`

* **DATAGIS_DB_GEOM_FIELD_NAME**

    Valeur par défaut: `'the_geom'`

* **DATAGIS_DB_EPSG**

    Valeur par défaut: `4171`

* **DEFAULT_PLATFORM_NAME**

    Valeur par défaut: `'IDGO'`

* **DEFAULT_CONTACT_EMAIL**

    Valeur par défaut: `contact@idgo.fr`

* **DOWNLOAD_SIZE_LIMIT**

    Valeur par défaut: `104857600`

* **ENABLE_FTP_ACCOUNT**

    Valeur par défaut: `True`

* **ENABLE_ORGANISATION_CREATE**

    Valeur par défaut: `True`

* **ENABLE_CSW_HARVESTER**

    Valeur par défaut: `True`

* **ENABLE_CKAN_HARVESTER**

    Valeur par défaut: `True`

* **ENABLE_DCAT_HARVESTER**

    Valeur par défaut: `False`

* **EXTRACTOR_BOUNDS**

    Valeur par défaut: `[[40, -14], [55, 28]]`

* **PHONE_REGEX**

    Valeur par défaut: `'^0\d{9}$'`

* **FTP_URL**

    Valeur par défaut: `None`

* **FTP_MECHANISM**

    Valeur par défaut: `'cgi'`

* **FTP_MECHANISM**

    Valeur par défaut: `''`

* **FTP_UPLOADS_DIR**

    Valeur par défaut: `'uploads'`

* **FTP_USER_PREFIX**

    Valeur par défaut: `''`

* **GEONETWORK_LOGIN**

    Valeur par défaut: `'admin'`

* **GEONETWORK_PASSWORD**

    Valeur par défaut: `'admin'`

* **GEONETWORK_TIMEOUT**

    Valeur par défaut: `36000`

* **MAPSERV_TIMEOUT**

    Valeur par défaut: `60`

* **MDEDIT_HTML_PATH**

    Valeur par défaut: `'mdedit/html/'`

* **MDEDIT_CONFIG_PATH**

    Valeur par défaut: `'mdedit/config/'`

* **MDEDIT_DATASET_MODEL**

    Valeur par défaut: `'models/model-dataset-empty.json'`

* **MDEDIT_SERVICE_MODEL**

    Valeur par défaut: `'models/model-service-empty.json'`

* **MDEDIT_LOCALES_PATH**

    Valeur par défaut: ```python
    os.path.join(
        settings.BASE_DIR,
        'idgo_admin/static/mdedit/config/locales/fr/locales.json')
    ```

* **REDIS_HOST**

    Valeur par défaut: `'localhost'`

* **REDIS_EXPIRATION**

    Valeur par défaut: `120`

* **READTHEDOC_URL**

    Valeur par défaut: `None`


### Installer OWSLib [IMPORTANT]

Dernière version : **idgo/0.17.1.patch200520**

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
