#!/bin/sh
set -eu
: "${API_UPSTREAM:=backend:8000}"
envsubst '${API_UPSTREAM}' < /etc/nginx/conf.d/accessreview.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
