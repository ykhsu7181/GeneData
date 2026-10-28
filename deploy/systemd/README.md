# GeneData systemd + Gunicorn deployment

This directory records the production process layout accepted for release
`d8312dd` on 2026-10-28. It intentionally contains no production secrets.

## Install and configure

1. Install the pinned backend dependencies with the production Python:

   ```bash
   /home/Software/anaconda3/envs/django2_env/bin/python3.9 \
     -m pip install -r django2/requirements.txt
   ```

2. Copy `genedata-production.env.example` to the host-only configuration path,
   populate the secrets, and restrict it:

   ```bash
   install -o rdcheng -g labuser -m 600 \
     deploy/systemd/genedata-production.env.example \
     /home/labuser/rdcheng/gd/config/genedata-production.env
   ```

3. Update `WorkingDirectory` in `genedata.service.example` to the immutable
   backend release being deployed. Install the unit as root:

   ```bash
   install -o root -g root -m 644 \
     deploy/systemd/genedata.service.example \
     /etc/systemd/system/genedata.service
   systemd-analyze verify /etc/systemd/system/genedata.service
   systemctl daemon-reload
   ```

## Cut over and verify

Keep the existing backend available until the release passes a separate-port
Gunicorn canary. Before starting the unit, stop the old process and confirm
port 2025 is free. Then run:

```bash
systemctl start genedata.service
systemctl status genedata.service --no-pager --full
ss -ltnp | grep ':2025[[:space:]]'
```

Verify the public catalog and a protected Range response through Nginx:

```bash
curl --fail --silent --show-error \
  'https://riceome.hzau.edu.cn/gd/api/v1/files/?page_size=1' \
  >/dev/null

curl --fail --silent --show-error --range 0-99 \
  'https://riceome.hzau.edu.cn/gd/api/v1/files/FAI_957/content/' \
  -o /tmp/FAI_957-first-100.bin
test "$(wc -c < /tmp/FAI_957-first-100.bin)" -eq 100
```

Only after those checks pass, enable boot startup:

```bash
systemctl enable genedata.service
systemctl is-active genedata.service
systemctl is-enabled genedata.service
```

The accepted initial topology uses one Gunicorn worker and four threads.
Introduce a shared cache such as Redis and revalidate throttling before adding
more worker processes.

## Roll back

Stop the unit, load the protected production environment, and start the last
accepted backend command as `rdcheng`. Never store the populated environment
file, token plaintext, or database credentials in Git.
