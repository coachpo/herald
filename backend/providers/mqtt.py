"""Bounded MQTT publishing; an attempt owns one short-lived child process.

Paho's blocking DNS/connect calls cannot be cancelled safely in an asyncio
thread. A process lets timeout/shutdown stop that attempt before a retry starts.
There is no MQTT listener, external worker, reconnect loop or persistent client.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import ssl
import time

from ..core.ssrf import SSRFError, assert_host_ssrf_safe
from .errors import DeliveryError


def _publish(config: dict, message: dict, timeout: float) -> dict:
    import paho.mqtt.client as mqtt

    deadline = time.monotonic() + timeout
    assert_host_ssrf_safe(config["broker_host"], block_private_networks=True)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, reconnect_on_failure=False)
    client.connect_timeout = timeout
    if config.get("username"):
        client.username_pw_set(config["username"], config["password"])
    if config.get("tls"):
        client.tls_set_context(ssl.create_default_context())
    connected = False

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        nonlocal connected
        if reason_code.is_failure:
            raise DeliveryError("mqtt_connection_rejected")
        connected = True

    client.on_connect = on_connect
    try:
        code = client.connect(config["broker_host"], config["broker_port"], keepalive=30)
        if code != mqtt.MQTT_ERR_SUCCESS:
            raise DeliveryError("mqtt_connection_failed")
        while not connected:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if client.loop(timeout=min(0.1, remaining)) != mqtt.MQTT_ERR_SUCCESS:
                raise DeliveryError("mqtt_connection_failed")
        info = client.publish(config["topic"], payload=message["body"].encode("utf-8"),
                              qos=config["qos"], retain=config["retain"])
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise DeliveryError("mqtt_publish_failed")
        while not info.is_published():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if client.loop(timeout=min(0.1, remaining)) != mqtt.MQTT_ERR_SUCCESS:
                raise DeliveryError("mqtt_publish_failed")
        return {"mqtt_qos": config["qos"]}
    finally:
        client.disconnect()


def _child(connection, config: dict, message: dict, timeout: float):
    try:
        connection.send((True, _publish(config, message, timeout)))
    except SSRFError:
        connection.send((False, "destination_blocked"))
    except TimeoutError:
        connection.send((False, "timeout"))
    except DeliveryError as error:
        connection.send((False, error.code))
    except Exception:
        connection.send((False, "mqtt_transport_error"))
    finally:
        connection.close()


async def send(config: dict, message: dict, *, timeout: float) -> dict:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, config, message, timeout), daemon=True)
    try:
        process.start()
        sender.close()
        deadline = time.monotonic() + timeout
        while not receiver.poll():
            if time.monotonic() >= deadline:
                raise DeliveryError("timeout")
            if not process.is_alive():
                raise DeliveryError("mqtt_process_failed")
            await asyncio.sleep(0.01)
        try:
            ok, result = receiver.recv()
        except EOFError:
            raise DeliveryError("mqtt_process_failed") from None
        if not ok:
            raise DeliveryError(result)
        return result
    finally:
        sender.close()
        receiver.close()
        # No publishing process survives cancellation, timeout or worker shutdown.
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
