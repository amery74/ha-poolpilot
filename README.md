# Pool Pilot v0.5.0

Version avec **filtration auto intelligente**.

## Nouveautés

- Mode manuel conservé.
- Mode auto intelligent : activation une fois, Pool Pilot gère ensuite chaque jour.
- Plage horaire par défaut : 07:00 → 22:00.
- Calcul quotidien basé sur température eau + météo prévue.
- Démarrage automatique chaque matin si le mode auto est actif.
- Arrêt automatique lorsque la durée recommandée du jour est atteinte ou à 22:00.
- Suivi du cycle du jour dans les attributs du switch auto.

## Entité principale

Utiliser le switch :

```yaml
switch.pool_pilot_filtration_auto_intelligente
```

Ses attributs exposent :

- status
- target_hours
- done_hours
- end_limit
- next_start
- windows
- detail

