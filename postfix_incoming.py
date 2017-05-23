#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Fabian Wenzelmann

# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# This script is used for accepting mails from postfix via a pipe transport.
# Usually in mlmmj you invoke /usr/bin/mlmmj-recieve. But the mlmmj is in
# another container. Therefore we invoke this file which sends the mail
# to the host running mlmmj (and so to receive_listener.py).

import sys
import os
import requests
import json

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Error processing incoming mail: nexthop not specified.')
        print('Usage: %s <NEXTHOP>' % sys.argv[0])
        print('This is probably a bug in the docker image - please report!')
        sys.exit(1)
    # read the mail from stdin
    mail = sys.stdin.read()
    # create a json object that we will send to our mlmmj listener
    data = {'nexthop': sys.argv[1], 'mail': mail}
    try:
        # TODO host anpassen
        mlmmj_host = os.environ.get('MLMMJ_HOST', 'mlmmj')
        mlmmj_port = int(os.environ.get('MLMMJ_PORT', 7777))
    except ValueError as e:
        print('MLMMJ_PORT must be an integer, error:', e)
        sys.exit(1)
    # try to send data
    try:
        # we give the other side 5 minutes... that should be plenty of time
        # but we want some timeout
        response = requests.post('http://%s:%d' % (mlmmj_host, mlmmj_port),
            json=data, headers={'host': 'localhost.mlmmj'},
            timeout=600)
    except requests.exceptions.RequestException as e:
        # TODO does not work... if we don't send a response we somehow get this...
        # not sure why
        print('Error while connecting to mlmmj listener:', e)
        sys.exit(1)
    except requests.exceptions.Timeout as timeoutErr:
        print('receive post timed out, maybe a bug in the image?')
        sys.exit(1)
    # everything worked fine
    # encode response
    if response.status_code != 200:
        print('Got weird return value, probably a bug? The listener should always return 200 status code')
    text = response.text
    try:
        # we use the builtin json decoder, not the one from requests
        json_data = json.loads(text)
    except ValueError as e:
        print("Got a weird response, I don't know what happend to the mail, probably check /var/spool/mlmmj/%s/archive (can't parse json)" % sys.argv[1])
        sys.exit(1)
    if 'returncode' not in json_data or 'output' not in json_data or type(json_data['returncode']) != int:
        print("Got a weird response, I don't know what happend to the mail, probably check /var/spool/mlmmj/%s/archive (missing/wrong value in data)" % sys.argv[1])
        sys.exit(1)
    if json_data['returncode'] != 0:
        print('mlmmj-receive returned with an error:', json_data['output'])
        sys.exit(json_data['returncode'])
    print(json_data['output'])
