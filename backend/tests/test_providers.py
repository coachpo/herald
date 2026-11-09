import asyncio
import json
import socket
import ssl
import threading
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from backend.channel_dispatch import DeliveryError, dispatch
from backend.providers import bark, gotify, mqtt, ntfy
from backend.providers import http as provider_http
from backend.target_config import normalize_target_config

@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))])

@pytest.fixture
def transport(monkeypatch):
    requests = []
    response = {"status": 200, "body": {"echo": "DO_NOT_PERSIST_PROVIDER_SECRET"}}
    original = httpx.AsyncClient
    def handle(request):
        requests.append(request)
        return httpx.Response(response["status"], json=response["body"])
    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        return original(**kwargs, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(provider_http.httpx, "AsyncClient", client)
    return requests, response

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,config,path,expected", [
    ("bark", {"server_base_url":"https://push.example/prefix","device_key":"device-secret"}, "/prefix/push", {"device_key":"device-secret","body":"hello 世界","title":"标题"}),
    ("ntfy", {"server_base_url":"https://push.example","topic":"inbox","access_token":"token-secret"}, "/", {"topic":"inbox","message":"hello 世界","title":"标题","priority":4}),
    ("gotify", {"server_base_url":"https://push.example","app_token":"app-secret"}, "/message", {"message":"hello 世界","title":"标题","priority":7}),
])
async def test_http_provider_mapping_and_safe_confirmation(transport, kind, config, path, expected):
    requests, _ = transport
    config = normalize_target_config(kind, config)
    result = await dispatch(kind, config, {"title":"标题","body":"hello 世界","priority":4}, timeout=1)
    assert result == {"http_status":200}
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == path
    assert json.loads(request.content) == expected
    if kind == "ntfy":
        assert request.headers["Authorization"] == "Bearer token-secret"
    if kind == "gotify":
        assert request.headers["X-Gotify-Key"] == "app-secret"
    assert "secret" not in json.dumps(result)

@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 404, 405, 429, 500])
async def test_http_failures_do_not_fallback_or_store_provider_body(transport, status):
    requests, response = transport
    response["status"] = status
    with pytest.raises(DeliveryError, match=f"^http_{status}$"):
        await dispatch("bark", {"server_base_url":"https://push.example","device_key":"secret"}, {"body":"hi"}, timeout=1)
    assert len(requests) == 1
    assert requests[0].method == "POST"

@pytest.mark.asyncio
async def test_dispatch_failure_never_echoes_transport_secrets(monkeypatch):
    async def fail(*_a, **_k):
        raise RuntimeError("https://user:password@example.com?token=secret")
    monkeypatch.setattr(bark, "send", fail)
    with pytest.raises(DeliveryError, match="^transport_error$"):
        await dispatch("bark", {}, {}, timeout=1)

@pytest.mark.asyncio
async def test_timeout_is_bounded_and_safe(monkeypatch):
    async def block(*_a, **_k):
        await asyncio.sleep(10)
    monkeypatch.setattr(ntfy, "send", block)
    with pytest.raises(DeliveryError, match="^timeout$"):
        await dispatch("ntfy", {}, {}, timeout=0.01)

@pytest.mark.asyncio
async def test_blocked_host_never_reaches_transport(monkeypatch, transport):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(DeliveryError, match="^destination_blocked$"):
        await dispatch("gotify", {"server_base_url":"https://push.example","app_token":"secret"}, {"body":"hi"}, timeout=1)
    assert not transport[0]

@pytest.mark.asyncio
async def test_slow_dns_does_not_block_other_target_or_send_after_timeout(monkeypatch, transport):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def check(url):
        if "slow.example" in url:
            started.set()
            release.wait(2)
            finished.set()

    monkeypatch.setattr(provider_http, "assert_ssrf_safe", check)
    loop = asyncio.get_running_loop()
    before = loop.time()
    slow = asyncio.create_task(dispatch("bark", {"server_base_url":"https://slow.example", "device_key":"key"}, {"body":"slow"}, timeout=0.05))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        result = await dispatch("bark", {"server_base_url":"https://fast.example", "device_key":"key"}, {"body":"fast"}, timeout=0.5)
        assert result == {"http_status":200}
        assert loop.time() - before < 0.5
        with pytest.raises(DeliveryError, match="^timeout$"):
            await slow
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
        if not slow.done():
            slow.cancel()
            await asyncio.gather(slow, return_exceptions=True)
    # Completion of the abandoned DNS lookup cannot resume the cancelled sender.
    assert [request.url.host for request in transport[0]] == ["fast.example"]

@pytest.mark.parametrize("kind,config", [
    ("bark", {"server_base_url":"https://push.example","device_key":"k","default_payload_json":{}}),
    ("mqtt", {"broker_host":"broker.example","topic":"x","tls_insecure":True}),
    ("mqtt", {"broker_host":"broker.example","topic":"x/+"}),
    ("mqtt", {"broker_host":"broker.example","topic":"x","username":"a"}),
    ("ntfy", {"server_base_url":"https://push.example","topic":"../../outside"}),
    ("gotify", {"server_base_url":"https://u:password@push.example","app_token":"key"}),
    ("gotify", {"server_base_url":"https://push.example/?key=secret","app_token":"key"}),
])
def test_reject_legacy_or_unsafe_configuration(kind, config):
    with pytest.raises((ValidationError, ValueError)):
        normalize_target_config(kind, config)

def test_mqtt_defaults():
    config = normalize_target_config("mqtt", {"broker_host":"broker.example","topic":"inbox"})
    assert config == {"broker_host":"broker.example","broker_port":1883,"topic":"inbox","tls":False,"qos":1,"retain":False}

@pytest.mark.parametrize("qos", [0, 1, 2])
def test_mqtt_waits_for_selected_qos_confirmation_and_verifies_tls(monkeypatch, qos):
    import paho.mqtt.client as paho
    calls = []
    info = SimpleNamespace(rc=0, published=False)
    info.is_published = lambda: info.published
    class Client:
        def __init__(self, *_a, **kwargs):
            assert kwargs["reconnect_on_failure"] is False
            self.on_connect = None
            self.connected = False
        def username_pw_set(self, username, password):
            calls.append(("auth", username, password))
        def tls_set_context(self, context):
            assert context.verify_mode == ssl.CERT_REQUIRED
            assert context.check_hostname is True
            calls.append(("tls",))
        def connect(self, host, port, keepalive):
            calls.append(("connect", host, port, keepalive))
            return 0
        def loop(self, timeout):
            assert 0 < timeout <= 0.1
            if not self.connected:
                self.connected = True
                self.on_connect(self, None, None, SimpleNamespace(is_failure=False), None)
            else:
                info.published = True
            calls.append(("loop",))
            return 0
        def publish(self, topic, payload, qos, retain):
            calls.append(("publish", topic, payload, qos, retain))
            return info
        def disconnect(self):
            calls.append(("disconnect",))
    monkeypatch.setattr(paho, "Client", Client)
    def forbidden(*_a, **_k):
        raise AssertionError("must not alter global socket timeout")
    monkeypatch.setattr(socket, "setdefaulttimeout", forbidden)
    config = normalize_target_config("mqtt", {"broker_host":"broker.example","topic":"inbox","qos":qos,"tls":True,"username":"owner","password":"secret"})
    assert mqtt._publish(config, {"body":"你好"}, timeout=1) == {"mqtt_qos":qos}
    assert ("publish", "inbox", "你好".encode(), qos, False) in calls
    assert sum(c[0] == "loop" for c in calls) == 2
    assert calls[-1] == ("disconnect",)

class FakeProcess:
    def __init__(self):
        self.pid = None
        self.alive = False
        self.terminated = False
        self.joined = False
        self.closed = False
    def start(self):
        self.pid = 1
        self.alive = True
    def is_alive(self):
        return self.alive
    def terminate(self):
        self.terminated = True
        self.alive = False
    def kill(self):
        self.alive = False
    def join(self, **_kwargs):
        self.joined = True
    def close(self):
        self.closed = True

@pytest.fixture
def mqtt_process(monkeypatch):
    process = FakeProcess()
    connection = SimpleNamespace(poll=lambda:False, close=lambda:None)
    context = SimpleNamespace(Pipe=lambda **_kwargs:(connection,connection), Process=lambda **_kwargs:process)
    monkeypatch.setattr(mqtt.multiprocessing, "get_context", lambda _method: context)
    return process

@pytest.mark.asyncio
async def test_mqtt_timeout_stops_attempt_before_return(mqtt_process):
    with pytest.raises(DeliveryError, match="^timeout$"):
        await mqtt.send({}, {}, timeout=0.01)
    assert mqtt_process.terminated and mqtt_process.joined and mqtt_process.closed

@pytest.mark.asyncio
async def test_mqtt_cancellation_stops_attempt_before_retry(mqtt_process):
    task = asyncio.create_task(mqtt.send({}, {}, timeout=10))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert mqtt_process.terminated and mqtt_process.joined and mqtt_process.closed

def test_mqtt_child_sanitizes_credentials_in_exceptions(monkeypatch):
    messages = []
    connection = SimpleNamespace(send=messages.append, close=lambda:None)
    def fail(*_args):
        raise RuntimeError("secret password")
    monkeypatch.setattr(mqtt, "_publish", fail)
    mqtt._child(connection, {}, {}, 1)
    assert messages == [(False, "mqtt_transport_error")]

@pytest.mark.asyncio
async def test_real_mqtt_child_fails_closed_without_network():
    # Literal loopback resolves locally in the child and is rejected before connect.
    with pytest.raises(DeliveryError, match="^destination_blocked$"):
        await mqtt.send({"broker_host":"127.0.0.1"}, {"body":"never sent"}, timeout=3)
