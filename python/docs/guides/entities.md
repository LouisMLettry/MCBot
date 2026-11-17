# Entities

Entities are everything in the world that isn't a block: mobs, animals, dropped items, other players, arrows,
boats… Each one comes as an [`Entity`][mcbot.Entity].

## List the entities around the player

```python
for e in mc.get_entities(radius=32):
    print(e.type, e.pos, round(e.distance, 1))
```

```
cow (12.4, -60.0, 3.1) 4.2
item (8.5, -60.0, 9.7) 6.0
zombie (20.1, -60.0, -2.3) 12.8
```

They come **nearest first**, without the player itself. Options:

```python
mc.get_entities(radius=16, types=["zombie", "skeleton"], limit=5)
mc.get_entities_in((0, -64, 0), (31, -50, 31))    # whose hitbox touches a box
```

- `types`: only these types (`"zombie"`, `"cow"`, `"item"`, `"player"`…). Default: all.
- `limit`: at most this many, the nearest ones.
- An empty list is not an error: there is just nothing around.

## What you know about an entity

```python
e.id               # stays the same while the entity exists: use it to follow one
e.type, e.category # "zombie", "monster"
e.pos, e.motion    # feet position, movement during the last tick
e.yaw, e.pitch     # where it faces
e.size, e.box      # hitbox (width, height), and its two corners
e.health           # living entities only, else None
e.item, e.count    # dropped items only: "oak_log", 3
e.name             # name tag, or a player's name
e.is_hostile       # True for monsters
```

All fields: [`Entity`][mcbot.Entity].

## Follow an entity

Ids are stable, so you can track one entity across requests:

```python
cow = mc.get_entities(types=["cow"], limit=1)[0]
for _ in range(10):
    _, info = mc.step(ticks=20, entities={"types": ["cow"]})
    same = next((e for e in info["entities"] if e.id == cow.id), None)
    print("gone" if same is None else same.pos)
```

## Which entities the camera sees

With `visibility=True`, each entity gets two flags:

- `in_view`: its hitbox is inside the camera's field of view;
- `line_of_sight`: a straight line from the camera reaches it without crossing a block (glass doesn't block,
  leaves do).

An entity shows in the picture only if it has both and is not `invisible`:

```python
seen = [e for e in mc.get_entities(visibility=True) if e.in_view and e.line_of_sight and not e.invisible]
```

## Entities that match an image

`step` can list the entities together with the image, **as the image shows them**: same camera, same moment.
Use this when you pair pictures with labels, for example to train an object detector:

```python
image, info = mc.step(ticks=1, frame=True, entities={"radius": 32, "visibility": True})
visible = [e for e in info["entities"] if e.in_view and e.line_of_sight]
```

The `entities` argument takes the same options as `get_entities`: `radius`, `min`/`max`, `types`, `limit`,
`visibility`.

## What the game knows

The mod only knows the entities the server sends to the game: about **8 chunks** around for mobs, 6 for dropped
items, never beyond the render distance. It knows what a player could see (position, health, name…), not a mob's
intentions (its target, its path). See [Limits](../concepts/limits.md).
