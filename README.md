# Pool Pilot v0.2.0

Prototype Home Assistant pour piscine : chimie, filtration, PAC et **Pool House**.

## Nouveau : Pool House et dosages

Ajoute tes produits via les services Home Assistant `pool_pilot.add_product`.

### Exemple pH moins Cash Piscine

Produit : 100 g pour 10 m³ afin de diminuer le pH de 0,1.

```yaml
service: pool_pilot.add_product
data:
  id: ph_minus_cash_5kg
  name: pH moins Cash Piscine
  category: ph_minus
  dosage_quantity: 100
  dosage_unit: g
  volume_basis_m3: 10
  effect_delta: 0.1
  stock_quantity: 5000
  stock_unit: g
```

Pour un bassin de 27 m³ avec pH 7,6 et cible 7,4, Pool Pilot recommande environ **540 g**.

### Exemple galets / pastilles

Produit : 5 pastilles pour 10 m³.

```yaml
service: pool_pilot.add_product
data:
  id: pastilles_chlore_5_10m3
  name: Pastilles chlore lent
  category: chlorine
  dosage_quantity: 5
  dosage_unit: pastille
  volume_basis_m3: 10
  stock_quantity: 80
  stock_unit: pastille
```

## Capteurs ajoutés

- `sensor.pool_pilot_recommandation_produit` : recommandation principale avec quantité.
- `sensor.pool_pilot_pool_house` : inventaire en attributs.
- `sensor.pool_pilot_actions` : attribut `recommendations` exploitable par la carte Lovelace.

## Services

- `pool_pilot.add_product`
- `pool_pilot.set_product_stock`
- `pool_pilot.confirm_product_added`
- `pool_pilot.remove_product`

La confirmation décrémente le stock lorsque l’unité de dosage et l’unité de stock sont identiques.
