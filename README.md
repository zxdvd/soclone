
## Introduction

A simple question and answer website based on tornado + mongodb.
Try to be a stackoverflow clone.

I wrote it on python 3.4 and didn't test with python 2.

## Installation

1. Setup mongodb and run it. I'd like to use docker.

        #docker pull mongo:latest
        #docker run --name mongo -p 27017:27017 -d mongo:latest

2. Install required python3 modules.

        #pip3 install -r requirements.txt

3. Setup settings and run.

        $cp settings.py.sample settings.py
        change the oauth2 related settings. Then
        $python3 main.py

## TODO

1. Security:
    * need to care about script when adding transfered markdown to page, need to
      use security html (I heard that there is a subclass of html which is safe)

2. Mongo:
    * Currently, I didn't care about count of a query. Sometimes it maybe too
      long I need to deal with that with "sort, skip and limit"

    * About versioning the post and answer. Comments has no verisoning.  
      For every post and answer, there is a "history" array field to store old
      versions.

3. Content
    * To save the mongdb space. Need to check if the edited new version is same
      as old version or only slight changes, if same, don't insert a new
      version, if slight changes, ..... I don't have a idea now.
    * Currenly, questions support comment but answer doesn't (will implement it
      soon).

4. User management
    * Currently, only baidu Oauth2 is implemented.

4. Vote support

5. Search and sort
