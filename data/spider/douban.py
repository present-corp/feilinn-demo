#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Components:
# * MovieInfo
#   Input: A URL to one douban movie page.
#   Output:
#       A list of actors/directors/scriptwriters, both name and URL
#       A list of related movies.
# * CelebriryInfo
#   Input: A URL to one celebrity page.
#   Output:
#       Atrributes: gender, DOB, POB, Professional, family, IMDB-ID, URL
#       A list of related movies.
#       Collaboration: list of other celebrities.
#
# * MovieInfoDatabaseWriter
#   Input: A movie object or celebrity object.
#   Output: Write the data into database.
#   Internally host several indexes:
#   1. crawled_urls
#   2. urls_to_crawl
#
# Database schema
# * douban_celebrity_v1
#   id, unique_id, gender, day_of_born, place_of_born
#
# * douban_celebrity_profession_v1
#   id, celebrity_unique_id, professional
#
# * douban_movie_v1
#   id, unique_id, title
#
# * douban_movie_director_map_v1
#   id, movie_unique_id, director_unique_id
#
# * douban_movie_scriptwriter_map_v1
#   id, movie_unique_id, script_writer_unique_id
#
# * douban_movie_actor_map_v1
#   id, movie_unique_id, actors_unique_id
#
# * douban_page_hash_map_v1 (for checking if a page needs to be updated)
#   id, page_url, hash

import sys
import re
import urllib2
import xml

# Python 2/3 compatibility hack: Import correct libraries
ver = sys.version[0]
if ver == '2':
    import urllib2 as UL
    import HTMLParser as HP
elif ver == '3':
    import urllib as UL
    import html.parser as HP
else:
    raise Exception("Support Python runtime version")


class UrlParseException(Exception):
    def __init__(self, url):
        Exception.__init__(self)
        self.__url = url
    def url(self):
        return self.__url

def parsehtml(url, html_parser):
    """
    parsehtml(url)

    A helper function to receive content from given URL.
    """
    response = UL.urlopen(url)
    encoding = response.headers.getparam('charset')
    content = response.read().decode(encoding)
    response.close()
    html_parser.feed(content)
    html_parser.reset()

class MoviePageVisitor(HP.HTMLParser):
    idle = 0
    movie_info_start = 1
    profession_start = 2
    director_start = 3
    scriptwriter_start = 4
    actor_start = 5
    get_new_celebrity = 6

    def __init__(self):
        HP.HTMLParser.__init__(self)
        self.__state = [MoviePageVisitor.idle]
        self.__new_celebrity = None
        self.__celebrities = {
                MoviePageVisitor.director_start: [],
                MoviePageVisitor.scriptwriter_start: [],
                MoviePageVisitor.actor_start: []
        }

    def directors(self):
        return self.__celebrities[MoviePageVisitor.director_start]
    def scriptwriters(self):
        return self.__celebrities[MoviePageVisitor.scriptwriter_start]
    def actors(self):
        return self.__celebrities[MoviePageVisitor.actor_start]

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        ltag = tag.lower()
        last_state = self.__state[-1]
        if ltag == 'div':
            if "id" in attrs_dict and attrs_dict["id"] == 'info':
                # Start from movie info.
                self.__state.append(MoviePageVisitor.movie_info_start)
            else:
                pass
        elif ltag == 'span':
            if "class" in attrs_dict and attrs_dict["class"] == "pl":
                # A profession index start
                if last_state == MoviePageVisitor.movie_info_start or \
                   last_state == MoviePageVisitor.profession_start or \
                   last_state == MoviePageVisitor.director_start or \
                   last_state == MoviePageVisitor.scriptwriter_start or \
                   last_state == MoviePageVisitor.actor_start:
                    self.__state.append(MoviePageVisitor.profession_start)
                else:
                    pass
        elif ltag == 'a':
            if last_state == MoviePageVisitor.director_start or \
               last_state == MoviePageVisitor.scriptwriter_start or \
               last_state == MoviePageVisitor.actor_start:
                if "href" in attrs_dict:
                    # Get URL of celebrities, the name of each celebrity
                    # can only be retrieved from handle_data
                    self.__new_celebrity = {}
                    self.__new_celebrity["url"] = attrs_dict["href"]
                    self.__new_celebrity["profession"] = last_state 
                    self.__state.append(MoviePageVisitor.get_new_celebrity)
            else:
                pass
        else:
            pass

    def handle_endtag(self, tag):
        pass

    def handle_data(self, data):
        last_state = self.__state[-1]
        if last_state == MoviePageVisitor.profession_start:
            if data == u'导演':
                self.__state.append(MoviePageVisitor.director_start)
            elif data == u'编剧':
                self.__state.append(MoviePageVisitor.scriptwriter_start)
            elif data == u'主演':
                self.__state.append(MoviePageVisitor.actor_start)
            else:
                pass
        elif last_state == MoviePageVisitor.get_new_celebrity:
            self.__new_celebrity["name"] = data.lstrip().rstrip()
            # Now we get full information of a new celebrity
            prof = self.__new_celebrity["profession"]
            self.__celebrities[prof].append(self.__new_celebrity)
            self.__new_celebrity = None
            self.__state.pop() # get_new_celebrity done.
        else:
            pass


class Movie(HP.HTMLParser):
    __movie_url_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/")
    __param_removal_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/(\?.*)$")
    def __init__(self, douban_url):
        """
        Movie.__init__(self, douban_url)
        """
        self.__movie_id = None
        self.__unique_id = None
        self.__title = None
        self.__related_movie_info = []
        self.__directors = []
        self.__actors = []
        self.__scriptwriters = []
        self.__parse_page(douban_url) # Note: May throw exception

    def url(self):
        # We don't keep URL all the time, as it's not really useful for
        # spider. Keeping a movie_id is good enough.
        return "http://movie.douban.com/subject/%s/" % self.__movie_id
        pass
    def unique_id(self):
        return self.__unique_id
    def title(self):
        return self.__title
    def actors(self):
        return self.__actors
    def scriptwriters(self):
        return self.__scriptwriters
    def directors(self):
        return self.__directors

    def __parse_page(self, douban_url):
        matched = Movie.__movie_url_pattern.match(douban_url)
        if matched is None:
            raise UrlParseException(douban_url)
        # This looks like a good page. Remove query parameters.
        matched = Movie.__param_removal_pattern.match(douban_url)
        if matched is not None:
            self.__movie_id = matched.group(1)
        # Get page content.
        m = MoviePageVisitor()
        parsehtml(self.url(), m)
        self.__directors = m.directors()
        self.__scriptwriters = m.scriptwriters()
        self.__actors = m.actors()
        m.reset()

class Celebrity(object):
    def __init__(self, douban_url):
        """
        Celebrity.__init__(self, douban_url)
        """
        self.__celebrity_id = None
        self.__gender = None
        self.__day_of_birth = None
        self.__city_of_birth = None
        self.__profession = None
        self.__unique_id = None
 
    def unique_id(self):
        return self.__unique_id
    def gender(self):
        return self.__gender
    def day_of_birth(self):
        return self.__bay_of_birth
    def city_of_birth(self):
        return self.__city_of_birth
    def profession(self):
        return self.__profession

    def __parse_page(self):
        pass

class Sqlite3Host(object):
    def __init__(self, sqlite_db_path):
        """
        Sqlite3Host.__init__(self, sqlite_db_path)

        Write data to a SQLite3 database.
        """
        self.__sqlite_db_path = sqlite_db_path
        self.__init_database()
        pass
    def save(self, obj):
        """
        Sqlite3Host.save(self, obj)

        Save object in database. Supports only :Movie: and :Celebrity:.
        """
        pass
    def __init_database(self):
        pass

def crawl(self, seed_url, database_host):
    pass

if __name__ == '__main__':
    # Unit test 1: Get celebrity information from movie page.
    def print_names(info):
        for each_info in info:
            print(each_info["name"].encode('utf-8'))
            print(each_info["url"].encode('utf-8'))
    m = Movie("http://movie.douban.com/subject/3078390/?from=showing")
    #print(m.url())
    print_names(m.actors())
    print("============")
    print_names(m.scriptwriters())
    print("============")
    print_names(m.directors())
