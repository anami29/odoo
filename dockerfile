FROM odoo:18.0

USER root

RUN apt-get update && apt-get install -y \
    python3-ldap \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY custom_addons /mnt/extra-addons

USER odoo