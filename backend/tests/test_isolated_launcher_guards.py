"""Guard unit tests only: mocked paths/connections; no SQL or network execution."""
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import stat
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest

spec=importlib.util.spec_from_file_location('isolated_qa_launcher',Path(__file__).resolve().parents[1]/'tools/run_isolated_qa.py')
guard=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=guard
spec.loader.exec_module(guard)

@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def deny(*args,**kwargs): raise AssertionError('Unit tests cannot connect')
    from sqlalchemy.engine import Engine
    monkeypatch.setattr(Engine,'connect',deny)
    monkeypatch.setattr(sqlite3,'connect',deny)
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket.socket,'connect_ex',deny)
    monkeypatch.setattr(socket,'create_connection',deny)

@pytest.fixture
def data():
    root='/tmp/frameora-concurrency-abcdefghijkl'
    return dict(run_id='abcdefghijkl',root=root,socket=root+'/mysql.sock',datadir=root+'/data',files=root+'/images',db_name=guard.DATABASE,db_user='qa_runner',db_password='synthetic-only',server_uuid='11111111-1111-4111-8111-111111111111',server_version='8.0.46')

@pytest.fixture
def local_paths(monkeypatch):
    monkeypatch.setattr(guard,'private_path',lambda value,**kwargs:Path(value))
    monkeypatch.setattr(Path,'read_text',lambda self:'abcdefghijkl')
    monkeypatch.setattr(Path,'is_file',lambda self:True)
    monkeypatch.setattr(Path,'stat',lambda self:NS(st_mode=stat.S_IFSOCK|0o600,st_size=200))


def test_valid_local_manifest_contains_no_environment_fallback(data,local_paths,monkeypatch):
    monkeypatch.setenv('DB_NAME','frameora_db')
    m=guard.validate_manifest(data)
    assert m.db_name==guard.DATABASE
    assert data['db_password'] not in repr(m)

@pytest.mark.parametrize('key,value',[
 ('db_name','frameora_db'),('db_name','other_test'),('db_user','root'),('db_password',''),
 ('root','/home/example/private'),('socket','/var/run/mysqld/mysqld.sock'),
 ('datadir','/var/lib/mysql'),('files','/home/example/gallery'),('run_id','../../bad'),
 ('server_uuid','unknown'),('server_version','8.4.0')])
def test_rejects_unsafe_manifest(data,local_paths,key,value):
    data[key]=value
    with pytest.raises(guard.GuardError):guard.validate_manifest(data)

@pytest.mark.parametrize('key',['db_name','db_user','db_password','socket','files','server_uuid'])
def test_missing_fields_never_fall_back(data,local_paths,key):
    del data[key]
    with pytest.raises(guard.GuardError):guard.validate_manifest(data)


def test_extra_configuration_rejected(data,local_paths):
    data['redis_url']='redis://localhost'
    with pytest.raises(guard.GuardError):guard.validate_manifest(data)


def test_marker_mismatch_rejected(data,local_paths,monkeypatch):
    monkeypatch.setattr(Path,'read_text',lambda self:'wrong-run')
    with pytest.raises(guard.GuardError):guard.validate_manifest(data)

@pytest.mark.parametrize('mode,uid,symlink',[(stat.S_IFREG|0o644,0,False),(stat.S_IFREG|0o600,1,False),(stat.S_IFREG|0o600,0,True)])
def test_private_path_permissions_owner_and_symlinks(monkeypatch,mode,uid,symlink):
    monkeypatch.setattr(guard.os,'getuid',lambda:0)
    monkeypatch.setattr(Path,'resolve',lambda self:self)
    monkeypatch.setattr(Path,'is_symlink',lambda self:symlink)
    monkeypatch.setattr(Path,'stat',lambda self:NS(st_uid=uid,st_mode=mode))
    with pytest.raises(guard.GuardError):guard.private_path('/tmp/test-manifest')


def connection_fixture(m):
    connection=Mock();cursor=connection.cursor.return_value
    cursor.fetchone.return_value=(m.db_name,m.db_user+'@localhost',m.server_uuid,str(m.datadir),str(m.socket),m.server_version,'REPEATABLE-READ',1)
    cursor.fetchall.return_value=[("GRANT USAGE ON *.* TO `qa_runner`@`localhost`",),("GRANT SELECT, INSERT, UPDATE, DELETE ON `frameora_concurrency_test`.* TO `qa_runner`@`localhost`",)]
    return connection,cursor


def test_mock_identity_checks_only_read_operations(data,local_paths,monkeypatch):
    m=guard.validate_manifest(data);monkeypatch.setattr(Path,'resolve',lambda self:self)
    connection,cursor=connection_fixture(m)
    guard.verify_connection(connection,m)
    assert [c.args[0].split()[0] for c in cursor.execute.call_args_list]==['SELECT','SHOW']
    cursor.close.assert_called_once();connection.commit.assert_not_called()

@pytest.mark.parametrize('index,value',[(0,'frameora_db'),(1,'root@localhost'),(2,'wrong-server'),(3,'/var/lib/mysql'),(4,'/run/mysql.sock'),(5,'8.4.0'),(6,'READ-COMMITTED'),(7,2)])
def test_server_identity_and_durability_fail_closed(data,local_paths,monkeypatch,index,value):
    m=guard.validate_manifest(data);monkeypatch.setattr(Path,'resolve',lambda self:self)
    connection,cursor=connection_fixture(m);row=list(cursor.fetchone.return_value);row[index]=value;cursor.fetchone.return_value=row
    with pytest.raises(guard.GuardError):guard.verify_connection(connection,m)
    cursor.fetchall.assert_not_called();cursor.close.assert_called_once()

@pytest.mark.parametrize('grant',[
 'GRANT ALL PRIVILEGES ON *.* TO `qa_runner`@`localhost`',
 'GRANT SELECT ON `frameora_db`.* TO `qa_runner`@`localhost`',
 'GRANT CREATE ON `frameora_concurrency_test`.* TO `qa_runner`@`localhost`',
 'GRANT SELECT, INSERT, UPDATE, DELETE ON `frameora_concurrency_test`.* TO `qa_runner`@`localhost` WITH GRANT OPTION',
 'GRANT `admin_role`@`%` TO `qa_runner`@`localhost`',
 'GRANT SELECT ON `frameora_concurrency_test`.* TO `qa_runner`@`localhost`'])
def test_unsafe_or_insufficient_grants_rejected(data,local_paths,monkeypatch,grant):
    m=guard.validate_manifest(data);monkeypatch.setattr(Path,'resolve',lambda self:self)
    connection,cursor=connection_fixture(m);cursor.fetchall.return_value=[(grant,)]
    with pytest.raises(guard.GuardError):guard.verify_connection(connection,m)


def test_acknowledgement_is_mandatory():
    with pytest.raises(guard.GuardError):guard.load_manifest('/not/read','wrong')


def test_cli_local_only_and_execution_disabled(monkeypatch,capsys):
    monkeypatch.setattr(guard,'load_manifest',Mock())
    verify=Mock(side_effect=AssertionError('No connection allowed'))
    monkeypatch.setattr(guard,'verify_connection',verify)
    args=['--manifest','/private/test.json','--acknowledge',guard.ACK]
    assert guard.main(args+['--preflight-only'])==0
    for scenario in guard.SCENARIOS:assert guard.main(args+['--suite',scenario])==2
    verify.assert_not_called()
    assert 'UNVERIFIED' in capsys.readouterr().out


def test_duplicate_json_fields_rejected(local_paths,monkeypatch):
    monkeypatch.setattr(Path,'read_text',lambda self:'{"db_name":"test","db_name":"frameora_db"}')
    with pytest.raises(guard.GuardError):guard.load_manifest('/private/test.json',guard.ACK)
