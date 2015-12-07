#!/usr/bin/python3
#
# Project: pyresteasy
# File: pyresteasy.py
#
# Copyright 2015 Matthew Mitchell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import json
from urllib.parse import quote

HTTP_OK = "200 OK"
HTTP_CREATED = "201 Created"
HTTP_NO_CONTENT = "204 No Content"
HTTP_BAD_REQUEST = "400 Bad Request"
HTTP_UNAUTHORISED = "401 Unauthorized"
HTTP_FORBIDDEN = "403 Forbidden"
HTTP_NOT_FOUND = "404 Not Found"
HTTP_METHOD_NOT_ALLOWED = "405 Method Not Allowed"
HTTP_CONFLICT = "409 Conflict"
HTTP_SERV_ERROR = "500 Internal Server Error"

MIME_JSON = "application/json"

def findMatch(obj, obj_list):

    for obj2 in obj_list:
        if obj == obj2:
            return obj2

    return None

def headersList(d):
    return list(d.items())

class JsonResp():

    def __call__(self, f):

        def jsonRespWrapper(*args, **kargs):

            try:
                resp = f(*args, **kargs)
                resp[0]["Content-Type"] = MIME_JSON
                resp[1] = json.dumps({"success" : resp[1]})
                return resp
            except HttpInterrupt as e:
                e.body = json.dumps({"error" : e.body})
                e.headers["Content-Type"] = MIME_JSON
                raise

        return jsonRespWrapper

class JsonReq():

    def __call__(self, f):

        def jsonReqWrapper(self, env, *args, **kargs):

            try:
                body = json.loads(env['wsgi.input'].read().decode('utf-8'))
            except ValueError:
                raise BadRequest(body="Badly formatted JSON")

            return f(self, env, body, *args, **kargs)

        return jsonReqWrapper

class HttpInterrupt(Exception):

    def __init__(self, headers={}, body=""):
        self.headers = headers
        self.body = body

class NotFound(HttpInterrupt):
    HTTP_CODE = HTTP_NOT_FOUND

class BadRequest(HttpInterrupt):
    HTTP_CODE = HTTP_BAD_REQUEST

class ServError(HttpInterrupt):
    HTTP_CODE = HTTP_SERV_ERROR

class Unauthorised(HttpInterrupt):
    HTTP_CODE = HTTP_UNAUTHORISED

class Forbidden(HttpInterrupt):
    HTTP_CODE = HTTP_FORBIDDEN

class Conflict(HttpInterrupt):
    HTTP_CODE = HTTP_CONFLICT

class Resource():

    def hasMethod(self, method):
        return callable(getattr(self, method, None))

class PathNode():

    def __init__(self):
        self.strs = []
        self.ids = []
        self.resource = None

class PathStr(PathNode):

    def __init__(self, s):
        super().__init__()
        self.s = s

    def __eq__(self, other):

        if type(other) is str:
            return self.s == other

        return self.s == other.s

class PathId(PathNode):

    def __init__(self, name, seg_type=None):

        super().__init__()

        self.name = name

        if seg_type == "int":
            self.seg_type = int
        else:
            self.seg_type = str

    def __eq__(self, other):

        if type(other) is str:

            if self.seg_type is str:
                return True

            try:
                int(other)
                return True
            except ValueError:
                return False

        return self.name == other.name and self.seg_type == other.seg_type

class RestEasy():

    def __init__(self, resources):

        self.resources = PathNode()

        for resource in resources:
            path = self.compilePathInfo(resource.path)

            cursor = self.resources

            for segment in path:

                node_list = cursor.strs if type(segment) == PathStr else cursor.ids

                match = findMatch(segment, node_list)

                if match is not None:
                    cursor = match
                else:
                    node_list.append(segment)
                    cursor = segment

            cursor.resource = resource

    def compilePathInfo(self, path):

        path = path.split("/")

        final = []
        for segment in path:

            if segment[0] == "{" and segment[-1] == "}":
                final.append(PathId(*segment[1:-1].split(":")))
            else:
                final.append(PathStr(segment))

        return final

    def getURL(self, env, addId=None):

        url = env['wsgi.url_scheme']+'://'

        if env.get('HTTP_HOST'):
            url += env['HTTP_HOST']
        else:
            url += env['SERVER_NAME']

            if env['wsgi.url_scheme'] == 'https':
                if env['SERVER_PORT'] != '443':
                   url += ':' + env['SERVER_PORT']
            else:
                if env['SERVER_PORT'] != '80':
                   url += ':' + env['SERVER_PORT']

        url += quote(env.get('SCRIPT_NAME', ''))
        url += quote(env.get('PATH_INFO', ''))

        if addId is not None:
            url += "/" + str(addId)

        return url

    def __call__(self, env, start_response):

        code, headers, body = self._callProcess(env, start_response)
        start_response(code, headersList(headers))
        return [bytes(body, "utf-8")]

    def _callProcess(self, env, start_response):

        try:
        
            # Find matching resource and get resource identifiers

            req_path = env["PATH_INFO"][1:].split("/")

            found = False
            res_ids = {}

            cursor = self.resources

            for segment in req_path:

                # Begin looking at string matches
                match = findMatch(segment, cursor.strs)

                if match is None:
                    # Next try ids
                    match = findMatch(segment, cursor.ids)
                    if match:
                        res_ids[match.name] = match.seg_type(segment)

                if match is None:
                    # Not Found
                    raise NotFound()
                    
                cursor = match

            resource = cursor.resource

            if resource is None:
                # Not Found
                raise NotFound()

            allowed = []

            for method in ["POST", "GET", "PUT", "DELETE"]:
                if resource.hasMethod(method):
                    allowed.append(method)

            allow = {"Allow": ",".join(allowed)};

            method = env['REQUEST_METHOD']

            if method == "OPTIONS":

                headers = {
                    'Access-Control-Allow-Headers': 'Content-Type, Accept, Content-Length, Host, Origin, User-Agent, Referer'
                }
                headers.update(allow)

                return (HTTP_NO_CONTENT, headers, "")

            if method not in allowed:
                return (HTTP_METHOD_NOT_ALLOWED, allow, "")

            if method == "POST":
                headers, body, rid = resource.POST(env, **res_ids)
                headers["Location"] = self.getURL(env, rid)
                return (HTTP_CREATED, headers, body)

            if method == "GET":
                headers, body = resource.GET(env, **res_ids)
                return (HTTP_OK, headers, body)

            if method == "PUT":
                headers, body = resource.PUT(env, **res_ids)

            elif method == "DELETE":
                headers, body = resource.DELETE(env, **res_ids)

            return (HTTP_OK if len(body) > 0 else HTTP_NO_CONTENT, headers, body)

        except HttpInterrupt as e:
            return (e.HTTP_CODE, e.headers, e.body)

