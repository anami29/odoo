FROM odoo:18.0

USER root

RUN apt-get update && apt-get install -y \
    python3-ldap \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages html2text python-magic

COPY custom_addons /mnt/extra-addons
COPY odoo.conf /etc/odoo/odoo.conf

USER odoo

ENTRYPOINT []

CMD sh -c 'odoo \
  --config=/etc/odoo/odoo.conf \
  --db_host="$PGHOST" \
  --db_port="$PGPORT" \
  --db_user="$PGUSER" \
  --db_password="$PGPASSWORD" \
  --http-interface=0.0.0.0 \
  --http-port=${PORT:-8069}'