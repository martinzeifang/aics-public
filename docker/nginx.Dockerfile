# Custom nginx-Image für AICS — bringt nginx.conf direkt mit (kein Bind-Mount).
# Wird parallel zum aics_web-Image über docker-publish.yml gebaut und nach
# ghcr.io/martinzeifang/aics-nginx gepusht.
#
# #1476: unprivileged Basis-Image (läuft nativ als UID 101, lauscht auf 8080/8443).
# Damit sind read_only-FS + cap_drop:ALL + no-new-privileges + tmpfs konfliktfrei —
# kein root-Entrypoint-chown, kein NET_BIND_SERVICE (Bind nur auf Ports >1024).
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Build-Schritte brauchen root; am Ende wieder auf den nginx-User (101) zurück.
USER root

# wget (GNU) für den Healthcheck (busybox-wget kennt --spider nicht).
RUN apk add --no-cache wget

COPY nginx.conf /etc/nginx/nginx.conf

# /usr/share/nginx/html wird per compose mit dem aics_frontend Volume gemountet,
# das gleichzeitig von aics_web (UID 1000) beschrieben wird. Default-Files entfernen
# und Ownership auf 1000:999 (aics:aics) setzen, damit das Volume harmlos
# initialisiert wird, egal welcher Container zuerst mountet.
RUN rm -rf /usr/share/nginx/html/* && \
    chown -R 1000:999 /usr/share/nginx/html

# Healthcheck gegen den unprivileged HTTP-Port (8080).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --spider http://127.0.0.1:8080/health || exit 1

EXPOSE 8080 8443

# Zurück auf den unprivilegierten nginx-User (101) — Container läuft nicht als root.
USER 101
