
import json
from bson import objectid
from datetime import datetime
from urllib.parse import urlencode

import markdown
from tornado import gen, httpclient, ioloop, web
from pymongo import MongoClient

from auths import BaiduOAuth2Mixin
from settings import AUTH, HOST

mongo = MongoClient('mongodb://%s:27017' % HOST)

dbPosts = mongo.posts
dbUsers = mongo.users

class BaseHandler(web.RequestHandler):
    def get_current_user(self):
        domain = self.get_secure_cookie('authdomain')
        uid = self.get_secure_cookie('uid')
        username = self.get_secure_cookie('username')
        if domain and uid:
            return tuple(i.decode('utf-8') for i in (domain, uid, username))
        else:
            return None

    def mongo_check_id(self, _id):
        if _id and objectid.ObjectId.is_valid(_id):
            return objectid.ObjectId(_id)
        else:
            self.write(json.dumps({'result':-1, 'msg':'invalid id!'}))
            self.finish()
    
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

    def add_user(self, db_handler, domain, token, **body):
        """Add user and related info to mongodb and cookie"""
        uid = body.get('uid', None)
        if uid:
            #save user info securely and save an unsafe "uname" cookie so that
            #client js can get username
            uname = body.get('uname', uid)
            for (k,v) in [('authdomain', domain), ('uid', uid), ('username',
                uname), ('token', token)]:
                self.set_secure_cookie(k, v)
            self.set_cookie('uname', uname)
            body.update(authdomain=domain, token=token)
            r = db_handler.update_one({'uid': uid, 'authdomain': domain},
                    {'$set': body}, upsert=True)
            print('modified_count:', r.modified_count)

class IndexHandler(BaseHandler):
    def get(self):
        #XXX TODO, will think more about limit, batch_size in the future
        #should not return all documents in a query
        limits = {i: 1 for i in ('content', 'creator', 'tags', 'title',
            'lastModified')}
        r = dbPosts.posts.find({}, limits)
        questions = []
        for q in r:
            q['_id'] = str(q['_id'])
            questions.append(q)
        self.render('index.html', out=questions)

class AskHandler(BaseHandler):
    """handler for /ask and /edit/p/id.
    Distinguish /ask and /edit/p/id in the template via 'edit'."""
    def initialize(self, edit):
        self.edit = edit

    @web.authenticated
    def get(self):
        self.xsrf_token
        self.render('ask.html', edit=self.edit)

class ShowQuestionHandler(BaseHandler):
    """handler for /p/id: id is the _id key of a mongo document (posts)"""
    def get(self, pageid):
        _id = self.mongo_check_id(pageid)
        create_time = _id.generation_time
        limits = {i: 1 for i in ('content', 'creator', 'tags', 'title',
            'lastModified', 'commentCount', 'comments')}
        question = dbPosts.posts.find_one({'_id': _id}, limits)
        if not question:
            self.redirect('/')
        question['content'] = markdown.markdown(question.get('content', ''))
        cursor = dbPosts.answers.find({'post_id': _id})
        answers = []
        for doc in cursor:
            doc['content'] = markdown.markdown(doc.get('content', ''))
            answers.append(doc)
        self.xsrf_token
        self.render('question.html', out=question, answers=answers)

class EditQuestionHandler(BaseHandler):
    """handler for /ajax/edit-question"""
    @web.authenticated
    def get(self):
        editid = self.get_argument('editid', '')
        _id = self.mongo_check_id(editid)
        limits = {i: 1 for i in ('content', 'creator', 'tags', 'title')}
        question = dbPosts.posts.find_one({'_id': _id}, limits)
        if question:
            #TODO XXX: currently only owner can edit his post
            #in the future maybe more users can edit it (depend on privilige)
            if self.current_user[:2] == tuple(question['creator'])[:2]:
                question.pop('_id')
                self.write(json.dumps(question))

class PostquestionHandler(BaseHandler):
    """handler for /ajax/post-question: post new or an edited old page"""
    @web.authenticated
    def post(self):
        title = self.get_argument('title', None)
        content = self.get_argument('content', None)
        editid = self.get_argument('editid', '')
        #valid editid means  user is editing the page but not create new page
        if editid:
            _id = self.mongo_check_id(editid)
            #check if user if the owner of this editing page
            q = dbPosts.posts.find_one({'_id': _id}, {'creator': 1})
            if (not q) or self.current_user[:2] != tuple(q['creator'])[:2]:
                #TODO XXX: currently only owner can edit his post
                #in the future maybe more users can edit it (depend on privilige)
                self.write(json.dumps({'result':-1, 'msg':'fail to update!'}))
                self.finish()
        else:
            _id = objectid.ObjectId()       #create new page

        if title and content:
            post = dict(title=title, content=content)
            post['tags'] = self.get_argument('tags', None)
            post['creator'] = self.current_user
            r = dbPosts.posts.update_one({'_id': _id},
                    {'$set': post, '$push': {'history': post},
                        '$currentDate': {'lastModified': True}},
                upsert=True)
            _id = r.upserted_id
            if r.upserted_id:
                self.write(json.dumps({'result':1, 'pageid': str(_id)}))
                self.finish()
            if r.modified_count:
                self.write(json.dumps({'result':1, 'pageid': str(_id)}))
                self.finish()
            self.write(json.dumps({'result':-1, 'msg':'fail to insert!'}))
        else:
            self.write(json.dumps({'result':-1, 'msg': 'title and content ' +
                'should not be empty'}))

class PostanswerHandler(BaseHandler):
    """handler for /ajax/post-answer. Contains both new answer and edit a old
    answer"""

    @web.authenticated
    def post(self):
        pathname = self.get_argument('pathname', '/p/')
        pathname = pathname[3:]             #skip the /p/ in the head
        post_id = self.mongo_check_id(pathname)
        content = self.get_argument('content', None)
        answerid = self.get_argument('answerid', None)
        if not content:
            self.write(json.dumps({'result':-1, 'msg':'invalid content!'}))
            self.finish()

        answer = dict(content=content, post_id=post_id)
        answer['creator'] = self.current_user
        #if has answerid, it's a edited answer otherwise a new answer
        #for a edited answer, need to check the creator
        if answerid:
            answerid = self.mongo_check_id(answerid)
            r = dbPosts.answers.update_one(
                    {'_id': answerid, 'creator': list(self.current_user)},
                    {'$set': answer, '$push': {'history': answer},
                        '$currentDate': {'lastModified': True}})
            self.write_result(r.modified_count)
        else:
            answer['lastModified'] = datetime.now()
            r = dbPosts.answers.insert_one(answer)
            _id = r.inserted_id
            self.write_result(_id)

class EditAnswerHandler(BaseHandler):
    """handler for /ajax/edit-answer"""
    @web.authenticated
    def get(self):
        _id = self.get_argument('_id', '')
        if not objectid.ObjectId.is_valid(_id):
            self.write(json.dumps({'result':1, 'msg': 'invalid answer id!'}))
            self.finish()
        _id = objectid.ObjectId(_id)
        limits = {i: 1 for i in ('content', 'creator')}
        answer = dbPosts.answers.find_one({'_id': _id}, limits)
        if not answer:
            self.write(json.dumps({'result':-1, 'msg': 'cannot find this answer!'}))
            self.finish()
        #TODO XXX: currently only owner can edit his post
        #in the future maybe more users can edit it (depend on privilige)
        if self.current_user[:2] != tuple(answer['creator'])[:2]:
            self.write(json.dumps({'result':1, 'msg': 'you arenot the creator!'}))
            self.finish()
        answer.pop('_id')
        self.write(json.dumps(answer))

class PostCommentHandler(BaseHandler):
    """handler for /ajax/post-comment"""
    @web.authenticated
    def post(self):
        _id = self.get_argument('pathname', '/p/')[3:]
        if not objectid.ObjectId.is_valid(_id):
            self.write(json.dumps({'result':-1, 'msg':'fail to post answer!'}))
            self.finish()
        _id = objectid.ObjectId(_id)
        content = self.get_argument('content', None)
        if content:
            comment = dict(content=content)
            comment['creator'] = self.current_user
            comment['time'] = datetime.now()
            r = dbPosts.posts.update_one({'_id': _id},
                    {'$inc': {'commentCount': 1}, '$push': {'comments': comment}})
            self.write_result(r.modified_count, ok={'pageid': str(_id)})

class BaiduOauthHandler(BaseHandler, BaiduOAuth2Mixin):
    @gen.coroutine
    def get(self):
        _client_id = AUTH['baidu']['client_id']
        _secret = AUTH['baidu']['secret']
        if self.get_argument('code', False):
            auth_info = yield self.get_authenticated_user(
                redirect_uri='http://%s:5000/auth/baidu' % HOST,
                code = self.get_argument('code'),
                client_id=_client_id,
                client_secret=_secret)
            token = auth_info.get('access_token', None)
            if token:
                self.set_secure_cookie('baidu_token', token)
                user_info = yield self.baidu_request('/passport/users/getLoggedInUser',
                        post_args={}, access_token=token)
                self.add_user(dbUsers.users, domain='baidu', token=token, **user_info)
                self.redirect('/')
        else:
            yield self.authorize_redirect(
                redirect_uri='http://%s:5000/auth/baidu' % HOST,
                client_id=_client_id,
                response_type='code')
