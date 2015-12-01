
import json
from bson import objectid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import markdown
from tornado import gen, web

from base import BaseHandler, dbPosts, dbUsers

class IndexHandler(BaseHandler):
    @gen.coroutine
    def get(self, tag=None):
        flt = {}
        if tag:
            flt = {'tags': tag}
        page = self.get_argument('page', '1')
        try:
            page = int(page)
        except ValueError:
            page = 1
        #only show 3 pages at most
        if page > 3:
            page = 3
        limits = {i: 1 for i in ('content', 'creator', 'tags', 'title',
            'lastModified')}
        page = page - 1              #first page skip 0, second skip 1*10
        r = dbPosts.posts.find(flt, limits, sort=[('lastModified', -1)],
                skip=page*10, limit=10)
        questions = [i for i in r if i]
        self.xsrf_token
        self.add_header('Vary', 'User-Agent')
        self.render(self.templdir+'index.html', out=questions)

class UserHandler(BaseHandler):
    @gen.coroutine
    def get(self, user):
        if '_' not in user:
            self.redirect('/')
        domain, uid = user.split('_', 1)
        items={}

        #get all answers answered by someone
        r = dbPosts.answers.find({'creator': {'$all': [domain, uid]}},
                sort=[('lastModified', -1)], limit=10)
        #get all posts against the answers
        tmp = [i.get('post_id', ' ') for i in r]
        posts = dbPosts.posts.find({'_id': {'$in': tmp}},
                sort=[('lastModified', -1)])
        items['answers'] = [i for i in posts if i]

        posts = dbPosts.posts.find({'creator': {'$all': [domain, uid]}},
                sort=[('lastModified', -1)], limit=10)
        items['questions'] = [i for i in posts if i]

        self.xsrf_token
        self.render('user.html', items = items)

class AskHandler(BaseHandler):
    """handler for /ask and /edit/p/id.
    Distinguish /ask and /edit/p/id in the template via 'edit'."""
    def initialize(self, edit):
        self.edit = edit

    @web.authenticated
    @gen.coroutine
    def get(self):
        self.xsrf_token
        self.render('ask.html', edit=self.edit)

class ShowQuestionHandler(BaseHandler):
    """handler for /p/id: id is the _id key of a mongo document (posts)"""
    @gen.coroutine
    def get(self, pageid):
        _id = self.mongo_check_id(pageid)
        #create_time = _id.generation_time
        question = dbPosts.posts.find_one({'_id': _id})
        if not question:
            self.redirect('/')
        question['content'] = markdown.markdown(question.get('content', ''))
        cursor = dbPosts.answers.find({'post_id': _id})
        answers = []
        for doc in cursor:
            doc['content'] = markdown.markdown(doc.get('content', ''))
            answers.append(doc)
        self.xsrf_token
        self.add_header('Vary', 'User-Agent')
        self.render(self.templdir+'question.html', out=question, answers=answers)

class AboutPageHandler(BaseHandler):
    """handler for page like /about (it redirects to a normal question)"""
    @gen.coroutine
    def get(self, url):
        post = dbPosts.posts.find_one({'linkurl': '/'+url})
        if post:
            _id = str(post.get('_id', ''))
            self.redirect('/p/'+_id, status=301)
        else:
            self.redirect('/')

class EditQuestionHandler(BaseHandler):
    """handler for /ajax/edit-question"""
    @web.authenticated
    @gen.coroutine
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
    @gen.coroutine
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
                self.write_result(False, fail={'msg': 'fail to update!'})
                return
        else:
            _id = objectid.ObjectId()       #create new page

        if title and content:
            post = dict(title=title, content=content)
            tags = self.get_argument('tags', '').split(',')
            post['tags'] = [tag.strip() for tag in tags]
            post['creator'] = self.current_user
            r = dbPosts.posts.update_one({'_id': _id},
                    {'$set': post, '$push': {'history': post},
                        '$currentDate': {'lastModified': True}},
                upsert=True)
            if r.upserted_id or r.modified_count:
                self.write_result(True, ok={'pageid': str(_id)})
            self.write_result(False, fail={'msg': 'fail to insert!'})
        else:
            self.write_result(False, fail={'msg': 'title and content should ' +
                'be empty!'})

class PostanswerHandler(BaseHandler):
    """handler for /ajax/post-answer. Contains both new answer and edit a old
    answer"""

    @web.authenticated
    @gen.coroutine
    def post(self):
        pathname = self.get_argument('pathname', '/p/')
        pathname = pathname[3:]             #skip the /p/ in the head
        post_id = self.mongo_check_id(pathname)
        content = self.get_argument('content', None)
        answerid = self.get_argument('answerid', None)
        if not content:
            self.write_result(False, fail={'msg': 'invalid content!'})

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
    @gen.coroutine
    def get(self):
        _id = self.get_argument('_id', '')
        _id = self.mongo_check_id(_id)
        limits = {i: 1 for i in ('content', 'creator')}
        answer = dbPosts.answers.find_one({'_id': _id}, limits)
        if not answer:
            self.write_result(None, fail={'msg': 'cannot find this answer!'})
            return
        #TODO XXX: currently only owner can edit his post
        #in the future maybe more users can edit it (depend on privilige)
        creator = answer.get('creator', '')
        if len(creator) > 1 and self.current_user[:2] != creator[:2]:
            self.write_result(None, fail={'msg': 'you arenot the creator!'})
            return
        answer.pop('_id')
        self.write(json.dumps(answer))

class PostCommentHandler(BaseHandler):
    """handler for /ajax/post-comment"""
    @web.authenticated
    @gen.coroutine
    def post(self):
        _id = self.get_argument('pathname', '/p/')[3:]
        _id = self.mongo_check_id(_id)
        content = self.get_argument('content', None)
        if content:
            comment = dict(content=content)
            comment['creator'] = self.current_user
            comment['time'] = datetime.now()
            #if answerid exists, then it's a answer comment
            answerid = self.get_argument('answerid', None)
            if answerid:
                answerid = self.mongo_check_id(answerid)
                r = dbPosts.answers.update_one({'_id': answerid},
                        {'$inc':{'commentCount':1}, '$push':{'comments':comment}})
                self.write_result(r.modified_count, ok={'pageid': str(_id)})
            else:
                r = dbPosts.posts.update_one({'_id': _id},
                        {'$inc': {'commentCount': 1}, '$push': {'comments': comment}})
                self.write_result(r.modified_count, ok={'pageid': str(_id)})

class VoteHandler(BaseHandler):
    """handler for /ajax/vote. Store vote under user collection."""
    @web.authenticated
    @gen.coroutine
    def get(self):
        _id = self.get_argument('_id', None)
        content = self.get_argument('content', None)
        vote = self.get_argument('vote', None)
        _id = self.mongo_check_id(_id)
        if content and vote:
            if vote == 'up':
                voteresult = True
            elif vote == 'down':
                voteresult = False
            else:
                self.write_result(None)
            domain, uid = self.current_user[:2]
            user = dict(authdomain=domain, uid=uid)
            #the user document will look like:
            #{authdomain: baidu, uid:XXX,
            #    votes: {question_id_1:true,    //true means vote up
            #            question_id_2:false}   //false means vote down
            #}
            #TODO XXX: need to think about a user vote up then vote down
            r = dbUsers.users.update_one(user,
                    {'$set':{'votes.'+str(_id): voteresult}})
            print(r.matched_count, r.modified_count)
            self.write_result(r.modified_count, finish=False)
            #if document not modified, that means user already voted
            #then needn't to inc/dec the voteCount
            if r.modified_count:
                #increase/decrease the vote count of question/answer
                #TODO XXX: this should not be done here
                #should be send to a task queue and let the queue write to db
                inc = 1 if vote=='up' else -1
                if content == 'answer':
                    dbPosts.answers.update_one({'_id':_id},
                            {'$inc': {'voteCount': inc}})
                if content == 'question':
                    dbPosts.posts.update_one({'_id':_id},
                            {'$inc': {'voteCount': inc}})

