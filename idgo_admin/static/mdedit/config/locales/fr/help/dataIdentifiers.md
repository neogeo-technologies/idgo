<!-- Begin @dataIdentifiers.md -->

# Identifiant de la donnée

## Définition

Le ou les identifiants de la donnée correspondent à un ou plusieurs codes permettant d’identifier de manière unique la donnée.  
Ces codes ne sont jamais modifiés pour une donnée même lors de sa mise à jour.

## Recommandations

Afin d’obtenir un code unique, il est recommandé de construire cet identifiant en associant le code pays de l’organisme propriétaire de la donnée, son numéro SIREN, ainsi qu’un code unique définit par le propriétaire de la donnée selon le schéma ci-dessous.  
Le code unique peut être généré de façon automatique selon un algorithme ou de façon aléatoire.

Structure recommandée de l’identifiant :

- Code du pays : « FR »
- Séparateur : « – »
- Code SIREN : code à 9 chiffres
- Séparateur : « – »
- Code unique

Il est également possible d’associer au code un espace de nommage pour préciser sa provenance (cf. exemple 2 ci-dessous). L’espace de nommage correspond au domaine dans lequel la donnée est identifiée par ce code et renvoie généralement à l’organisme qui a attribué l’identifiant à la donnée.  
Il est recommandé d’intégrer les informations concernant l’espace de nom, dans le code de la donnée (cf. exemple 1 ci-dessous).
