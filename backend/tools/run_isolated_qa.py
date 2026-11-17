"""Test-only preflight. No connection/execution path is enabled in this release."""
import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
import uuid

ACK = 'I_ACKNOWLEDGE_DISPOSABLE_TEST_ONLY'
DATABASE = 'frameora_concurrency_test'
SCENARIOS = ('duplicate-requests', 'final-credit-contention', 'recovery-races', 'refund-idempotency')

class GuardError(ValueError):
    pass

@dataclass(frozen=True)
class Manifest:
    run_id: str
    root: Path
    socket: Path
    datadir: Path
    files: Path
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    server_uuid: str
    server_version: str


def private_path(value, *, directory=False):
    if not isinstance(value, str):
        raise GuardError('Expected an explicit absolute private path.')
    p = Path(value)
    if not p.is_absolute() or p.resolve() != p or p.is_symlink():
        raise GuardError('Unsafe or symlinked path.')
    try:
        info = p.stat()
    except OSError:
        raise GuardError('Required private path is unavailable.') from None
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise GuardError('Private paths must be owned by the runner and inaccessible to other users.')
    if directory and not stat.S_ISDIR(info.st_mode):
        raise GuardError('Expected a private directory.')
    return p


def validate_manifest(data):
    required = {'run_id','root','socket','datadir','files','db_name','db_user','db_password','server_uuid','server_version'}
    if not isinstance(data, dict) or set(data) != required:
        raise GuardError('Manifest fields are missing or unsupported; environment fallback is forbidden.')
    if not all(isinstance(v,str) and v for v in data.values()):
        raise GuardError('Every manifest field must be explicitly populated.')
    if not re.fullmatch(r'[a-z0-9]{12,32}',data['run_id']):
        raise GuardError('Invalid run identifier.')
    if data['db_name'] != DATABASE or not re.fullmatch(r'qa_[a-z0-9_]{1,24}',data['db_user']):
        raise GuardError('Only the disposable database and restricted qa_ account are allowed.')
    try:
        if str(uuid.UUID(data['server_uuid'])) != data['server_uuid']:
            raise ValueError()
    except ValueError:
        raise GuardError('An exact server UUID is required.') from None
    if data['server_version'] != '8.0.46':
        raise GuardError('This harness targets the reviewed MySQL 8.0.46 version.')
    root = private_path(data['root'],directory=True)
    if root != Path('/tmp') / ('frameora-concurrency-' + data['run_id']):
        raise GuardError('Unexpected disposable root.')
    marker = private_path(str(root / 'isolated-test-marker'))
    if not marker.is_file() or marker.read_text().strip() != data['run_id']:
        raise GuardError('Disposable root marker mismatch.')
    paths = {k: private_path(data[k],directory=k!='socket') for k in ('socket','datadir','files')}
    for key, leaf in [('socket','mysql.sock'),('datadir','data'),('files','images')]:
        if paths[key] != root / leaf:
            raise GuardError('All approved resources must be direct children of the marked root.')
    if not stat.S_ISSOCK(paths['socket'].stat().st_mode):
        raise GuardError('MySQL endpoint must be a private Unix socket, never TCP.')
    return Manifest(**{**data,'root':root,**paths})


def load_manifest(path, acknowledgement):
    if acknowledgement != ACK:
        raise GuardError('Explicit disposable-test acknowledgement required.')
    p = private_path(path)
    if not p.is_file() or p.stat().st_size > 16384:
        raise GuardError('Invalid manifest file.')
    def unique_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise GuardError('Duplicate manifest field.')
            result[key]=value
        return result
    try:
        data=json.loads(p.read_text(),object_pairs_hook=unique_pairs)
    except (OSError,ValueError):
        raise GuardError('Manifest could not be validated.') from None
    return validate_manifest(data)


def verify_connection(connection, manifest):
    """Future guard for EACH new DB-API connection; currently unit-tested with fakes only.

    Caller must establish the validated Unix-socket connection, never the app engine.
    This read-only check grants no execution capability and is not called by the CLI.
    """
    cursor=connection.cursor()
    try:
        cursor.execute('SELECT DATABASE(), CURRENT_USER(), @@server_uuid, @@datadir, @@socket, @@version, @@session.transaction_isolation, @@innodb_flush_log_at_trx_commit')
        row=cursor.fetchone()
        expected=(manifest.db_name,manifest.db_user+'@localhost',manifest.server_uuid)
        if not row or tuple(row[:3]) != expected or Path(row[3]).resolve()!=manifest.datadir or Path(row[4]).resolve()!=manifest.socket or row[5]!=manifest.server_version:
            raise GuardError('Connected database identity does not match the approved manifest.')
        if row[6] != 'REPEATABLE-READ' or row[7] != 1:
            raise GuardError('Unexpected isolation or transaction durability configuration.')
        cursor.execute('SHOW GRANTS FOR CURRENT_USER')
        grants=cursor.fetchall()
        permitted={'SELECT','INSERT','UPDATE','DELETE'}
        found=set()
        for (grant,) in grants:
            if re.fullmatch(r'GRANT USAGE ON \*\.\* TO .+',grant) and 'WITH GRANT OPTION' not in grant:
                continue
            match=re.fullmatch(r'GRANT ([A-Z, ]+) ON `frameora_concurrency_test`\.\* TO .+',grant)
            if not match or 'WITH GRANT OPTION' in grant:
                raise GuardError('Global, role, DDL, grant-option or other-database privileges are forbidden.')
            privileges=set(match[1].split(', '))
            if not privileges <= permitted: raise GuardError('Unexpected database privileges.')
            found |= privileges
        if found != permitted: raise GuardError('Required scoped DML privileges are missing.')
    finally:
        cursor.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--acknowledge',required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only',action='store_true')
    mode.add_argument('--suite',choices=SCENARIOS)
    args=parser.parse_args(argv)
    try:
        load_manifest(args.manifest,args.acknowledge)
        if args.suite:
            raise GuardError('Execution is disabled: database fixtures and fault-injection execution require separate approval.')
    except (GuardError,OSError):
        print('Preflight refused: invalid isolation prerequisites or execution is not approved. No connection opened.')
        return 2
    print('Local preflight PASS. No connection opened; server identity, grants and concurrency remain UNVERIFIED.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
