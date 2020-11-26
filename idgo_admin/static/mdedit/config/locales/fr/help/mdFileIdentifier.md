<!-- Begin @mdFileIdentifier.md -->

# Identifiant de la fiche

## Définition

Code permettant d’identifier de manière unique la fiche de description de la donnée.
Ce code n’est jamais modifié pour une fiche même lors de sa mise à jour.

S'il n'est pas renseigné, cet identifiant est généré automatiquement par mdEdit sous la forme d'un code unique pseudo aléatoire.

## Recommandations

Afin d’obtenir un code unique, il existe 2 possibilités:

- Construire cet identifiant en associant le code pays de l’organisme propriétaire de la donnée, son numéro SIREN, ainsi qu’un code unique définit par le propriétaire de la donnée (ex.: FR–246300019–143_004).
- Utiliser une URI, c'est à dire une adresse internet (URL) composée du nom de domaine du site internet de l'organisme propriétaire des données suivi d'un identifiant. Cette adresse ne doit pas obligatoirement pointée vers une ressource particulière.

**Structure recommandée de l’identifiant :**

- Code du pays : « FR »
- Séparateur   : « – »
- Code SIREN   : code à 9 chiffres
- Séparateur   : « – »
- Code unique  : choisi par l'administrateur des données
