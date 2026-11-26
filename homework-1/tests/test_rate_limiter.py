import threading

from src.app import create_app
from src.utils.rate_limiter import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


# --- RateLimiter unit tests --------------------------------------------------

def test_sliding_window():
    clock = FakeClock()
    limiter = RateLimiter(limit=3, window=60, clock=clock)

    for t, remaining in ((0, 2), (10, 1), (20, 0)):
        clock.now = t
        result = limiter.hit("ip")
        assert result.allowed and result.remaining == remaining

    clock.now = 30
    blocked = limiter.hit("ip")
    assert not blocked.allowed
    assert blocked.retry_after == 30  # the t=0 hit expires at t=60

    clock.now = 60
    assert limiter.hit("ip").allowed  # t=0 hit has expired

    clock.now = 61
    assert limiter.hit("ip").retry_after == 9  # next expiry: t=10 hit at t=70


def test_rejected_requests_do_not_extend_the_block():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    limiter.hit("ip")
    for t in range(1, 60):
        clock.now = t
        assert not limiter.hit("ip").allowed
    clock.now = 60
    assert limiter.hit("ip").allowed


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window=60, clock=FakeClock())
    assert limiter.hit("a").allowed
    assert not limiter.hit("a").allowed
    assert limiter.hit("b").allowed


def test_thread_safety():
    limiter = RateLimiter(limit=100, window=60)
    results = []

    def worker():
        for _ in range(10):
            results.append(limiter.hit("ip").allowed)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(results) == 100


# --- Integration with the app ------------------------------------------------

def test_101st_request_gets_429():
    client = create_app({"TESTING": True}).test_client()
    for _ in range(100):
        assert client.get("/transactions").status_code == 200

    response = client.get("/transactions")
    assert response.status_code == 429
    assert response.get_json()["error"] == "Too Many Requests"
    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["X-RateLimit-Remaining"] == "0"


def test_limit_applies_to_all_routes_and_is_per_ip():
    client = create_app({"TESTING": True, "RATE_LIMIT": 2}).test_client()
    assert client.get("/transactions").headers["X-RateLimit-Remaining"] == "1"
    assert client.post("/transactions", json={}).status_code == 400
    assert client.get("/unknown").status_code == 429
    other_ip = client.get("/transactions", environ_overrides={"REMOTE_ADDR": "10.0.0.2"})
    assert other_ip.status_code == 200


def test_can_be_disabled():
    client = create_app({"TESTING": True, "RATE_LIMIT_ENABLED": False}).test_client()
    responses = [client.get("/transactions") for _ in range(150)]
    assert all(r.status_code == 200 for r in responses)
    assert "X-RateLimit-Limit" not in responses[0].headers
