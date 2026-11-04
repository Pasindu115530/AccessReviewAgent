#!/bin/sh
set -eu
# Only replace this variable: preserve nginx's own $uri, $host, etc.
: "${API_UPSTREAM:?Set API_UPSTREAM to your backend hostname (without https://)}"
envsubst '${API_UPSTREAM}' < /etc/nginx/conf.d/accessreview.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
