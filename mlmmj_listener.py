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
import os
import json
import subprocess
import binascii
import base64
import argparse

# This file is the anchor point that runs inside the mlmmj docker container.
# It listens on a certain port (default is 7777) and waits for calls to mlmmj
# executables.
# Simply start this script without any arguments or with -p PORT for a different
# port.
# It works as follows: All requests must be a json dictionary with the following
# content: It must have a field 'mlmmj-command' that is the name of an
# executable. Valid values are therefor:
# - 'mlmmj-bounce'
# - 'mlmmj-list'
# - 'mlmmj-maintd'
# - 'mlmmj-make-ml'
# - 'mlmmj-process'
# - 'mlmmj-receive'
# - 'mlmmj-send'
# - 'mlmmj-sub'
# - 'mlmmj-unsub'
#
# Also a list of type string can contained in the json data called 'args',
# these are all the arguments that will be passed to the executable.
# In the case of mlmmj-receive there also must be a field 'mail' in the json
# data. That is the content of the mail: postfix prints the mail content to
# stdout and mlmmj reads that input. This field must be the base64 encoded
# version of the byte data read from stdin.
# So the workflow in this case is as follows:
# Postfix writes something to stdout, another script (usually postfix_incoming)
# reads that data as a byte array, encodes it using base64 and sends the content
# to this listener. This listener then decodes the base64 string and feeds
# the content in mlmmj-receive.
# For all other commands an input is not possible at the moment, I think none
# of the other mlmmj-... commands require it.

def call_cmd(args, input=None):
    byte_array = None
    if input is not None:
        try:
            byte_array = base64.b64decode(input, validate=True)
        except binascii.Error as e:
            return 1, 'Received invalid email body: Email not encoded in valid base 64: ' + str(e)
    returncode = 0
    try:
        if byte_array is None:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        else:
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, input=byte_array)
    except subprocess.CalledProcessError as e:
        output = e.output
        returncode = e.returncode
    except FileNotFoundError as notFound:
        output = str(notFound)
        returncode = 1
    try:
        output = output.decode('utf-8', 'replace')
    except AttributeError:
        pass
    return returncode, output

class MLMMJHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global executables
        global allowed_commands
        content_len = int(self.headers.get('content-length', 0))
        post_body = self.rfile.read(content_len)
        mlmmj_resp = ''
        succ = True
        try:
            post_body = post_body.decode('utf-8')
        except UnicodeDecodeError as e:
            mlmmj_resp = 'Error while encoding request: ' + str(e)
            succ = False
        if succ:
            try:
                as_json = json.loads(post_body)
            except ValueError as e:
                mlmmj_resp = 'Error while parsing body as json: ' + str(e)
                succ = False
        if succ:
            # if everything was ok until now, check if the json object is
            # a dictionary and if it contains only valid fields
            if type(as_json) != dict:
                mlmmj_resp = 'Invalid json body: Must be a dict'
                succ = False
        if succ:
            # check dict arguments
            if 'mlmmj-command' not in as_json or 'args' not in as_json:
                mlmmj_resp = 'Invalid json body: Dictionary must contain field "mlmmj-command"'
                succ = False
            else:
                mlmmj_command = as_json['mlmmj-command']
                additional_args = as_json['args']
        if succ:
            # next we check if the the mlmmj-command is valid
            if mlmmj_command not in allowed_commands:
                mlmmj_resp = 'Invalid mlmmj-command "%s": Must be the name of an mlmmj executable' % mlmmj_command
                succ = False
        # next check if the command is mlmmj-receive, in this case 'mail' must
        # be present as well
        if succ:
            if mlmmj_command == 'mlmmj-receive':
                if 'mail' not in as_json:
                    mlmmj_resp = 'Invalid mlmmj-receive instruction: Must contain a field "mail" (base64 encoded mail)'
                    succ = False
                else:
                    input = as_json['mail']
            else:
                input = None
        # if everything is ok this far we call the command and get the output
        if succ:
            args = [os.path.join(executables, mlmmj_command)] + additional_args
            returncode, output = call_cmd(args, input)
            if returncode != 0:
                mlmmj_resp = 'mlmmj instruction returned error: ' + output
            else:
                mlmmj_resp = output
        else:
            # set returncode to an error
            returncode = 1
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        resp = {'returncode': returncode, 'output': mlmmj_resp}
        self.wfile.write(json.dumps(resp).encode('utf-8'))
        return

executables = None
allowed_commands = {'mlmmj-bounce', 'mlmmj-list',
    'mlmmj-maintd', 'mlmmj-make-ml', 'mlmmj-process', 'mlmmj-receive',
    'mlmmj-send', 'mlmmj-sub', 'mlmmj-unsub'}


def main():
    parser = argparse.ArgumentParser(description='Script to wait for mlmmj commands and execute them.')
    parser.add_argument('--port', '-p', type=int, required=False, default=7777, help='The port to listen on (default 7777)')
    parser.add_argument('--executables', '-e', type=str, required=False, default='/usr/local/bin/', help='The directory containing all mlmmj-* executables (default "/usr/local/bin")')
    args = parser.parse_args()
    global executables
    executables = args.executables

    # start server
    try:
        server = HTTPServer(('', args.port), MLMMJHandler)
        print('Started mlmmj listener on port', args.port)
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

if __name__ == '__main__':
    main()
