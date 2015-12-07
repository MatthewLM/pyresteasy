#!/usr/bin/python3
#
# Project: pyresteasy
# File: test.py
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

import pyresteasy

from webtest import TestApp

import unittest
import random
import string

TEST_CUSTOMER = {"name" : "Mr. Bean", "dob_year" : 1963}
DELETE_PRODUCT_RES = {"message" : "Deleted!"}
ERR_MESS = "Something went wrong"

customers = {}
products = {}
cid_count = 0

class Customers(pyresteasy.Resource):
    path = "customers"

    @pyresteasy.JsonReq()
    def POST(self, env, json):
        global cid_count
        cid = cid_count
        cid_count += 1
        customers[cid] = json
        return [{}, "", cid]

class Customer(pyresteasy.Resource):
    path = "customers/{cid:int}"

    def DELETE(self, env, cid):
        del customers[cid]
        return [{}, ""]

    @pyresteasy.JsonReq()
    def PUT(self, env, json, cid):
        customers[cid].update(json)
        return [{}, ""]

    @pyresteasy.JsonResp()
    def GET(self, env, cid):
        return [{}, customers[cid]]

class Products(pyresteasy.Resource):
    path = "products"

    @pyresteasy.JsonResp()
    @pyresteasy.JsonReq()
    def POST(self, env, json):
        pid = json["name"]
        products[pid] = json
        return [{}, {"id" : pid}, pid]

class Product(pyresteasy.Resource):
    path = "products/{pname}"

    @pyresteasy.JsonResp()
    def DELETE(self, env, pname):
        del products[pname]
        return [{}, DELETE_PRODUCT_RES]

    @pyresteasy.JsonResp()
    @pyresteasy.JsonReq()
    def PUT(self, env, json, pname):
        products[pname].update(json)
        return [{}, products[pname]]

    @pyresteasy.JsonResp()
    def GET(self, env, pname):
        return [{}, products[pname]]

class ProdVersions(pyresteasy.Resource):
    path = "products/{pname}/versions"

    @pyresteasy.JsonReq()
    def POST(self, env, json, pname):
        products[pname][json["version"]] = json
        return [{}, "", json["version"]]

class ProdVersion(pyresteasy.Resource):
    path = "products/{pname}/versions/{version:int}"

    @pyresteasy.JsonResp()
    def GET(self, env, pname, version):
        return [{}, products[pname][version]]

class ResourceFailJson(pyresteasy.Resource):
    path = "fail_json"

    @pyresteasy.JsonResp()
    def GET(self, env):
        raise pyresteasy.ServError({"Error": ERR_MESS}, ERR_MESS)

class ResourceFail(pyresteasy.Resource):
    path = "fail"

    def GET(self, env):
        raise pyresteasy.ServError({"Error": ERR_MESS}, ERR_MESS)

test_app = TestApp(pyresteasy.RestEasy([
    Customers(), Customer(), Products(), Product(), ProdVersions(), ProdVersion(),
    ResourceFail(), ResourceFailJson()
]))

class TestREST(unittest.TestCase):

    def assertJSON(self, got, exp):
        return self.assertDictEqual(got["success"], exp)

    def createCustomer(self):
        cid = cid_count
        return (test_app.post_json("/customers", TEST_CUSTOMER, status=201), cid)

    def createProduct(self):
        rand_name = ''.join(random.choice(string.ascii_letters) for x in range(5))
        pdict = {"name" : rand_name, "desc" : "A product!", "versions" : {}}
        return (test_app.post_json("/products", pdict, status=201), pdict)

    def createVersion(self, pname):
        v = {"version" : random.randint(1, 1000), "desc" : "Super Cool Version!"}
        return (test_app.post_json("/products/" + pname + "/versions", v, status=201), v)

    def testPostWithIntId(self):
        res, cid = self.createCustomer();
        self.assertEqual(res.location, "http://localhost:80/customers/" + str(cid))
        self.assertDictEqual(customers[cid], TEST_CUSTOMER)

    def testDeleteWithIntId(self):
        res, cid = self.createCustomer();
        self.assertIn(cid, customers)
        test_app.delete("/customers/" + str(cid), status=204)
        self.assertNotIn(cid, customers)

    def testPutWithIntId(self):
        res, cid = self.createCustomer();
        new_data = TEST_CUSTOMER.copy()
        new_data["name"] = "Dr. Dmitri"
        test_app.put_json("/customers/" + str(cid), {"name" : "Dr. Dmitri"}, status=204)
        self.assertDictEqual(customers[cid], new_data)
        new_data["dob_year"] = 1984
        test_app.put_json("/customers/" + str(cid), {"dob_year" : 1984}, status=204)
        self.assertDictEqual(customers[cid], new_data)

    def testGetWithIntId(self):
        res, cid = self.createCustomer();
        res = test_app.get("/customers/" + str(cid), status=200)
        self.assertEqual(res.content_type, "application/json")
        self.assertJSON(res.json, TEST_CUSTOMER)

    def testPostWithStrIdAndJson(self):
        res, pdict = self.createProduct();
        name = pdict["name"]
        self.assertEqual(res.content_type, "application/json")
        self.assertEqual(res.location, "http://localhost:80/products/" + name)
        self.assertEqual(products[name], pdict)
        self.assertJSON(res.json, {"id" : name})

    def testDeleteWithStrIdAndJson(self):
        res, pdict = self.createProduct();
        name = pdict["name"]
        self.assertIn(name, products)
        res = test_app.delete("/products/" + name, status=200)
        self.assertEqual(res.content_type, "application/json")
        self.assertJSON(res.json, DELETE_PRODUCT_RES)
        self.assertNotIn(name, products)

    def testPutWithStrIdAndJson(self):
        res, pdict = self.createProduct();
        name = pdict["name"]
        pdict["price"] = 39.99
        res = test_app.put_json("/products/" + name, {"price": 39.99}, status=200)
        self.assertDictEqual(products[name], pdict)
        self.assertJSON(res.json, pdict)

    def testGetWithStrId(self):
        res, pdict = self.createProduct();
        name = pdict["name"]
        res = test_app.get("/products/" + name, status=200)
        self.assertJSON(res.json, pdict)

    def test2LevelPost(self):
        res, pdict = self.createProduct();
        pname = pdict["name"]
        res, v = self.createVersion(pname)
        vname = v["version"]
        self.assertEqual(
            res.location, 
            "http://localhost:80/products/" + pname + "/versions/" + str(vname)
        )
        self.assertEqual(products[pname][vname], v)

    def test2LevelGet(self):
        res, pdict = self.createProduct();
        pname = pdict["name"]
        res, v = self.createVersion(pname)
        vname = v["version"]
        res = test_app.get("/products/" + pname + "/versions/" + str(vname), status=200)
        self.assertJSON(res.json, v)

    def testMethodNotAllowed(self):
        res = test_app.get("/products", status=405)
        self.assertEqual(res.headers["Allow"], "POST")

    def testBadJson(self):
        test_app.post("/customers", "{name : \"Matt\", \"dob_year\" : 1990}", status=400)

    def testHttpInterrupt(self):
        res = test_app.get("/fail", status=500)
        self.assertEqual(res.headers["Error"], ERR_MESS)
        self.assertEqual(res.body, bytes(ERR_MESS, "utf-8"))

    def testJsonHttpInterrupt(self):
        res = test_app.get("/fail_json", status=500)
        self.assertEqual(res.headers["Error"], ERR_MESS)
        self.assertEqual(res.json["error"], ERR_MESS)

    def testNotFound(self):
        test_app.get("/products/hello/anyone", status=404)

    def testBadId(self):
        test_app.get("/customers/bad", status=404)

    def testOptions(self):
        res, cid = self.createCustomer()
        res = test_app.options("/customers/" + str(cid), status=204)
        self.assertEqual(res.headers["Allow"], "GET,PUT,DELETE")
        

