"""Tests the Builder against the fake mod (no Minecraft needed)."""

from mcbot import Builder, Phase, Placement


def make_builder(client, **options):
    logs = []
    return Builder(client, delay_ticks=0, log=logs.append, **options), logs


def test_cells_are_counted_by_what_was_there(client):
    client.fake.world.update({(0, -60, 0): "stone", (1, -60, 0): "dirt"})
    builder, logs = make_builder(client)

    assert builder.place(Placement((0, -60, 0), "stone")) is False  # already the planned block
    assert builder.place(Placement((1, -60, 0), "stone")) is False  # another block: left as it is
    assert builder.place(Placement((2, -60, 0), "stone")) is True

    assert (builder.placed, builder.already_there, builder.replaced) == (1, 1, 0)
    assert builder.occupied == [(Placement((1, -60, 0), "stone"), "dirt")]
    assert client.fake.world[(1, -60, 0)] == "dirt"
    assert builder.failures == []
    assert any("occupied by dirt" in line for line in logs)
    assert builder.summary() == "1 blocks placed, 1 cells already as planned, 1 cells occupied by another block"


def test_replace_breaks_the_other_block(client):
    client.fake.world.update({(0, -60, 0): "stone", (1, -60, 0): "dirt"})
    builder, _ = make_builder(client, replace=True)

    builder.place(Placement((0, -60, 0), "stone"))
    builder.place(Placement((1, -60, 0), "stone"))

    assert client.fake.requests[-1]["replace"] is True
    assert client.fake.world[(1, -60, 0)] == "stone"
    assert (builder.placed, builder.replaced, builder.already_there, builder.occupied) == (1, 1, 1, [])
    assert builder.summary() == "1 blocks placed (1 replacing another block), 1 cells already as planned"


def test_air_empties_the_cell(client):
    client.fake.world.update({(3, -60, 0): "dirt", (4, -60, 0): "glass"})
    builder, _ = make_builder(client)

    assert builder.place(Placement((3, -60, 0), "air")) is True
    assert builder.place(Placement((4, -60, 0), "minecraft:air")) is True
    assert builder.place(Placement((5, -60, 0), "air")) is False  # already empty

    assert client.fake.world == {}
    assert [r["type"] for r in client.fake.requests] == ["break_block"] * 3  # no block put in hand
    assert (builder.removed, builder.already_there, builder.placed) == (2, 1, 0)
    assert builder.summary() == "0 blocks placed, 2 removed, 1 cells already as planned"


def test_build_flies_to_each_phase(client):
    builder, logs = make_builder(client)
    builder.build([
        Phase("Wall", standpoint=(0.5, -58, 0.5), blocks=[Placement((x, -60, 3), "cobblestone") for x in range(-2, 3)]),
        Phase("Hole", standpoint=(3.5, -58, 0.5), blocks=[Placement((0, -60, 3), "air")]),
    ])
    assert builder.placed == 5 and builder.removed == 1
    assert sorted(client.fake.world) == [(-2, -60, 3), (-1, -60, 3), (1, -60, 3), (2, -60, 3)]
    assert logs[0] == "-- Wall: 5 blocks"
