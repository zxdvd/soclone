
from pymongo import MongoClient

mongo = MongoClient('mongodb://localhost:27017')

dbPosts = mongo.posts
dbUsers = mongo.users

def migrate_tag():
    r = dbPosts.posts.find({}, {'_id':1, 'tags':1})
    for d in r:
        tags = d['tags']
        tags = [tag.strip() for tag in tags.split(',')]
        dbPosts.posts.update_one({'_id': d['_id']}, {'$set':{'tags': tags}})

if __name__ == '__main__':
    migrate_tag()
