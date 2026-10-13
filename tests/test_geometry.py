import numpy as np
import pytest

from rhb_led_driver.geometry import arc_points, file_points, normalize, path_points, segment_points


def test_path_spaces_pixels_evenly_through_corners():
    xy = path_points([[0, 0], [10, 0], [10, 10]], 21)
    assert np.allclose(xy[0], [0, 0]) and np.allclose(xy[10], [10, 0]) and np.allclose(xy[-1], [10, 10])
    assert np.allclose(np.hypot(*np.diff(xy, axis=0).T), 1.0)


def test_arc_runs_from_start_to_end():
    xy = arc_points([0, 0], 2.0, 90, -90, 3)
    assert np.allclose(xy, [[0, 2], [2, 0], [0, -2]])


def test_points_file_with_header_and_comments(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("x,y\n# measured\n1,2\n3,4\n")
    assert np.allclose(file_points(f, 2), [[1, 2], [3, 4]])
    with pytest.raises(ValueError, match="2 points"):
        file_points(f, 3)


def test_exactly_one_shape_required(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        segment_points({"name": "a"}, 5, tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        segment_points({"name": "a", "path": [[0, 0], [1, 0]], "arc": {}}, 5, tmp_path)


def test_normalize_keeps_aspect_over_all_segments():
    uv = normalize({"a": np.array([[0.0, 0.0], [100.0, 0.0]]), "b": np.array([[50.0, 25.0]])})
    assert np.allclose(uv["a"], [[0, 0], [1, 0]])
    assert np.allclose(uv["b"], [[0.5, 0.25]])


def test_arc_center_is_the_arc_center_not_its_bounding_box(tmp_path):
    from rhb_led_driver.geometry import segment_center

    raw = {"arc": {"center": [5, 5], "radius": 2, "start_deg": 225, "end_deg": -45}}
    xy = segment_points(raw, 100, tmp_path)
    assert np.allclose(segment_center(raw, xy), [5, 5])
    assert np.allclose(np.hypot(*(xy - [5, 5]).T), 2.0)


def test_full_circle_has_no_doubled_pixel_at_the_seam():
    xy = arc_points([0, 0], 1.0, 90, -270, 4)
    assert np.allclose(xy, [[0, 1], [1, 0], [0, -1], [-1, 0]])


def test_disc_is_a_serpentine_grid_clipped_to_the_circle(tmp_path):
    from rhb_led_driver.geometry import disc_rows, segment_center

    rows = disc_rows(2.0, 1.0)
    assert [len(xs) for xs, _ in rows] == [1, 3, 5, 3, 1]
    assert np.allclose(rows[1][0], [1, 0, -1]) and np.allclose(rows[2][0], [-2, -1, 0, 1, 2])
    raw = {"disc": {"center": [10, 10], "radius": 2.0, "pitch": 1.0, "rows": [1, 3]}}
    xy = segment_points(raw, 8, tmp_path)
    assert np.allclose(xy[0], [11, 11]) and np.allclose(xy[3], [8, 10])
    assert np.allclose(segment_center(raw, xy), [10, 10])
    with pytest.raises(ValueError, match="hold 8 pixels"):
        segment_points(raw, 9, tmp_path)
