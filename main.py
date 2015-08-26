
from tornado import ioloop, log

from handlers import *
from settings import TORNADO_SETTINGS

#pretty log for tornado server
log.enable_pretty_logging()

if __name__ == '__main__':
    app = web.Application([
        (r'/', IndexHandler),
        (r'/ask', AskHandler, dict(edit=False)),
        (r'/edit/p/.*', AskHandler, dict(edit=True)),
        (r'/auth/baidu', BaiduOauthHandler),
        (r'/auth/weibo', WeiboOauthHandler),
        (r'/p/(.*)/?', ShowQuestionHandler),
        (r'/ajax/post-question', PostquestionHandler),
        (r'/ajax/post-answer', PostanswerHandler),
        (r'/ajax/post-comment', PostCommentHandler),
        (r'/ajax/edit-question', EditQuestionHandler),
        (r'/ajax/edit-answer', EditAnswerHandler),
        (r'/ajax/vote', VoteHandler),
        (r'/static/(.*)', web.StaticFileHandler, {'path': './static'}),
        #(r'/ajax/getbug/([\d]+)', GetbugHandler),
        #(r'/expirerun/([\d]+)', ExpireRunHandler),
        #(r'/([.@\d\w]+)', PersonHandler),
        ], **TORNADO_SETTINGS)
    app.listen(5000)
    ioloop.IOLoop.instance().start()
