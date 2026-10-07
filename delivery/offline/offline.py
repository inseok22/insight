#!/usr/bin/env python3
"""Offline delivery tooling; only `bundle` accesses public image/package registries."""
import argparse
import base64
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
SERVICES = {'web', 'backend', 'mariadb', 'grafana', 'prometheus', 'dcgm'}


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def password_hash(password):
    salt = secrets.token_bytes(8)
    return '{SSHA}' + base64.b64encode(hashlib.sha1(password.encode() + salt).digest() + salt).decode()


def read_manifest(path):
    data = json.loads(path.read_text())
    if data.get('platform') not in ('linux/amd64', 'linux/arm64') or set(data.get('images', {})) != SERVICES:
        raise ValueError('Manifest requires platform linux/amd64 or linux/arm64 and all six images')
    for name, image in data['images'].items():
        if not isinstance(image, str) or 'REPLACE' in image or any(c.isspace() for c in image) or image.startswith('-'):
            raise ValueError(f'{name}: replace the placeholder with a tested image reference')
        if ':' not in image.rsplit('/', 1)[-1] or image.endswith(':latest'):
            raise ValueError(f'{name}: use an explicit version tag (or digest)')
    return data


def metric_url(value):
    p = urllib.parse.urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('Metrics URL must be HTTP(S), without credentials/query/fragment')
    # Access validates malformed ports too.
    _ = p.port
    if any(c.isspace() for c in value):
        raise ValueError('Metrics URL must not contain whitespace')
    return p


def dashboard(uid, title, panels, gpu=False):
    items = []
    for i, (label, expr, unit) in enumerate(panels):
        items.append({'id': i + 1, 'title': label, 'type': 'timeseries',
                      'datasource': {'type': 'prometheus', 'uid': 'metrics'},
                      'gridPos': {'x': (i % 2) * 12, 'y': (i // 2) * 8, 'w': 12, 'h': 8},
                      'targets': [{'refId': 'A', 'expr': expr, 'legendFormat': '{{gpu}} {{model_name}}'}],
                      'fieldConfig': {'defaults': {'unit': unit}, 'overrides': []}})
    return {'uid': uid, 'title': title, 'schemaVersion': 39, 'version': 1,
            'editable': False, 'refresh': '15s', 'time': {'from': 'now-30m', 'to': 'now'},
            'templating': {'list': [{'name': 'gpu', 'type': 'custom', 'query': '0,1,2,3,4,5,6,7',
                                    'current': {'text': '0', 'value': '0'}}] if gpu else []},
            'panels': items}


def render(folder, manifest, host, llm_url, admin_hash, port=8080):
    host = str(ipaddress.IPv4Address(host))
    if not 1024 <= port <= 65535:
        raise ValueError('Web port must be between 1024 and 65535')
    metrics = metric_url(llm_url)
    folder.mkdir(parents=True, exist_ok=True)
    base = f'http://{host}:{port}'
    # Reconfiguration preserves credentials and existing DB volumes.
    secret_file = folder / 'credentials.json'
    if secret_file.exists():
        credentials = json.loads(secret_file.read_text())
    else:
        credentials = {key: secrets.token_hex(32) for key in ('root', 'db', 'jwt')}
        private_json(secret_file, credentials)
    env = {
        'PRODUCT_PROFILE': 'llm', 'MONITORING_SCOPE': 'gpu_llm', 'TERMINAL_ENABLED': 'false',
        'LSC_SYNC_ENABLED': 'false', 'RESOURCE_RESERVATIONS_ENABLED': 'false',
        'SECRET_KEY': credentials['jwt'], 'INITIAL_ADMIN_USERNAME': 'admin',
        'INITIAL_ADMIN_PASSWORD_HASH': admin_hash, 'CORS_ORIGINS': base,
        'ADMIN_DATABASE_URL': f"mysql+pymysql://insight:{credentials['db']}@mariadb:3306/insight_admin?charset=utf8mb4",
        'USER_DATABASE_URL': f"mysql+pymysql://insight:{credentials['db']}@mariadb:3306/desk_users?charset=utf8mb4",
        'GPU_URL': json.dumps([{'id': f'gpu-{n}', 'name': f'GPU {n}',
                               'url': f'{base}/grafana/d/dcgm/gpu?var-gpu={n}&kiosk'} for n in range(8)]),
        'VLLM_URL': json.dumps([{'id': 'llm', 'name': 'LLM Dashboard',
                                'url': f'{base}/grafana/d/llm/llm?kiosk'}]),
    }
    # JSON env values do not need shell interpolation. Compose env_file uses quoted values.
    write_private(folder / 'backend.env', ''.join(f"{k}='{v}'\n" for k, v in env.items()))
    write_private(folder / 'db.env', f"MARIADB_ROOT_PASSWORD={credentials['root']}\n")
    # MariaDB accepts mysql_native_password hashes, so no DB user password in the init SQL.
    db_hash = '*' + hashlib.sha1(hashlib.sha1(credentials['db'].encode()).digest()).hexdigest().upper()
    sql = "CREATE DATABASE IF NOT EXISTS insight_admin;\nCREATE DATABASE IF NOT EXISTS desk_users;\n"
    sql += f"CREATE USER IF NOT EXISTS 'insight'@'%' IDENTIFIED BY PASSWORD '{db_hash}';\n"
    sql += "GRANT ALL ON insight_admin.* TO 'insight'@'%';\nGRANT ALL ON desk_users.* TO 'insight'@'%';\n"
    (folder / 'init.sql').write_text(sql)
    prom = {'global': {'scrape_interval': '15s'}, 'scrape_configs': [
        {'job_name': 'dcgm', 'static_configs': [{'targets': ['dcgm:9400']}]},
        {'job_name': 'llm', 'scheme': metrics.scheme, 'metrics_path': metrics.path or '/metrics',
         'static_configs': [{'targets': [metrics.netloc]}]},
    ]}
    write_json(folder / 'prometheus.json', prom)
    write_json(folder / 'provisioning/datasources/metrics.yaml', {
        'apiVersion': 1, 'datasources': [{'name': 'Metrics', 'uid': 'metrics', 'type': 'prometheus',
         'access': 'proxy', 'url': 'http://prometheus:9090', 'isDefault': True, 'editable': False}]})
    write_json(folder / 'provisioning/dashboards/provider.yaml', {
        'apiVersion': 1, 'providers': [{'name': 'offline', 'type': 'file',
         'options': {'path': '/var/lib/grafana/dashboards'}, 'allowUiUpdates': False}]})
    selector = '{job="dcgm",gpu="$gpu"}'
    write_json(folder / 'dashboards/dcgm.json', dashboard('dcgm', 'DCGM · GPU', [
        ('GPU utilization', 'DCGM_FI_DEV_GPU_UTIL' + selector, 'percent'),
        ('GPU memory used', 'DCGM_FI_DEV_FB_USED' + selector, 'decmbytes'),
        ('Temperature', 'DCGM_FI_DEV_GPU_TEMP' + selector, 'celsius'),
        ('Power', 'DCGM_FI_DEV_POWER_USAGE' + selector, 'watt'),
    ], gpu=True))
    write_json(folder / 'dashboards/llm.json', dashboard('llm', 'LLM Dashboard · vLLM metrics', [
        ('Metrics endpoint up', 'up{job="llm"}', 'short'),
        ('Running requests', 'vllm:num_requests_running{job="llm"}', 'short'),
        ('Waiting requests', 'vllm:num_requests_waiting{job="llm"}', 'short'),
        ('Output tokens / second', 'sum by (model_name) (rate(vllm:generation_tokens_total{job="llm"}[5m]))', 'ops'),
        ('Time to first token · p95', 'histogram_quantile(0.95, sum by (le, model_name) (rate(vllm:time_to_first_token_seconds_bucket{job="llm"}[5m])))', 's'),
        ('Request latency · p95', 'histogram_quantile(0.95, sum by (le, model_name) (rate(vllm:e2e_request_latency_seconds_bucket{job="llm"}[5m])))', 's'),
    ]))
    def service(name, **kwargs):
        return {'image': manifest['images'][name], 'platform': manifest['platform'],
                'pull_policy': 'never', 'restart': 'unless-stopped', **kwargs}
    services = {
        'mariadb': service('mariadb', env_file=['db.env'],
            volumes=['db:/var/lib/mysql', './init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro'],
            healthcheck={'test': ['CMD', 'healthcheck.sh', '--connect', '--innodb_initialized'],
                         'interval': '5s', 'timeout': '5s', 'retries': 30}),
        'backend': service('backend', env_file=['backend.env'],
            depends_on={'mariadb': {'condition': 'service_healthy'}},
            healthcheck={'test': ['CMD', 'python', '-c',
                "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)"],
                'interval': '5s', 'timeout': '5s', 'retries': 30}),
        'web': service('web', ports=[f'{host}:{port}:80'],
            depends_on={'backend': {'condition': 'service_healthy'}, 'grafana': {'condition': 'service_started'}}),
        'grafana': service('grafana', environment={
            'GF_SERVER_ROOT_URL': base + '/grafana/', 'GF_SERVER_SERVE_FROM_SUB_PATH': 'true',
            'GF_SECURITY_ALLOW_EMBEDDING': 'true', 'GF_USERS_ALLOW_SIGN_UP': 'false',
            'GF_ANALYTICS_REPORTING_ENABLED': 'false', 'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false',
            'GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES': 'false', 'GF_PLUGINS_PREINSTALL_DISABLED': 'true',
            'GF_PLUGINS_PUBLIC_KEY_RETRIEVAL_DISABLED': 'true',
            'GF_AUTH_ANONYMOUS_ENABLED': 'false'},
            ports=['127.0.0.1:13000:3000'],
            volumes=['grafana:/var/lib/grafana', './provisioning:/etc/grafana/provisioning:ro',
                     './dashboards:/var/lib/grafana/dashboards:ro']),
        'prometheus': service('prometheus', ports=['127.0.0.1:19090:9090'],
            command=['--config.file=/etc/prometheus/prometheus.json', '--storage.tsdb.path=/prometheus',
                     '--storage.tsdb.retention.time=15d'],
            volumes=['./prometheus.json:/etc/prometheus/prometheus.json:ro', 'metrics:/prometheus']),
        'dcgm': service('dcgm', cap_add=['SYS_ADMIN'],
            deploy={'resources': {'reservations': {'devices': [
                {'driver': 'nvidia', 'count': 'all', 'capabilities': ['gpu']}]}}}),
    }
    write_json(folder / 'compose.json', {'name': 'insight-gpu-llm', 'services': services,
                                       'volumes': {'db': {}, 'grafana': {}, 'metrics': {}}})
    private_json(folder / 'site.json', {'host': host, 'llm_url': llm_url, 'port': port, 'admin_hash': admin_hash})


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(value)
    path.chmod(0o600)


def private_json(path, value):
    write_private(path, json.dumps(value) + '\n')


def compose(folder, *args, **kwargs):
    return run(['docker', 'compose', '-f', str(folder / 'compose.json'), *args], **kwargs)


def configure(args):
    manifest = read_manifest(args.manifest)
    prior = json.loads((args.runtime / 'site.json').read_text()) if (args.runtime / 'site.json').exists() else {}
    host = args.host or input(f"GPU/관제 서버 내부 IPv4 [{prior.get('host', '')}]: ").strip() or prior.get('host')
    ipaddress.IPv4Address(host)
    previous_url = prior.get('llm_url')
    if previous_url and prior.get('host') != host:
        parsed = metric_url(previous_url)
        if parsed.hostname == prior.get('host'):
            netloc = host + (f':{parsed.port}' if parsed.port else '')
            previous_url = urllib.parse.urlunsplit(parsed._replace(netloc=netloc))
    llm_url = args.llm_url or previous_url or f'http://{host}:8000/metrics'
    if 'admin_hash' in prior:
        admin_hash = prior['admin_hash']
    else:
        password = getpass.getpass('Insight admin 초기 비밀번호 (12자 이상): ')
        if len(password) < 12 or password != getpass.getpass('비밀번호 확인: '):
            raise ValueError('Password must match and have at least 12 characters')
        admin_hash = password_hash(password)
    render(args.runtime, manifest, host, llm_url, admin_hash, args.port or prior.get('port', 8080))
    compose(args.runtime, 'config', '--quiet')
    print('설정 생성 완료. LLM 기본값 8000/metrics는 추정값이며 check로 확인해야 합니다.')


def checksum(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bundle(args):
    manifest = read_manifest(args.manifest)
    repo = ROOT.parents[1]
    out = args.output.resolve()
    if out.exists():
        raise ValueError('Choose a new output directory; existing bundles are never overwritten')
    run(['docker', 'info'], stdout=subprocess.DEVNULL)
    out.mkdir(parents=True)
    try:
        # An allowlist prevents copying local .env, DB files, existing delivery credentials or customer data.
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            for name in ('frontend/src', 'frontend/public', 'backend/app'):
                shutil.copytree(repo / name, stage / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for name in ('frontend/package.json', 'frontend/package-lock.json', 'frontend/index.html',
                         'frontend/tsconfig.json', 'frontend/tsconfig.app.json', 'frontend/tsconfig.node.json',
                         'frontend/vite.config.ts', 'backend/requirements.txt',
                         'delivery/offline/Dockerfile.web', 'delivery/offline/Dockerfile.backend',
                         'delivery/offline/nginx.conf'):
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(repo / name, target)
            for name in ('web', 'backend'):
                run(['docker', 'buildx', 'build', '--load', '--platform', manifest['platform'],
                     '-f', str(stage / f'delivery/offline/Dockerfile.{name}'),
                     '-t', manifest['images'][name], str(stage)])
        for name in sorted(SERVICES - {'web', 'backend'}):
            run(['docker', 'pull', '--platform', manifest['platform'], manifest['images'][name]])
        ids = {}
        for name, ref in manifest['images'].items():
            info = json.loads(run(['docker', 'image', 'inspect', ref], capture_output=True).stdout)[0]
            if f"{info['Os']}/{info['Architecture']}" != manifest['platform']:
                raise ValueError(f'Wrong architecture for {name}')
            ids[name] = info['Id']
        manifest['image_ids'] = ids
        write_json(out / 'images.json', manifest)
        run(['docker', 'save', '-o', str(out / 'images.tar'), *manifest['images'].values()])
        for name in ('offline.py', 'README.md', 'feature-inventory.md', 'host-report.sh'):
            shutil.copyfile(ROOT / name, out / name)
        write_json(out / 'SHA256.json', {p.name: checksum(p) for p in out.iterdir() if p.is_file()})
        print(f'이미지 반입 묶음 생성: {out}\n호스트 설치 파일은 별도입니다. Ubuntu/GPU에서 단절망 인수 테스트 후 반입하세요.')
    except BaseException:
        (out / 'INCOMPLETE').write_text('Bundle generation failed. Do not deliver.\n')
        raise


def verify_bundle(folder):
    if (folder / 'INCOMPLETE').exists():
        raise ValueError('Incomplete bundle')
    checks = json.loads((folder / 'SHA256.json').read_text())
    if not {'images.json', 'images.tar', 'offline.py', 'README.md'} <= set(checks):
        raise ValueError('Bundle checksum manifest is incomplete')
    for name, expected in checks.items():
        if Path(name).name != name or checksum(folder / name) != expected:
            raise ValueError(f'Checksum mismatch: {name}')


def load(args):
    verify_bundle(ROOT)
    manifest = read_manifest(args.manifest)
    # Only permit the manifest protected by the bundle checksum.
    if args.manifest.resolve() != (ROOT / 'images.json').resolve():
        raise ValueError('Load requires the bundled images.json')
    check_host(manifest)
    run(['docker', 'load', '-i', str(ROOT / 'images.tar')])
    check_images(manifest)


def check_host(manifest):
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
    if platform.system() != 'Linux' or manifest['platform'] != f'linux/{arch}':
        raise ValueError('Host OS/architecture differs from the bundle')
    run(['docker', 'info'], stdout=subprocess.DEVNULL)
    run(['docker', 'compose', 'version'])
    result = run(['nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'], capture_output=True)
    if len(result.stdout.strip().splitlines()) != 8:
        raise ValueError('Expected eight physical GPUs; check driver, hardware and MIG configuration')


def check_images(manifest):
    for name, ref in manifest['images'].items():
        info = json.loads(run(['docker', 'image', 'inspect', ref], capture_output=True).stdout)[0]
        if info['Id'] != manifest.get('image_ids', {}).get(name):
            raise ValueError(f'{name}: image differs from the bundle, run load first')


def wait_http(url, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return json.load(response)
        except (OSError, ValueError):
            time.sleep(2)
    raise ValueError('Service did not become ready within the timeout')


def up(args):
    manifest = read_manifest(args.manifest)
    check_host(manifest)
    check_images(manifest)
    compose(args.runtime, 'config', '--quiet')
    # Grafana is initially loopback-only; reset its bootstrap password before publishing the web proxy.
    first = not (args.runtime / 'grafana-initialized').exists()
    password = None
    if first:
        password = getpass.getpass('Grafana admin 초기 비밀번호 (12자 이상): ')
        if len(password) < 12 or password != getpass.getpass('비밀번호 확인: '):
            raise ValueError('Password must match and have at least 12 characters')
        compose(args.runtime, 'stop', 'web')
    compose(args.runtime, 'up', '-d', '--force-recreate', '--no-build', '--pull', 'never',
            'mariadb', 'backend', 'grafana', 'prometheus', 'dcgm')
    wait_http('http://127.0.0.1:13000/grafana/api/health')
    if first:
        compose(args.runtime, 'exec', '-T', 'grafana', 'grafana', 'cli',
                '--homepath', '/usr/share/grafana', '--config', '/etc/grafana/grafana.ini',
                'admin', 'reset-admin-password', '--password-from-stdin',
                input=password + '\n', stdout=subprocess.DEVNULL)
        (args.runtime / 'grafana-initialized').touch()
    compose(args.runtime, 'up', '-d', '--force-recreate', '--no-build', '--pull', 'never', 'web')
    site = json.loads((args.runtime / 'site.json').read_text())
    wait_http(f"http://{site['host']}:{site['port']}/api/v1/health")
    print('서비스 기동 완료. 수집 확인: python3 offline.py check')


def query(expression):
    url = 'http://127.0.0.1:19090/api/v1/query?' + urllib.parse.urlencode({'query': expression})
    data = wait_http(url, seconds=10)
    if data.get('status') != 'success':
        raise ValueError('Prometheus query failed')
    return data['data']['result']


def collected(expressions, expected=1):
    return all((rows := query(expr)) and float(rows[0]['value'][1]) == expected for expr in expressions)


def check(args):
    compose(args.runtime, 'ps')
    # Up alone is insufficient: an unrelated HTTP endpoint may expose only generic process metrics.
    if not collected(['up{job="dcgm"}', 'up{job="llm"}']):
        raise ValueError('A metrics endpoint is down. Check the configured IP, port, path and exporter logs')
    if not collected(['count(count by (UUID) (DCGM_FI_DEV_GPU_UTIL{job="dcgm"}))'], 8):
        raise ValueError('DCGM is reachable but eight distinct GPU UUIDs have not been collected')
    gpu_rows = query('count by (gpu) (DCGM_FI_DEV_GPU_UTIL{job="dcgm"})')
    if {row['metric'].get('gpu') for row in gpu_rows} != {str(i) for i in range(8)}:
        raise ValueError('GPU metric indices do not match the eight dashboard tabs (0 through 7)')
    families = ['vllm:num_requests_running', 'vllm:num_requests_waiting', 'vllm:generation_tokens_total',
                'vllm:time_to_first_token_seconds_bucket', 'vllm:e2e_request_latency_seconds_bucket']
    missing = [name for name in families if not query(name + '{job="llm"}')]
    if missing:
        raise ValueError('LLM dashboard metrics missing (engine/version compatibility or no requests yet): ' + ', '.join(missing))
    site = json.loads((args.runtime / 'site.json').read_text())
    product = wait_http(f"http://{site['host']}:{site['port']}/api/v1/config/product", seconds=10)
    if set(product.get('features', [])) != {'gpu', 'vllm'}:
        raise ValueError('Unexpected enabled feature set')
    print('PASS: DCGM 8 GPU UUIDs, required LLM metrics and two-feature API configuration. Browser/login checks remain manual.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT / 'images.json')
    p.add_argument('--runtime', type=Path, default=ROOT / 'runtime')
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('configure')
    c.add_argument('--host')
    c.add_argument('--llm-url')
    c.add_argument('--port', type=int)
    b = sub.add_parser('bundle')
    b.add_argument('--output', type=Path, required=True)
    for name in ('load', 'up', 'check'):
        sub.add_parser(name)
    args = p.parse_args()
    args.runtime = args.runtime.resolve()
    try:
        globals()[args.command](args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Subprocess output may contain credentials: do not print captured stdout/stderr.
        print(f'ERROR: {error if not isinstance(error, subprocess.CalledProcessError) else "command failed; check service status"}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
