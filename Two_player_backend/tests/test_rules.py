from app.engine.rules import health_factor


def test_health_speed_thresholds():
    assert health_factor(100) == 1.0
    assert health_factor(75) == 0.9
    assert health_factor(50) == 0.75
    assert health_factor(25) == 0.55
    assert health_factor(0) == 0.0
