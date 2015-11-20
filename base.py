
import json
from bson import objectid
from datetime import datetime, timedelta

from tornado import gen, web
from pymongo import MongoClient

from settings import HOST

mongo = MongoClient('mongodb://%s:27017' % HOST)

dbPosts = mongo.posts
dbUsers = mongo.users

class BaseHandler(web.RequestHandler):
    def get_current_user(self):
        #scookies = [domain, uid, uname]
        scookies = self.get_secure_cookie('scookies')
        if scookies:
            scookies = json.loads(scookies.decode('utf-8'))
            if len(scookies) >= 2 and scookies[0] and scookies[1]:
                return scookies
        return None

    def add_user(self, db_handler, domain, token, **body):
        """Add user and related info to mongodb and cookie.
        uid should be stored as string but not int"""
        uid = body.pop('uid', None)
        if uid:
            uid = str(uid)
            #save user info securely and save an unsafe "uname" cookie so that
            #client js can get username
            uname = body.get('uname', uid)
            scookies = json.dumps([domain, uid, uname])
            self.set_secure_cookie('scookies', scookies)
            #some usernames has characters that cookie disallowed, encode it
            self.set_cookie('uname', quote(uname))
            body.update(authdomain=domain, token=token)
            r = db_handler.update_one({'uid': uid, 'authdomain': domain},
                    {'$set': body}, upsert=True)
            print('modified_count:', r.modified_count)

    def mongo_check_id(self, _id):
        if _id and objectid.ObjectId.is_valid(_id):
            return objectid.ObjectId(_id)
        else:
            self.write_result(False, fail={'msg': 'invalid id!'})
    
    #after check result of mongo update/insert, write a feedback to ajax client
    #can customize the feedback info and whether finish write or not
    def write_result(self, result, ok={'msg':'OK'}, fail={'msg':'FAIL'},
            finish=True):
        if result:
            ok['result'] = 1
            self.write(json.dumps(ok))
        else:
            fail['result'] = -1
            self.write(json.dumps(fail))
        if finish:
            self.finish()

    def prepare(self):
        """Check mobile browser of not.
        First check from cookie, if not found detect from User Agent."""
        mob = self.get_cookie('mob', None)
        if mob == '1':
            self.templdir = 'mob/'
        elif mob == '0':
            self.templdir = ''
        else:
            UA = self.request.headers.get('User-Agent', '').lower()
            mobile = ['android', 'iphone', 'googlebot-mobile']
            if any(i in UA for i in mobile):
                self.set_cookie('mob', '1')
                self.templdir = 'mob/'
            else:
                self.set_cookie('mob', '0')
                self.templdir = ''


