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
# to the host running mlmmj (and so to mlmmj_listener.py).

import sys
import os
import requests
import json
import base64
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script called by postfix and sends mail to an mlmmj listener (mlmmj_listener.py).')
    parser.add_argument('nexthop', help='$nexthop from postfix')
    parser.add_argument('--mlmmj', type=str, required=False, help='Host of the mlmmj listener (ip or hostname). Default is to use the MLMMJ_HOST env variable (or "mlmmj" if not set)')
    parser.add_argument('--port', '-p', type=int, required=False, help='Port of the mlmmj listener. Default is to use the MLMMJ_PORT env variable (or 7777 if not set)')
    parser.add_argument('--spool', '-s', type=str, required=False, default='/var/spool/mlmmj', help='Path of the mlmmj directory (default is "/var/spool/mlmmj")')
    args = parser.parse_args()
    if args.mlmmj is None:
        mlmmj_host = os.environ.get('MLMMJ_HOST', 'mlmmj')
    else:
        mlmmj_host = args.mlmmj
    if args.port is None:
        try:
            mlmmj_port = int(os.environ.get('MLMMJ_PORT', 7777))
        except ValueError as e:
            print('MLMMJ_PORT env variable must be an integer, errror:', e)
            sys.exit(1)
    else:
        mlmmj_port = args.port
    # after everything is ok we read the mail from stdin and encode it
    bytes_mail = sys.stdin.buffer.read()
    enc = base64.b64encode(bytes_mail).decode('utf-8')
    # now we finally send the data
    # we want some kind of timeout so we give the listener 5 minutes...
    # should be more than enough
    list_path = os.path.join(args.spool, args.nexthop)
    args = ['-F', '-L', list_path]
    data = {'mlmmj-command': 'mlmmj-receive', 'args': args, 'mail': enc}
    try:
        response = requests.post('http://%s:%d' % (mlmmj_host, mlmmj_port),
        json=data, headers={'host': 'localhost.mlmmj'}, timeout=600)
    except requests.exceptions.RequestException as e:
        print('Error while connecting to mlmmj listener:', e)
        sys.exit(1)
    except requests.exceptions.Timeout as timeoutErr:
        print('receive post timed out, maybe a bug in the image?')
        sys.exit(1)
    # everything worked fine... get response
    if response.status_code != 200:
        print('Got weird return value, probably a bug? The listener should always return 200 status code')
    text = response.text
    # get json data
    try:
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
