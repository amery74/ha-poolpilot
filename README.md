# Pool Pilot v0.3.0

Version avec planification automatique de la filtration intégrée.

## Nouveautés

- Un seul équipement pompe est nécessaire : `CONF_PUMP_SWITCH` / entité pompe existante.
- Nouveau switch Home Assistant : **Filtration auto planifiée**.
- Pool Pilot calcule la durée quotidienne recommandée puis crée des créneaux.
- Démarrage/arrêt automatique de la pompe pendant les créneaux.
- Si la durée est longue, la filtration est découpée en deux cycles.
- Services :
  - `pool_pilot.enable_auto_schedule`
  - `pool_pilot.disable_auto_schedule`
  - `pool_pilot.toggle_auto_schedule`
  - `pool_pilot.start_auto_filtration` reste disponible pour démarrage immédiat.

## Logique de planning

- Durée = durée recommandée calculée par Pool Pilot.
- Durée <= 12h : un créneau centré autour de 15h.
- Durée > 12h : deux créneaux, matin + après-midi/soir.
- Pool Pilot n’éteint la pompe automatiquement que si c’est lui qui l’a allumée via le planning.


### Modifier/supprimer Pool House

Cette build 0.3.0 ajoute aussi le service `pool_pilot.update_product` et conserve `pool_pilot.remove_product` pour la carte Dashboard : le stylo modifie un produit existant, la croix le supprime.
