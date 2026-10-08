#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s prepare|django|nginx|stop REPO_ROOT RUNTIME_ROOT [DJANGO_PORT] [JBROWSE_PORT]\n' "$0" >&2
}

if [[ $# -lt 3 ]]; then
    usage
    exit 2
fi

mode="$1"
repo_root="${2%/}"
runtime_root="${3%/}"
manual_root="$repo_root/manual_files"
django_root="$repo_root/django2"
venv_root="${GENEDATA_WSL_VENV:-$HOME/.virtualenvs/genedata-jbrowse}"
jbrowse_release="$runtime_root/releases/jbrowse2-v4.3.0"
jbrowse_cache="$repo_root/tmp/jbrowse2-web-v4.3.0"
nginx_config="$runtime_root/nginx.conf"
django_port="${4:-2025}"
jbrowse_port="${5:-18088}"

require_safe_roots() {
    if [[ "$repo_root" != /* || ! -d "$repo_root/.git" ]]; then
        printf 'Invalid repository root: %s\n' "$repo_root" >&2
        exit 1
    fi
    if [[ "$runtime_root" != /home/*/* || "$runtime_root" == "$HOME" ]]; then
        printf 'Runtime root must be a dedicated directory below /home: %s\n' "$runtime_root" >&2
        exit 1
    fi
}

prepare() {
    require_safe_roots
    for command_name in python3 nginx bgzip tabix wslpath; do
        if ! command -v "$command_name" >/dev/null 2>&1; then
            printf 'Missing WSL command: %s\n' "$command_name" >&2
            exit 1
        fi
    done
    if [[ ! -d "$manual_root" ]]; then
        printf 'Manual file directory does not exist: %s\n' "$manual_root" >&2
        exit 1
    fi

    mkdir -p \
        "$runtime_root/derived/jbrowse" \
        "$runtime_root/logs" \
        "$runtime_root/nginx-temp/client" \
        "$runtime_root/nginx-temp/proxy" \
        "$runtime_root/releases" \
        "$runtime_root/www"

    if [[ ! -x "$venv_root/bin/python" ]]; then
        python3 -m venv "$venv_root"
        "$venv_root/bin/python" -m pip install --upgrade pip
        "$venv_root/bin/python" -m pip install -r "$django_root/requirements.txt"
    fi

    if [[ ! -f "$jbrowse_release/index.html" ]]; then
        if [[ -f "$jbrowse_cache/index.html" ]] && \
            [[ "$(tr -d '\r\n' < "$jbrowse_cache/version.txt")" == "4.3.0" ]]; then
            cp -a "$jbrowse_cache" "$jbrowse_release"
        else
            "$repo_root/scripts/build_jbrowse2_web.sh" "$jbrowse_release"
        fi
    fi
    ln -sfn "$jbrowse_release" "$runtime_root/www/jbrowse2"

    # Local development records contain Windows absolute paths. Linux permits
    # backslashes in a filename, so these aliases let pathlib resolve those
    # records while their real targets remain inside MANUAL_FILES_DIR.
    windows_manual_root="$(wslpath -w "$manual_root")"
    while IFS= read -r -d '' source_path; do
        windows_path="${windows_manual_root}\\$(basename "$source_path")"
        ln -sfn "$source_path" "$runtime_root/$windows_path"
    done < <(find "$manual_root" -maxdepth 1 -type f -print0)

    cat > "$nginx_config" <<EOF
worker_processes 1;
pid $runtime_root/nginx.pid;
error_log $runtime_root/logs/nginx-error.log info;

events { worker_connections 256; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log $runtime_root/logs/nginx-access.log;
    sendfile on;
    client_body_temp_path $runtime_root/nginx-temp/client;
    proxy_temp_path $runtime_root/nginx-temp/proxy;

    server {
        listen $jbrowse_port;
        server_name localhost 127.0.0.1;

        location = /jbrowse2 { return 301 /jbrowse2/; }
        location /jbrowse2/ {
            root $runtime_root/www;
            index index.html;
        }
        location /_protected_manual_files/ {
            internal;
            alias $manual_root/;
            gzip off;
            add_header Accept-Ranges bytes always;
            add_header X-Content-Type-Options nosniff always;
        }
        location /_protected_derived_data/ {
            internal;
            alias $runtime_root/derived/;
            gzip off;
            add_header Accept-Ranges bytes always;
            add_header X-Content-Type-Options nosniff always;
        }
        location /gd/api/ {
            proxy_pass http://127.0.0.1:$django_port;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
EOF
    nginx -t -c "$nginx_config" -p "$runtime_root/"
    printf 'JBrowse development runtime prepared at %s\n' "$runtime_root"
}

run_django() {
    require_safe_roots
    : "${GENEDATA_DB_PASSWORD:?GENEDATA_DB_PASSWORD is required}"
    export DJANGO_SETTINGS_MODULE=filemanager.settings
    export GENEDATA_MANUAL_FILES_DIR="$manual_root"
    export GENEDATA_DERIVED_DATA_DIR="$runtime_root/derived"
    export GENEDATA_JBROWSE_DATA_DIR="$runtime_root/derived/jbrowse"
    export GENEDATA_BGZIP_COMMAND=bgzip
    export GENEDATA_TABIX_COMMAND=tabix
    export PYTHONPATH="$django_root"
    printf '%s\n' "$$" > "$runtime_root/django.pid"
    cd "$runtime_root"
    exec "$venv_root/bin/python" "$django_root/manage.py" runserver "127.0.0.1:$django_port" --noreload
}

run_nginx() {
    require_safe_roots
    exec nginx -c "$nginx_config" -p "$runtime_root/" -g 'daemon off;'
}

stop_pidfile() {
    local pidfile="$1"
    local expected="$2"
    [[ -f "$pidfile" ]] || return 0
    local service_pid
    service_pid="$(tr -d '[:space:]' < "$pidfile")"
    if [[ "$service_pid" =~ ^[0-9]+$ && -r "/proc/$service_pid/cmdline" ]]; then
        local command_line
        command_line="$(tr '\0' ' ' < "/proc/$service_pid/cmdline")"
        if [[ "$command_line" == *"$expected"* ]]; then
            kill -TERM "$service_pid"
        else
            printf 'Refusing to stop unexpected process %s: %s\n' "$service_pid" "$command_line" >&2
        fi
    fi
}

stop_services() {
    require_safe_roots
    stop_pidfile "$runtime_root/django.pid" "$django_root/manage.py"
    stop_pidfile "$runtime_root/nginx.pid" "$nginx_config"
}

case "$mode" in
    prepare) prepare ;;
    django) run_django ;;
    nginx) run_nginx ;;
    stop) stop_services ;;
    *) usage; exit 2 ;;
esac
