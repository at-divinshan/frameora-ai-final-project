"""Deferred integration fixtures. Collection cannot connect or provision resources."""
import socket
import sqlite3
import subprocess
from unittest.mock import Mock
import pytest

@pytest.fixture(autouse=True)
def deny_side_effects(monkeypatch):
    def denied(*args,**kwargs): raise AssertionError('Isolated QA execution has not been approved')
    from sqlalchemy.engine import Engine
    import dotenv
    monkeypatch.setattr(Engine,'connect',denied)
    monkeypatch.setattr(sqlite3,'connect',denied)
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket.socket,'connect_ex',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr(subprocess,'Popen',denied)
    monkeypatch.setattr(dotenv,'dotenv_values',denied)
    monkeypatch.setattr(dotenv,'load_dotenv',denied)

@pytest.fixture
def isolated_sessions():
    pytest.skip('BLOCKED: separately approved identity-guarded MySQL session factory required')

@pytest.fixture
def deterministic_provider():
    # Opaque bytes only, not generated image files. Future storage integration
    # needs separately approved local fixture bytes and an isolated file root.
    return Mock(side_effect=lambda *, count: [f'fixture-{i}'.encode() for i in range(count)])

@pytest.fixture
def forbidden_external_clients():
    def denied(*args,**kwargs): raise AssertionError('Real provider call forbidden')
    return {name:Mock(side_effect=denied) for name in ('stripe','gmail','pollinations','redis')}
