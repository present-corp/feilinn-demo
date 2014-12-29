#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import re
import urllib2
import logging
import sqlite3

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

def parsehtml(url):
    """
    parsehtml(url)

    A helper function to receive content from given URL.
    """
    response = UL.urlopen(url)
    encoding = response.headers.getparam('charset')
    content = response.read().decode(encoding)
    response.close()
    return content

class MoviePageVisitor(HP.HTMLParser):
    # State automaton
    idle = 0
    movie_info_start = 1
    profession_start = 2
    director_start = 3
    scriptwriter_start = 4
    actor_start = 5
    profession_get_role = 6
    profession_get_celebrities = 7
    get_new_celebrity = 8
    placeholder = 9
    can_ignore = 10
    related_movie_start = 11
    movie_title_start = 12
    movie_year_start = 13

    def __init__(self, html_content):
        HP.HTMLParser.__init__(self)
        self.__state = [MoviePageVisitor.idle]
        self.__tag_stack = []
        self.__new_celebrity = None
        self.__related_movie_urls = []
        self.__title = None
        self.__year = None
        self.__celebrities = {
                MoviePageVisitor.director_start: [],
                MoviePageVisitor.scriptwriter_start: [],
                MoviePageVisitor.actor_start: []
        }
        self.feed(content)
        self.reset()

    def directors(self):
        return self.__celebrities[MoviePageVisitor.director_start]
    def scriptwriters(self):
        return self.__celebrities[MoviePageVisitor.scriptwriter_start]
    def actors(self):
        return self.__celebrities[MoviePageVisitor.actor_start]
    def related_movie_urls(self):
        return self.__related_movie_urls
    def title(self):
        return self.__title
    def year(self):
        return self.__year

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        ltag = tag.lower()
        last_state = self.__state[-1]

        if ltag == 'div':
            if "id" in attrs_dict and attrs_dict["id"] == 'info':
                self.__state.append(MoviePageVisitor.movie_info_start)
            elif "class" in attrs_dict and \
                    attrs_dict["class"] == 'recommendations-bd':
                self.__state.append(MoviePageVisitor.related_movie_start)
            else:
                pass
        elif ltag == 'span':
            if "class" in attrs_dict and attrs_dict["class"] == 'pl':
                # Update state of parent level: It should be the start
                # of events
                if last_state == MoviePageVisitor.placeholder:
                    assert self.__state[-2] == MoviePageVisitor.movie_info_start
                    self.__state[-1] = MoviePageVisitor.profession_start
                    self.__state.append(MoviePageVisitor.profession_get_role)
                else:
                    pass
            elif "class" in attrs_dict and attrs_dict["class"] == 'attrs':
                self.__state.append(MoviePageVisitor.profession_get_celebrities)
            elif last_state == MoviePageVisitor.movie_info_start:
                # Placeholder. Will be replaced at <span class="pl".
                self.__state.append(MoviePageVisitor.placeholder)
            elif "property" in attrs_dict and \
                    attrs_dict["property"] == "v:itemreviewed":
                self.__state.append(MoviePageVisitor.movie_title_start)
            elif "class" in attrs_dict and attrs_dict["class"] == "year":
                self.__state.append(MoviePageVisitor.movie_year_start)
            else:
                pass
        elif ltag == 'a':
            if last_state == MoviePageVisitor.profession_get_celebrities:
                role = self.__state[-2]
                assert role == MoviePageVisitor.director_start or \
                        role == MoviePageVisitor.scriptwriter_start or \
                        role == MoviePageVisitor.actor_start
                if "href" in attrs_dict:
                    # Get URL of celebrities, the name of each celebrity
                    # can only be retrieved from handle_data
                    self.__new_celebrity = {}
                    # Make sure the URL matches the content 
                    m = Celebrity.celebrity_pattern.match(attrs_dict["href"])
                    if m is not None:
                        self.__new_celebrity["id"] = m.group(1)
                    else:
                        self.__new_celebrity["id"] = attrs_dict["href"]
                    self.__new_celebrity["profession"] = role 
                    self.__state.append(MoviePageVisitor.get_new_celebrity)
            elif last_state == MoviePageVisitor.related_movie_start:
                self.__related_movie_urls.append(attrs_dict["href"])
            else:
                pass
        else:
            pass

    def handle_endtag(self, tag):
        ltag = tag.lower()
        last_state = self.__state[-1]
        if ltag == 'a':
            if last_state == MoviePageVisitor.get_new_celebrity or \
               last_state == MoviePageVisitor.movie_title_start or \
               last_state == MoviePageVisitor.movie_year_start:
                self.__state.pop()
            else:
                pass
        elif ltag == 'span':
            if last_state == MoviePageVisitor.director_start or \
               last_state == MoviePageVisitor.scriptwriter_start or \
               last_state == MoviePageVisitor.actor_start or \
               last_state == MoviePageVisitor.profession_get_celebrities or \
               last_state == MoviePageVisitor.profession_get_role or \
               last_state == MoviePageVisitor.movie_title_start or \
               last_state == MoviePageVisitor.movie_year_start:
                self.__state.pop()
            elif last_state == MoviePageVisitor.can_ignore:
                pass
            elif last_state == MoviePageVisitor.profession_start:
                # It may happen for tags like region/languages
                assert False
                pass
            else:
                pass
        elif ltag == 'div':
            if last_state == MoviePageVisitor.movie_info_start:
                self.__state.pop()
            elif last_state == MoviePageVisitor.related_movie_start:
                self.__state.pop()
            else:
                pass

    def handle_data(self, data):
        date = data.lstrip().rstrip()
        last_state = self.__state[-1]
        if last_state == MoviePageVisitor.profession_get_role:
            assert self.__state[-2] == MoviePageVisitor.profession_start
            if data == u'导演':
                self.__state[-2] = MoviePageVisitor.director_start
            elif data == u'编剧':
                self.__state[-2] = MoviePageVisitor.scriptwriter_start
            elif data == u'主演':
                self.__state[-2] = MoviePageVisitor.actor_start
            else:
                # Others like region, just keep placeholder
                self.__state[-2] = MoviePageVisitor.can_ignore
                pass
        elif last_state == MoviePageVisitor.get_new_celebrity:
            self.__new_celebrity["name"] = data.lstrip().rstrip()
            # Now we get full information of a new celebrity
            prof = self.__new_celebrity["profession"]
            self.__celebrities[prof].append(self.__new_celebrity)
            self.__new_celebrity = None
        elif last_state == MoviePageVisitor.movie_title_start:
            self.__title = data
        elif last_state == MoviePageVisitor.movie_year_start:
            self.__year = data[1:-1]
        else:
            pass


class Movie(HP.HTMLParser):
    __movie_url_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/")
    __param_removal_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/(\?.*)$")
    def __init__(self, douban_url, html_content = None):
        """
        Movie.__init__(self, douban_url, html_content)
        """
        self.__movie_id = None
        self.__unique_id = None
        self.__title = None
        self.__year = None
        self.__related_movie_ids = []
        self.__directors = []
        self.__actors = []
        self.__scriptwriters = []
        self.__parse_page(douban_url, html_content)

    def url(self):
        # We don't keep URL all the time, as it's not really useful for
        # spider. Keeping a movie_id is good enough.
        return Movie.reformat_movie_url(self.__movie_id)

    def unique_id(self):
        return self.__unique_id
    def title(self):
        return self.__title
    def year(self):
        return self.__year
    def actors(self):
        return self.__actors
    def scriptwriters(self):
        return self.__scriptwriters
    def directors(self):
        return self.__directors
    def related_movie_ids(self):
        """
        Movie.related_movie_urls() -> List of movie IDs

        Return a list of related movie IDs, found from HTML page. The
        IDs can be used to regenerate full movie page URL with
        Movie.reformat_movie_url().
        """
        return self.__related_movie_ids

    def __parse_page(self, douban_url, html_content):
        self.__movie_id = Movie.parse_movie_id(douban_url)
        content = html_content
        if html_content is None:
            content = parsehtml(self.url())
        else:
            content = html_content
        m = MoviePageVisitor(content)

        self.__directors = m.directors()
        self.__scriptwriters = m.scriptwriters()
        self.__actors = m.actors()
        self.__related_movie_ids = \
                [Movie.parse_movie_id(each) for each in m.related_movie_urls()]
        self.__title = m.title()
        self.__year = m.year()
        self.__unique_id = "%s_%s" % (self.__title, self.__year)

    @staticmethod
    def parse_movie_id(douban_url):
        """
        Movie.parse_movie_id(self, douban_url) -> Id only.

        Static method. Parse movie Id from given Douban movie URL. If
        the input URL does not look like a valid Douban movie URL, raise
        :UrlParseException: exception.
        """
        matched = Movie.__movie_url_pattern.match(douban_url)
        if matched is None:
            raise UrlParseException(douban_url)
        # This looks like a good page. Remove query parameters.
        matched = Movie.__param_removal_pattern.match(douban_url)
        if matched is not None:
            movie_id = matched.group(1)
        else:
            raise UrlParseException(douban_url)
        return movie_id

    @staticmethod
    def reformat_movie_url(movie_id):
        return "http://movie.douban.com/subject/%s/" % movie_id


class Celebrity(object):
    celebrity_pattern = re.compile("\/celebrity\/([0-9][0-9]*)\/")
    __celebrity_url_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/celebrity\/([0-9][0-9]*)\/")
    __param_removal_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/celebrity\/([0-9][0-9]*)\/(\?.*)$")

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

    @staticmethod
    def parse_celebrity_id(douban_url):
        """
        Celebrity.parse_celebrity_id(self, douban_url) -> Id only.

        Static method. Parse celebrity Id from given Douban movie URL. If
        the input URL does not look like a valid Douban movie URL, raise
        :UrlParseException: exception.
        """
        matched = Celebrity.__celebrity_url_pattern.match(douban_url)
        if matched is None:
            raise UrlParseException(douban_url)
        # This looks like a good page. Remove query parameters.
        matched = Celebrity.__param_removal_pattern.match(douban_url)
        if matched is not None:
            celebrity_id = matched.group(1)
        else:
            raise UrlParseException(douban_url)
        return celebrity_id

    @staticmethod
    def reformat_celebrity_url(celebrity_id):
        return "http://movie.douban.com/celebrity/%s/" % celebrity_id


class Sqlite3Host(object):
    __table_params = {
        'v1_celebrity_info': ('id',
                              'douban_id',
                              'name',
                              'day_of_birth',
                              'place_of_birth'),
        'v1_movie_info': ('id',
                          'douban_id',
                          'name',
                          'year'),
        'v1_movie_profession_map': ('movie_douban_id',
                                    'celebrity_douban_id',
                                    'profession'),
        'v1_pending_movie_urls': ('movie_url'),
        'v1_pending_celebrity_urls': ('celebrity_url')
    }
    __table_creation_statements = {
        'v1_celebrity_info': """create table v1_celebrity_info (
                                id text,
                                douban_id text,
                                name text,
                                day_of_birth text,
                                place_of_birth text)""",
        'v1_movie_info': """create table v1_movie_info (
                            id text,
                            douban_id text,
                            name text,
                            year text)""",
        'v1_movie_profession_map': \
                """create table v1_movie_profession_map (
                   movie_douban_id text,
                   celebrity_douban_id text,
                   profession text)""",
        'v1_pending_movie_urls': \
                """create table v1_pending_movie_urls (
                   movie_url text)""",
        'v1_pending_celebrity_urls': \
                """create table v1_pending_celebrity_urls (
                   celebrity_url text)"""
        }
    def __init__(self, sqlite_db_path):
        """
        Sqlite3Host.__init__(self, sqlite_db_path)

        Write data to a SQLite3 database.
        """
        self.__sqlite_db_path = sqlite_db_path
        self.__conn = sqlite3.connect(sqlite_db_path)
        self.__create_database()
        pass
    def save(self, obj):
        """
        Sqlite3Host.save(self, obj)

        Save object in database. Supports only :Movie: and :Celebrity:.
        """
        pass

    def __create_table(self):
        tables = Sqlite3Host.__table_params.keys()
        query = '''select :table_name from sqlite_master where
                   type='table' and name=:table_name'''
        for each_table in tables:
            cur = self.__conn.execute(query, {'table_name': each_table})
            if cur.fetchone() is None: # A table does not exist
                logging.info("Create table %s." % each_table)
                create = Sqlite3Host.__table_creation_statements[each_table]
                self.__conn.execute(create)
            else:
                logging.info("Table %s exists. Use it." % each_table)
        self.__conn.commit()
        # Now all tables are created

def crawl(self, seed_url, database_host):
    pass

if __name__ == '__main__':
    # Unit test 1: Get celebrity information from movie page.
    def print_names(info):
        for each_info in info:
            print(each_info["name"].encode('utf-8'))
            print(each_info["id"].encode('utf-8'))
    url = "http://movie.douban.com/subject/1291843/?from=showing"
    content = parsehtml(url)
    m = Movie(url, content)
    print_names(m.actors())
    print("============")
    print_names(m.scriptwriters())
    print("============")
    print_names(m.directors())
    print("============")
    print(m.related_movie_ids())
    print("============")
    print(m.year())
    print(m.title())
    print(m.url())
    # Unit test 2: Create table
    h = Sqlite3Host('test.db')
