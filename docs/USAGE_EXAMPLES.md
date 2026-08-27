# Utilisations de ProofForge V1.07

ProofForge convient lorsqu'une proposition logique ou une chaîne d'arguments doit être rejouable, inspectable et liée à des témoins de calcul.

## Exemples d'utilisation

- vérifier qu'une règle d'accès est une tautologie ou obtenir une valuation qui la réfute ;
- vérifier qu'une conclusion découle d'un ensemble de prémisses ;
- comparer deux formulations de règle pour confirmer leur équivalence ;
- isoler un noyau minimal d'exigences contradictoires ;
- construire la fermeture des dépendances d'une preuve et repérer les hypothèses ouvertes.
- vérifier la cohérence conjointe de plusieurs conclusions déjà prouvées et obtenir
  un modèle ou un noyau contradictoire explicite.
- mesurer quelles prémisses-obligations sont couvertes par d’autres preuves formelles
  sélectionnées, identifier les lacunes et les fournisseurs inutilisés.

## Installation PowerShell

```powershell
Set-Location .\proofforge
.\scripts\Setup.ps1
.\scripts\Start.ps1
```

L’API écoute par défaut sur `http://127.0.0.1:8013` et sa documentation interactive
est disponible sur `/docs`.

## Dossier de cohérence V1.05 complet

Les deux arguments ci-dessous établissent respectivement `P` et `!P`. Le serveur
fige les arguments, calcule les entaillements, puis constate leur contradiction.

```powershell
$BaseUri = "http://127.0.0.1:8013"

$PositiveArgument = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/arguments" -ContentType "application/json" `
  -Body (@{
    name = "Conclusion positive"
    premises = @("P")
    conclusion = "P"
    variables = @("P")
  } | ConvertTo-Json -Depth 8)

$NegativeArgument = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/arguments" -ContentType "application/json" `
  -Body (@{
    name = "Conclusion négative"
    premises = @("!P")
    conclusion = "!P"
    variables = @("P")
  } | ConvertTo-Json -Depth 8)

$PositiveProof = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/entailments" -ContentType "application/json" `
  -Body (@{ argument_id = $PositiveArgument.id } | ConvertTo-Json)

$NegativeProof = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/entailments" -ContentType "application/json" `
  -Body (@{ argument_id = $NegativeArgument.id } | ConvertTo-Json)

$Dossier = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/multi-argument-coherence-dossiers" `
  -ContentType "application/json" `
  -Body (@{
    entailment_ids = @($NegativeProof.id, $PositiveProof.id)
  } | ConvertTo-Json -Depth 8)

$Dossier.qualification
$Dossier.contradiction_witnesses | ConvertTo-Json -Depth 12
$Dossier.snapshot_hash

Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/multi-argument-coherence-dossiers/$($Dossier.id)"
Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/multi-argument-coherence-dossiers"
```

Le corps de création doit contenir uniquement `entailment_ids` et, facultativement,
la méthode constante documentée. Toute tentative d’envoyer `qualification`,
`witnesses`, `result` ou une autre propriété est rejetée par `extra=forbid`.

## Dossier chronologique de stabilité V1.06

Créez plusieurs arguments immuables portant le même `name` pour représenter les états
successifs d’une même preuve, puis calculez chaque entaillement. Ici, `$ProofV1`,
`$ProofV2` et `$ProofV3` sont les réponses de `POST /v1/entailments`.

```powershell
$Stability = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/proof-stability-dossiers" `
  -ContentType "application/json" `
  -Body (@{
    entailment_ids = @($ProofV3.id, $ProofV1.id, $ProofV2.id)
  } | ConvertTo-Json -Depth 8)

$Stability.qualification
$Stability.transitions | ConvertTo-Json -Depth 10
$Stability.longest_stable_streak
$Stability.worst_transition | ConvertTo-Json -Depth 10
$Stability.dependencies

Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/proof-stability-dossiers/$($Stability.id)"
Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/proof-stability-dossiers"
```

L’ordre de la liste n’est pas une chronologie client : le serveur impose
`created_at`, puis `id`. N’envoyez ni `qualification`, ni transition, ni compteur, ni
témoin. Une stabilité formelle n’accorde aucune autorisation automatique.

## Parcours type

1. Enregistrer les formules ou arguments.
2. Demander le calcul avec leurs identifiants, sans fournir de verdict.
3. Lire le résultat, les contre-exemples et les hashes.
4. Pour une preuve composée, créer un dossier de dépendances et examiner `CLOSED`, `OPEN_ASSUMPTIONS`, `CYCLIC` ou `INVALID`.
5. Pour plusieurs conclusions, créer un dossier de cohérence et examiner
   `CONSISTENT`, `CONTRADICTORY`, `INSUFFICIENT` ou `INCOMPATIBLE`.
6. Pour une série de preuves, créer un dossier chronologique et examiner `STABLE`,
   `REGRESSED`, `RECOVERED`, `INSUFFICIENT` ou `INCOMPATIBLE`.
7. Pour un périmètre de preuves, créer un dossier de couverture et examiner
   `COMPLETE`, `GAPPED`, `INSUFFICIENT` ou `INCOMPATIBLE` ainsi que les obligations.

Une preuve formelle dans le langage pris en charge n'établit pas la vérité empirique de ses prémisses.

## Dossier de couverture des obligations V1.07

Créez d’abord les arguments et leurs entaillements. Dans l’exemple ci-dessous,
`$ProofA` conclut `P` à partir de `P & P`, tandis que `$ProofB` conclut `P & P` à
partir de `P`. Les deux preuves sont formellement valides et chaque conclusion couvre
la prémisse de l’autre preuve.

```powershell
$Coverage = Invoke-RestMethod -Method Post `
  -Uri "$BaseUri/v1/proof-obligation-coverage-dossiers" `
  -ContentType "application/json" `
  -Body (@{
    entailment_ids = @($ProofB.id, $ProofA.id)
  } | ConvertTo-Json -Depth 8)

$Coverage.qualification
$Coverage.coverage_ratio
$Coverage.obligations | ConvertTo-Json -Depth 10
$Coverage.worst_reference | ConvertTo-Json -Depth 10
$Coverage.orphan_provider_entailment_ids

Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/proof-obligation-coverage-dossiers/$($Coverage.id)"
Invoke-RestMethod -Method Get `
  -Uri "$BaseUri/v1/proof-obligation-coverage-dossiers"
```

Le serveur impose l’ordre `(created_at, id)` et recalcule chaque référence. Le corps
ne doit contenir que `entailment_ids` et, facultativement, la méthode constante
documentée. N’envoyez ni qualification, ni ratio, ni obligation, ni fournisseur.
`COMPLETE` signifie seulement que toutes les prémisses du périmètre sélectionné ont
une conclusion formelle correspondante issue d’une autre preuve valide.
