#!/bin/bash

# ignores empty results
shopt -s nullglob

# we want to use the virtual and transport files, by default they should be
# in /var/spool/mlmmj
# But we also want to share the virtual and transport files with postfix
# and therefore store them in another directory /mlmmj_conf
# to do so we create a symlink
# if the files don't exist we create them
# TODO we should call newaliases in this case: postfix will send out warnings otherwise
# but since they're empty it's not too bad...
# if they exist the .db file should already be there

TRANSPORT="/mlmmj_conf/transport"
VIRTUAL="/mlmmj_conf/virtual"

if [ ! -f "$TRANSPORT" ]; then
  touch "$TRANSPORT"
fi

if [ ! -f "$VIRTUAL" ]; then
  touch "$VIRTUAL"
fi

if [ -z "$POSTFIX_HOST" ]; then
  POSTFIX_HOST="$(/sbin/ip route|awk '/default/ { print $3 }')"
  printf "POSTFIX_HOST not specified, assuming that postfix is reachable on %s\n" "$POSTFIX_HOST"
fi

ln -sf /mlmmj_conf/virtual /var/spool/mlmmj/virtual && \
    ln -sf /mlmmj_conf/transport /var/spool/mlmmj/transport

# we have to change the relayhost in each mailinglist s.t. mlmmj connects to
# the postfix in the postfix container
(IFS='
'
for listdir in `find /var/spool/mlmmj/ -name control -type d`; do
  printf "$POSTFIX_HOST\n" > "$listdir/relayhost"
done)

# start the server and wait for incoming mails...
exec "$@"
