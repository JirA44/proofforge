# Journal des versions

## V1.07 — 1.0.7

- Dossiers de couverture fondés sur 2 à 100 identifiants d’entaillements uniques et
  persistés, avec ordre serveur déterministe `(created_at, id)`.
- Recalcul des arguments, verdicts, contre-exemples et empreintes SHA-256 avant toute
  qualification ; aucun résultat calculé n’est accepté du client.
- Chaque prémisse devient une obligation reliée aux conclusions exactes des autres
  preuves sélectionnées, valides et entailées ; l’auto-couverture est interdite.
- Totaux, ratio global et par preuve, fournisseurs déterministes, fournisseurs
  orphelins, lacunes et pire référence explicitement exposés.
- Qualifications prudentes `COMPLETE`, `GAPPED`, `INSUFFICIENT` et `INCOMPATIBLE`.
- Snapshot ordre-indépendant, dossier immuable, idempotent, hashé et audit append-only
  `PROOF_OBLIGATION_COVERAGE_ANALYZED`.
- API POST/GET/list, SQLite/PostgreSQL, OpenAPI 3.1, documentation française,
  PowerShell et CI alignés sur 1.0.7.

## V1.06 — 1.0.6

- Dossiers chronologiques immuables sur 2 à 100 entaillements persistés.
- Ordre serveur déterministe `(created_at, id)`, recalcul des arguments, résultats,
  hashes et dépendances exactes entre conclusions antérieures et prémisses.
- Transitions de verdict, régressions, récupérations, plus longue série stable, pire
  transition et contre-exemples pertinents calculés côté serveur.
- Qualifications prudentes `STABLE`, `REGRESSED`, `RECOVERED`, `INSUFFICIENT` et
  `INCOMPATIBLE` selon des règles fixes documentées.
- Snapshot ordre-indépendant, dossier hashé, immuable, idempotent et audit append-only
  `PROOF_STABILITY_ANALYZED`.
- API POST/GET/list, SQLite/PostgreSQL, OpenAPI 3.1, documentation française,
  PowerShell et CI alignés sur 1.0.6.

## V1.05 — 1.0.5

- Dossiers de cohérence formelle fondés uniquement sur 2 à 50 identifiants
  d’entaillements persistés et uniques.
- Rechargement des arguments et entaillements, recalcul des preuves et vérification
  de tous les hashes avant qualification.
- Ensemble canonique des conclusions et détection exhaustive de leur satisfaisabilité
  conjointe dans la borne existante de huit variables.
- Qualifications serveur `CONSISTENT`, `CONTRADICTORY`, `INSUFFICIENT` et
  `INCOMPATIBLE`, avec affectation satisfaisante ou noyau contradictoire et témoins.
- Snapshot indépendant de l’ordre, dossier hashé, immuable, idempotent et audit
  append-only `MULTI_ARGUMENT_COHERENCE_ANALYZED`.
- API POST/GET/list, SQLite/PostgreSQL, OpenAPI 3.1, documentation française et CI
  Python 3.10/3.12 alignés.

## V1.04 — 1.0.4

- Dossiers déterministes de fermeture des dépendances d’une preuve racine.
- Recalcul serveur des entaillements, arguments et hashes persistés.
- Graphe exact conclusion-vers-prémisse, preuves atteignables et supports inutilisés.
- Qualifications `CLOSED`, `OPEN_ASSUMPTIONS`, `CYCLIC` et `INVALID`.
- Snapshots immuables, idempotents, hashés et audités ; aucun résultat client.
- API de création, liste et consultation, SQLite/PostgreSQL et OpenAPI 3.1 alignés.
- Vingt-neuf tests cumulatifs validés.

## V1.03 — 1.0.3

- Jeux de prémisses immuables et hashés.
- Détection exhaustive de cohérence ou d’incohérence.
- Extraction déterministe d’un noyau incohérent minimal par inclusion.
- Témoins machine prouvant la nécessité de chaque prémisse du noyau.
- Rejeu idempotent, audit append-only et protections SQLite/PostgreSQL.
- Aucun verdict, noyau ou témoin accepté depuis le client.
- Vingt tests historiques et nouveaux validés.

## V1.02 — 1.0.2

- Comparaison déterministe de l'équivalence de deux expressions.
- Contre-exemple détaillé lorsqu'une valuation produit des valeurs différentes.
- Snapshots de comparaison immuables, idempotents, hashés et audités.
- Routes de création, liste et consultation des comparaisons.

## V1.01 — 1.0.1

- Ajout des arguments immuables composés de prémisses et d'une conclusion.
- Vérification déterministe de l'entaillement par table de vérité.
- Contre-exemple machine pour les arguments non valides.
- Détection explicite des ensembles de prémisses incohérents.
- Rejeu idempotent, hashes de résultats et stockage append-only renforcé.

## V1.00 — 1.0.0

- Registre de propositions immuables.
- Vérification déterministe des tautologies propositionnelles.
