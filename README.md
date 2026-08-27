> **Présentation → [docs/PRESENTATION.md](docs/PRESENTATION.md)** — à quoi ça sert, cas d'usages, usages futurs.

# ProofForge V1.07

ProofForge enregistre des propositions et des arguments immuables, puis vérifie leur forme par calcul déterministe. Le client soumet des expressions, jamais un verdict.

La V1.07 est cumulative : elle conserve le vérificateur de tautologies V1.00,
l'entaillement V1.01, la comparaison d'équivalence V1.02, l’analyse des prémisses
incohérentes V1.03 et les dépendances V1.04, ajoute la cohérence
multi-arguments V1.05 et la stabilité chronologique V1.06, puis mesure la couverture
exacte des obligations de preuve.

## Couverture des obligations — nouveauté V1.07

`POST /v1/proof-obligation-coverage-dossiers` accepte exclusivement 2 à 100
`entailment_ids` uniques et persistés. Le serveur ignore l’ordre client, recharge les
preuves et arguments par `(created_at, id)`, recalcule les verdicts et toutes les
empreintes SHA-256, puis traite chaque prémisse comme une obligation. Une obligation
est `COVERED` seulement si la conclusion d’une autre preuve sélectionnée, valide et
`ENTAILED`, lui correspond exactement après suppression des espaces. Une preuve ne
peut donc pas couvrir elle-même sa propre prémisse.

Le dossier expose toutes les obligations et leurs fournisseurs déterministes, la
couverture par référence, les totaux, le ratio global, les fournisseurs orphelins et
la pire référence. Le client ne peut fournir aucun de ces résultats.

| Priorité | Règle fixe | Qualification |
|---:|---|---|
| 1 | preuve/hash recalculé invalide ou contrat incompatible | `INCOMPATIBLE` |
| 2 | au moins une référence n’est pas `ENTAILED` | `INSUFFICIENT` |
| 3 | au moins une prémisse n’a aucun fournisseur valide distinct | `GAPPED` |
| 4 | toutes les obligations sont couvertes | `COMPLETE` |

Le snapshot couvre les preuves recalculées, l’ordre serveur et les obligations. Il est
immuable, idempotent et audité par `PROOF_OBLIGATION_COVERAGE_ANALYZED`. Le ratio
décrit uniquement le jeu de références fourni : il ne prouve ni la vérité empirique
des prémisses, ni l’exhaustivité des obligations métier, et n’accorde aucune
autorisation automatique.

## Stabilité chronologique — nouveauté V1.06

`POST /v1/proof-stability-dossiers` accepte uniquement 2 à 100
`entailment_ids` uniques et persistés. L’ordre client est ignoré : le serveur recharge
les preuves et leurs arguments, les trie par `(created_at, id)`, recalcule résultats et
hashes, puis reconstruit les dépendances exactes entre conclusions antérieures et
prémisses ultérieures.

Chaque paire successive produit une transition `STABLE`, `REGRESSION`, `RECOVERY` ou
`INSUFFICIENT_CHANGE`. Une régression passe de `ENTAILED` à `NOT_ENTAILED` et conserve
le contre-exemple cible ; une récupération effectue le mouvement inverse et conserve
le contre-exemple antérieur. Le dossier expose aussi les compteurs, la plus longue
série de verdict identique et la pire transition. Celle-ci est choisie selon la
sévérité fixe régression > insuffisance > récupération > stabilité, puis la plus
récente en cas d’égalité.

| Priorité | Règle fixe | Qualification |
|---:|---|---|
| 1 | hash/preuve invalide ou séries de noms/langages/méthodes différentes | `INCOMPATIBLE` |
| 2 | au moins un `INCONSISTENT_PREMISES` | `INSUFFICIENT` |
| 3 | dernière transition significative = régression | `REGRESSED` |
| 4 | dernière transition significative = récupération | `RECOVERED` |
| 5 | aucune régression/récupération | `STABLE` |

Le snapshot est indépendant de l’ordre d’entrée, hashé, immuable, idempotent et
audité. Une stabilité formelle ne prouve aucune vérité empirique et ne constitue
jamais une autorisation automatique.
`STABLE` peut parfaitement décrire une série durablement `NOT_ENTAILED` : la
qualification mesure l’absence de transition, pas la validité positive de la preuve.

## Cohérence multi-arguments — nouveauté V1.05

`POST /v1/multi-argument-coherence-dossiers` accepte uniquement une liste
`entailment_ids` de 2 à 50 identifiants uniques. ProofForge recharge chaque preuve et
son argument, recalcule l’entaillement, l’empreinte de l’argument et l’empreinte du
résultat. Le client ne fournit jamais qualification, conclusion calculée, témoin ou
contre-exemple.

Le serveur déduplique et trie les conclusions sous forme canonique, réunit les
variables déclarées, puis recherche une affectation satisfaisant toutes les
conclusions. La limite cumulative reste celle du moteur existant : **8 variables**.
Au-delà, le dossier est `INCOMPATIBLE` et aucun calcul partiel n’est présenté comme
une preuve.

| Qualification | Règle fixe |
|---|---|
| `INCOMPATIBLE` | langage/méthode incompatibles ou plus de 8 variables cumulées |
| `INSUFFICIENT` | hash/preuve non reproductible ou conclusion non entailée |
| `CONTRADICTORY` | aucune valuation ne satisfait conjointement les conclusions |
| `CONSISTENT` | une valuation explicite satisfait toutes les conclusions |

En cas de contradiction, un noyau minimal par inclusion est retourné. Chaque élément
du noyau possède une valuation qui satisfait les autres conclusions lorsqu’on le
retire : ce sont des témoins machine explicites de nécessité. Un noyau de deux
conclusions couvre notamment une proposition et sa négation logique ; un noyau plus
grand documente une impossibilité conjointe. Le snapshot est indépendant de l’ordre,
hashé, immuable, idempotent et audité une seule fois.

La cohérence formelle ne démontre ni la vérité empirique des conclusions ni leur
compatibilité métier.

## Fermeture des dépendances — nouveauté V1.04

1. `POST /v1/proof-dependency-dossiers` reçoit uniquement un `root_entailment_id` et jusqu’à 49 identifiants de preuves de support.
2. ProofForge recharge chaque argument, recalcule son entaillement et vérifie les hashes persistés. Le client ne fournit ni graphe, ni résultat, ni qualification.
3. Une arête est créée lorsqu’une conclusion de support correspond exactement, espaces ignorés, à une prémisse de la preuve racine ou d’un autre support.
4. `CLOSED` signifie que toutes les prémisses de la preuve racine ont un support fourni ; `OPEN_ASSUMPTIONS` expose celles qui restent ouvertes ; `CYCLIC` signale une dépendance circulaire ; `INVALID` signale une preuve non entailée ou non reproductible.
5. Les supports inutilisés, les cycles, la partie atteignable et les preuves recalculées sont figés dans un snapshot immuable, hashé et audité.

La fermeture concerne la racine sélectionnée : les preuves de support sont elles-mêmes revérifiées, mais leurs hypothèses ne sont pas déclarées vraies dans le monde réel.

## Noyau incohérent minimal — nouveauté V1.03

1. `POST /v1/premise-sets` fige de 1 à 32 prémisses et jusqu’à 8 variables déclarées.
2. `POST /v1/inconsistency-analyses` reçoit uniquement l’identifiant du jeu de prémisses ; aucun verdict, noyau ou témoin client n’est accepté.
3. ProofForge énumère les valuations. Un ensemble `CONSISTENT` reçoit une affectation satisfaisante. Un ensemble `INCONSISTENT` reçoit un noyau minimal par inclusion.
4. Pour chaque prémisse du noyau, une affectation satisfaisant le noyau privé de cette prémisse prouve sa nécessité. Le hash couvre le verdict, le noyau, les témoins et le nombre de valuations contrôlées.

« Minimal » signifie ici minimal par inclusion : aucune prémisse du noyau ne peut être retirée tout en conservant l’incohérence. Cela ne garantit pas le noyau de cardinalité minimale lorsqu’il en existe plusieurs. Le calcul ne juge aucune vérité empirique.

## Démarrage Windows PowerShell

```powershell
./scripts/Setup.ps1
./scripts/Start.ps1
```

Documentation : `http://127.0.0.1:8013/docs`.

## Parcours

1. `POST /v1/propositions` avec une expression utilisant `!`, `&`, `|`, `->` et des parenthèses.
2. `POST /v1/verifications` avec l’identifiant de la proposition.
3. ProofForge énumère toutes les valuations : `VERIFIED` signifie tautologie ; `REFUTED` contient un contre-exemple ; une entrée invalide est rejetée.

## Arguments — nouveauté V1.01

1. `POST /v1/arguments` avec une liste de prémisses, une conclusion et les variables déclarées.
2. `POST /v1/entailments` avec l'identifiant de l'argument.
3. Le résultat est calculé côté serveur :
   - `ENTAILED` : aucun contre-exemple n'existe ;
   - `NOT_ENTAILED` : une valuation réfute le raisonnement ;
   - `INCONSISTENT_PREMISES` : aucune valuation ne satisfait toutes les prémisses.

Les arguments et résultats sont immuables, hashés et rejoués de manière idempotente.

## Équivalence — nouveauté V1.02

1. `POST /v1/formula-comparisons` reçoit deux expressions et leurs variables déclarées, jamais un verdict.
2. ProofForge évalue les deux formules sur les mêmes valuations.
3. `EQUIVALENT` signifie qu'aucune divergence n'existe ; `NOT_EQUIVALENT` fournit la première valuation divergente ainsi que les deux valeurs calculées.
4. `GET /v1/formula-comparisons` et `GET /v1/formula-comparisons/{id}` relisent les snapshots immuables.

Une vérification machine dans ce langage limité n’établit aucune vérité concernant le monde réel.

## Tests

Guides complémentaires : [exemples d'utilisation](docs/USAGE_EXAMPLES.md) et [contribution](CONTRIBUTING.md).

```powershell
./scripts/Test.ps1
```

