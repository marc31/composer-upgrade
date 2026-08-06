# Spécification -- Outil interactif de mise à jour des dépendances Composer

## Objectif

Créer un exécutable **Python** permettant d'analyser les dépendances
Composer, de proposer des mises à jour interactives et d'assister
l'utilisateur dans le choix de la version à installer.

L'outil **ne remplace pas Composer** : il l'orchestre.

------------------------------------------------------------------------

# Objectifs fonctionnels

-   Lister les dépendances obsolètes.
-   Afficher les mises à jour mineures, majeures et patch.
-   Filtrer les versions trop récentes (release age minimal).
-   Consulter l'historique des versions d'un paquet.
-   Consulter les changelogs lorsqu'ils existent.
-   Sélectionner précisément la version à installer.
-   Générer puis exécuter les commandes Composer appropriées.

------------------------------------------------------------------------

# Pourquoi Python ?

Le projet devient rapidement complexe :

-   JSON
-   appels HTTP
-   GitHub / GitLab / Packagist
-   comparaison de versions
-   interface interactive
-   orchestration Composer

Python est plus maintenable que Bash.

Ne pas réimplémenter Composer.

Composer reste la source de vérité pour :

-   résolution des dépendances
-   contraintes
-   versions installables
-   dépôts configurés

------------------------------------------------------------------------

# Ligne de commande

``` text
composer-upgrade [OPTIONS]
```

Options :

``` text
--direct
    Affiche uniquement les dépendances directes.

--composer-command "<commande>"
    Exemple :
        composer
        ./vendor/bin/sail composer

--min-release-age DAYS
    Ignore les releases publiées depuis moins de DAYS jours.

--minimum-release-age-exclude PATTERN
    Option répétable.
    Exemples :
        rector/rector
        laravel/*
        symfony/*

--major
    Rend visibles et sélectionnables les mises à jour majeures.

--dry-run

--no-interaction

--with-all-dependencies
```

------------------------------------------------------------------------

# Fonctionnement

## Écran principal

Colonnes proposées :

  TYPE   NEW   AGE   PACKAGE   INSTALLED   LATEST ELIGIBLE
  ------ ----- ----- --------- ----------- -----------------

TYPE :

-   PATCH
-   MINOR
-   MAJOR

NEW :

-   NEW si la release date est inférieure au seuil configuré.

AGE :

Nombre de jours depuis la publication de la version.

Tri :

-   AGE croissant.

Le filtre "release age" doit être appliqué **aux versions**, pas aux
paquets.

Exemple :

    installée : 2.5.2

    2.6.1   sortie il y a 1 jour
    2.6.0   sortie il y a 8 jours

avec :

    --min-release-age 3

la version proposée est :

    2.6.0

Le paquet reste affiché.

------------------------------------------------------------------------

# Navigation interactive

Actions souhaitées :

-   sélectionner plusieurs paquets
-   afficher les informations d'un paquet
-   choisir une version spécifique
-   lancer les mises à jour

L'implémentation de l'interface est libre.

Une intégration fzf est un plus mais ne doit pas être obligatoire.

------------------------------------------------------------------------

# Vue d'un paquet

Afficher :

-   nom
-   version installée
-   contrainte Composer
-   dépôt
-   homepage

Puis :

| VERSION \| DATE \| AGE \| TYPE \| ELIGIBLE \|

jusqu'à la version installée.

Exemple :

    2.6.1
    2.6.0
    2.5.3
    2.5.2 <- installée

------------------------------------------------------------------------

# Changelog

Détecter automatiquement l'hébergeur :

-   GitHub
-   GitLab
-   Bitbucket

Pour GitHub :

-   Releases
-   Notes de release
-   URL
-   Date

Afficher uniquement les releases comprises entre la version installée et
la version sélectionnée.

------------------------------------------------------------------------

# Mise à jour

Cas 1 :

La version est compatible avec la contrainte actuelle.

Utiliser :

``` text
composer update vendor/package:VERSION --with-all-dependencies
```

Cas 2 :

La version est incompatible (ex : majeure).

Prévenir l'utilisateur que la contrainte sera modifiée.

Utiliser ensuite :

``` text
composer require vendor/package:^VERSION --with-all-dependencies
```

Le script doit détecter automatiquement si le paquet appartient à :

-   require
-   require-dev

------------------------------------------------------------------------

# Sécurité

Avant toute modification :

-   vérifier la présence de composer.json
-   vérifier la présence de composer.lock
-   proposer un dry-run
-   afficher le plan d'exécution
-   demander confirmation
-   exécuter Composer
-   afficher le résultat

------------------------------------------------------------------------

# Sources de données

Composer :

-   paquets installés
-   contraintes
-   dépendances directes
-   résolution

Packagist / dépôt Composer :

-   versions
-   dates

GitHub / GitLab / Bitbucket :

-   releases
-   changelogs

Ne jamais supposer que tous les paquets sont sur GitHub.

------------------------------------------------------------------------

# Architecture proposée

``` text
composer_upgrade/
├── __main__.py
├── cli.py
├── config.py
├── composer.py
├── updater.py
├── models.py
├── versions.py
├── repositories/
│   ├── base.py
│   ├── packagist.py
│   ├── github.py
│   ├── gitlab.py
│   └── bitbucket.py
└── ui/
    ├── simple.py
    └── fzf.py
```

------------------------------------------------------------------------

# Principe important

L'application ne doit jamais essayer de reproduire le fonctionnement du
résolveur de Composer.

Elle doit uniquement :

-   collecter les informations
-   aider à choisir
-   construire les commandes
-   laisser Composer effectuer la résolution.
