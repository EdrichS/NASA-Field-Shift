import pytest

from app.data.geometry import FIELD_BUFFER_M, geom_hash, validate

POINT = {"type": "Point", "coordinates": [120.9, 15.6]}
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[120.9, 15.6], [120.91, 15.6], [120.91, 15.61], [120.9, 15.61], [120.9, 15.6]]
    ],
}


def test_hash_ignores_tiny_float_noise_and_key_order():
    noisy = {"coordinates": [120.9000001, 15.5999999], "type": "Point"}
    assert geom_hash(noisy) == geom_hash(POINT)


def test_hash_differs_for_different_places_and_shapes():
    assert geom_hash(POINT) != geom_hash({"type": "Point", "coordinates": [120.95, 15.6]})
    assert geom_hash(POINT) != geom_hash(SQUARE)


def test_hash_is_short_and_stable():
    assert len(geom_hash(POINT)) == 16
    assert geom_hash(POINT) == geom_hash(dict(POINT))
    assert FIELD_BUFFER_M == 250


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        {"type": "Point", "coordinates": [200, 0]},
        {"type": "Point", "coordinates": [0, 95]},
        {"type": "Point", "coordinates": [1]},
        {"type": "Polygon", "coordinates": []},
        "not a geometry",
    ],
)
def test_invalid_geometry_is_rejected(bad):
    with pytest.raises(ValueError):
        validate(bad)
