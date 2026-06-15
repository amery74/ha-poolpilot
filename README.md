# Pool Pilot pour Home Assistant

Pool Pilot est un prototype d'intégration custom qui agrège des entités déjà présentes dans Home Assistant pour piloter une piscine : Flipr/local, pompe de filtration, pompe à chaleur et météo.

## Fonctions incluses

- Configuration du volume en m³.
- Sélection des entités existantes : température eau, pH, RedOx/ORP, chlore libre, pompe, PAC, météo, température prévue, couverture.
- Capteurs calculés : durée de filtration recommandée, facteur météo, état chimie, état baignade, actions recommandées.
- Réglages via entités `number` : pH cible, chlore cible, coefficient de filtration, min/max heures.
- Sélecteur de mode filtration : `off`, `manual`, `auto`.
- Boutons : démarrer/arrêter la pompe, confirmer chlore, pH-, pH+, lavage filtre.

## Installation manuelle

1. Décompresse le ZIP.
2. Copie `custom_components/pool_pilot` dans `/config/custom_components/pool_pilot`.
3. Redémarre Home Assistant.
4. Va dans **Paramètres > Appareils et services > Ajouter une intégration > Pool Pilot**.
5. Sélectionne les entités existantes.

## Notes importantes

Ce dépôt est une base installable/prototype. Les actions sur la pompe utilisent `homeassistant.turn_on` et `homeassistant.turn_off` sur l'entité configurée. Pour une piscine réelle, ajoute toujours des sécurités matérielles indépendantes : débit, pression, niveau d'eau, asservissement PAC/pompe.

## Exemple d'automation de notification

```yaml
alias: Piscine - Alerte action recommandée
trigger:
  - platform: state
    entity_id: sensor.piscine_actions_recommandees
action:
  - service: notify.mobile_app_mon_telephone
    data:
      title: Piscine
      message: "{{ states('sensor.piscine_actions_recommandees') }}"
```

## Exemple d'automation PAC -> pompe

```yaml
alias: Piscine - Sécurité PAC pompe
trigger:
  - platform: state
    entity_id: climate.pac_piscine
action:
  - choose:
      - conditions: "{{ is_state('climate.pac_piscine', 'heat') }}"
        sequence:
          - service: switch.turn_on
            target:
              entity_id: switch.pompe_piscine
```
