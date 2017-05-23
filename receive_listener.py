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

from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
import json
import subprocess

def call_cmd(args, mail_body):
    # TODO fails
    byte_array = bytearray(mail_body, 'utf-8', 'strict')
    returncode = 0
    try:
        output = subprocess.check_output(
            args, stderr=subprocess.STDOUT, input=byte_array)
    except subprocess.CalledProcessError as e:
        output = e.output
        returncode = e.returncode
    try:
        output = output.decode("utf-8", "replace")
    except AttributeError:
        pass
    return returncode, output

class PostfixHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)
        mlmmj_resp = ''
        succ = True
        try:
            post_body = post_body.decode('utf-8')
        except UnicodeDecodeError as e:
            mlmmj_resp = str(e)
            succ = False
        if succ:
            try:
                as_json = json.loads(post_body)
            except ValueError as e:
                mlmmj_resp = str(e)
                succ = False
        # if still everything is ok, get args and call mlmmj
        if succ:
            if 'nexthop' not in as_json or 'mail' not in as_json:
                mlmmj_resp = 'Invalid post request to the server handler, maybe a bug in the container?'
                succ = False
        if succ:
            # finally, everything ok and we cann call mlmmj-receive
            nexthop = as_json['nexthop']
            mail = as_json['mail']
            args = ['/usr/local/bin/mlmmj-receive', '-F', '-L', '/var/spool/mlmmj/%s' % nexthop]
            returncode, output = call_cmd(args, mail)
            if returncode != 0:
                mlmmj_resp = 'mlmmj-receive returned error: ' + output
            else:
                mlmmj_resp = output
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        resp = {'returncode': returncode, 'output': mlmmj_resp}
        self.wfile.write(json.dumps(resp).encode('utf-8'))
        return

if __name__ == '__main__':
    port = 7777
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError as e:
            print('Error reading port:', e)
            sys.exit(1)
    try:
        server = HTTPServer(('', port), PostfixHandler)
        print('Started mlmmj listener on port', port)
        server.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down mlmmj listener')
        server.socket.close()
    except OSError as osErr:
        print('Error while starting server:', osErr)
        sys.exit(1)
    except Exception as e:
        print('Unkown error:', e)
        sys.exit(1)
