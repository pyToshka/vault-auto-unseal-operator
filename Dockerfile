FROM python:3.11-alpine

LABEL description="Kubernetes Vault auto unseal operator"

ENV APPDIR /app
ENV PYTHONUNBUFFERED 1
RUN mkdir $APPDIR
WORKDIR $APPDIR

COPY . .
# hadolint ignore=DL3018
RUN apk update && apk add --no-cache --virtual .build-deps gcc python3-dev py-configobj linux-headers libc-dev \
    && pip install  --use-deprecated=legacy-resolver --no-cache-dir -r ./requirements.txt \
    && addgroup -S app_grp && adduser -S app -G app_grp \
    && chown -R app:app_grp $APPDIR \
    && apk del .build-deps  \
    && rm -rf /var/cache/apk/*  \
    && rm -rf  /tmp/*

USER app
CMD ["kopf", "run", "--standalone", "/app/create_obj.py", "--verbose"]
