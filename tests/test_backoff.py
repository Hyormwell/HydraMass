from hydra_reposter.utils.timers import backoff


def test_backoff_range():
    base_wait = 5
    for _ in range(1000):
        total = backoff(base_wait)
        assert base_wait <= total < base_wait + 3