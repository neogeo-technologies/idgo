from rest_framework.exceptions import ValidationError
from rest_framework import status

ERRORS = {
    '001': {
        'classType': None,
        'errorCode': '001',
        'errorLabel': 'SYNTAX_ERROR',
        'errorMessage': "Syntaxe du message en entrée incorrecte",
        'methodType': None,
        'resourceId': None,
    },
    '002': {
        'classType': None,
        'errorCode': '002',
        'errorLabel': 'FORMAT_ERROR',
        'errorMessage': "Un champ de la ressource est invalide",
        'methodType': None,
        'resourceId': None,
    },
    '003': {
        'classType': None,
        'errorCode': '003',
        'errorLabel': 'RESOURCE_MISSING',
        'errorMessage': "La ressource spécifiée est introuvable",
        'methodType': None,
        'resourceId': None,
    },
    '004': {
        'classType': None,
        'errorCode': '004',
        'errorLabel': 'RELATION_MISSING',
        'errorMessage': "Une relation avec l'entité est manquante",
        'methodType': None,
        'resourceId': None,
    },
    '005': {
        'classType': None,
        'errorCode': '004',
        'errorLabel': 'RESOURCE_ALREADY_EXISTS',
        'errorMessage': "La ressource existe déja",
        'methodType': None,
        'resourceId': None,
    },
    '006': {
        'classType': None,
        'errorCode': '006',
        'errorLabel': 'INTERNAL_SERVER_ERROR',
        'errorMessage': "Erreur interne au serveur",
        'methodType': None,
        'resourceId': None,
    },
    '007': {
        'classType': None,
        'errorCode': '007',
        'errorLabel': 'INTERNAL_CLIENT_ERROR',
        'errorMessage': "Erreur interne au client",
        'methodType': None,
        'resourceId': None,
    },
}


class SidGenericError(ValidationError):

    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = ERRORS['006']
    default_code = 'internal_server_error'

    def __init__(self, client_error_code=None, extra_context={}, status_code=None, *args, **kwargs):
        if status_code:
            self.status_code = status_code
        else:
            self.status_code = self.default_status
        if client_error_code in ERRORS.keys():
            ERRORS[client_error_code].update(extra_context)
            self.detail = ERRORS[client_error_code]
