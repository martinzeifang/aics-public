# Custom nginx-Image für AICS — bringt nginx.conf direkt mit (kein Bind-Mount).
# Wird parallel zum aics_web-Image über docker-publish.yml gebaut und nach
# ghcr.io/martinzeifang/aics-nginx gepusht.
FROM nginx:1.27-alpine

# Distroless wäre schöner, aber wir brauchen wget für den Healthcheck.
RUN apk add --no-cache wget

COPY nginx.conf /etc/nginx/nginx.conf

# /usr/share/nginx/html wird per compose mit dem aics_frontend Volume gemountet,
# das gleichzeitig von aics_web (UID 1000) beschrieben wird. Docker initialisiert
# leere named Volumes vom ERSTEN Mountpoint mit Inhalt — das ist hier nginx mit
# seinen Default-Files (index.html, 50x.html, root:root). Folge: aics_web kann
# danach nicht reinschreiben.
# Fix: Default-Files entfernen und Ownership auf 1000:999 (aics:aics) setzen,
# damit das Volume harmlos initialisiert wird, egal welcher Container zuerst
# mountet.
RUN rm -rf /usr/share/nginx/html/* && \
    chown -R 1000:999 /usr/share/nginx/html

# Healthcheck (kann von compose überschrieben werden)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --spider http://127.0.0.1/health || exit 1

EXPOSE 80 443
