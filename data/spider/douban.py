#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import re
import urllib2
import logging
import sqlite3
import threading

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

class UnsupportedDataException(Exception):
    def __init__(self, type_name):
        Exception.__init__(self)
        self.__type_name = type_name
    def type_name(self):
        return self.__type_name

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

class CelebritySearchPageVisitor(HP.HTMLParser):
    STATE_IDLE = 0
    STATE_SEARCH_RESULT = 1
    STATE_NAME_START = 2

    def __init__(self, html_content):
        HP.HTMLParser.__init__(self)
        self.__state = [CelebritySearchPageVisitor.STATE_IDLE]
        self.__search_result_url = None
        self.__name = None
        self.feed(html_content)
        self.reset()
    def search_result_url(self):
        return self.__search_result_url
    def name(self):
        return self.__name

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        ltag = tag.lower()
        last_state = self.__state[-1]

        if ltag == 'h3':
            self.__state.append(CelebritySearchPageVisitor.STATE_SEARCH_RESULT)
        elif ltag == 'a':
            if last_state == CelebritySearchPageVisitor.STATE_SEARCH_RESULT:
                if "href" in attrs_dict:
                    self.__search_result_url = attrs_dict["href"]
                self.__state.append(CelebritySearchPageVisitor.STATE_NAME_START)
        else:
            pass
    def handle_endtag(self, tag):
        ltag = tag.lower()
        last_state = self.__state[-1]
        if ltag == 'h3':
            if last_state == CelebritySearchPageVisitor.STATE_SEARCH_RESULT:
                self.__state.pop()
        elif ltag == 'a':
            if last_state == CelebritySearchPageVisitor.STATE_NAME_START:
                self.__state.pop()

    def handle_data(self, data):
        last_state = self.__state[-1]
        if last_state == CelebritySearchPageVisitor.STATE_NAME_START:
            self.__name = data.rstrip().lstrip()

class CelebrityPageVisitor(HP.HTMLParser):
    __year_only = re.compile(r'(\d\d\d\d)')
    __full_date = re.compile(r'(\d\d\d\d-\d+-\d+)')

    STATE_IDLE = 0
    STATE_INFO_START = 1
    STATE_GET_FIELD = 2
    STATE_DOB = 3
    STATE_DOBD = 4
    STATE_POB = 5
    STATE_GENDER = 6
    STATE_IMDB_LINK = 7

    def __init__(self, html_content):
        HP.HTMLParser.__init__(self)
        self.__state = [CelebrityPageVisitor.STATE_IDLE]
        self.__gender = Celebrity.UNKNOWN_GENDER
        self.__search_result_url = None
        self.__day_of_birth = None
        self.__day_of_death = None
        self.__place_of_birth = None
        self.__imdb_link = None
        self.feed(html_content)
        self.reset()

    def search_result_url(self):
        return self.__search_result_url
    def day_of_birth(self):
        return self.__day_of_birth
    def day_of_death(self):
        return self.__day_of_death
    def place_of_birth(self):
        return self.__place_of_birth
    def imdb_link(self):
        return self.__imdb_link
    def gender(self):
        return self.__gender

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        ltag = tag.lower()
        last_state = self.__state[-1]

        if ltag == 'div':
            if "class" in attrs_dict and attrs_dict["class"] == 'info':
                self.__state.append(CelebrityPageVisitor.STATE_INFO_START)
        elif ltag == 'span':
            if last_state == CelebrityPageVisitor.STATE_INFO_START:
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
        elif ltag == 'a':
            if last_state == CelebrityPageVisitor.STATE_IMDB_LINK:
                if "href" in attrs_dict:
                    self.__imdb_link = attrs_dict["href"]
                self.__state.pop()
        else:
            pass
    def handle_endtag(self, tag):
        ltag = tag.lower()
        last_state = self.__state[-1]
        if ltag == 'a':
            if last_state == CelebrityPageVisitor.STATE_IMDB_LINK:
                self.__state.pop()
        elif ltag == 'span':
            if last_state == CelebrityPageVisitor.STATE_GET_FIELD:
                self.__state.pop()
        elif ltag == 'div':
            if last_state == CelebrityPageVisitor.STATE_INFO_START:
                self.__state.pop()

    def handle_data(self, data):
        last_state = self.__state[-1]
        data = data.lstrip().rstrip()
        if last_state == CelebrityPageVisitor.STATE_GET_FIELD:
            if data == u'出生日期':
                self.__state[-1] = CelebrityPageVisitor.STATE_DOB
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
            elif data == u'生卒日期':
                self.__state[-1] = CelebrityPageVisitor.STATE_DOBD
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
            elif data == u'出生地':
                self.__state[-1] = CelebrityPageVisitor.STATE_POB
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
            elif data == u'性别':
                self.__state[-1] = CelebrityPageVisitor.STATE_GENDER
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
            elif data == u'imdb编号':
                self.__state[-1] = CelebrityPageVisitor.STATE_IMDB_LINK
                self.__state.append(CelebrityPageVisitor.STATE_GET_FIELD)
                pass
        elif last_state == CelebrityPageVisitor.STATE_DOB:
            # Format: year or year-month-day
            matched = CelebrityPageVisitor.__full_date.search(data)
            if matched is not None:
                self.__day_of_birth = matched.group(1)
            else:
                matched = CelebrityPageVisitor.__year_only.search(data)
                if matched is not None:
                    self.__day_of_birth = matched.group(1)
            # We don't assume every page has date of birth
            self.__state.pop()
        elif last_state == CelebrityPageVisitor.STATE_DOBD:
            # Format: year or year-month-day
            matched = CelebrityPageVisitor.__full_date.findall(data)
            if matched is not None:
                self.__day_of_birth = matched[0]
                self.__day_of_death = matched[1]
            else:
                matched = CelebrityPageVisitor.__year_only.findall(data)
                if matched is not None:
                    self.__day_of_birth = matched[0]
                    self.__day_of_death = matched[1]
            # We don't assume every page has date of birth
            self.__state.pop()
        elif last_state == CelebrityPageVisitor.STATE_POB:
            if data[0] == u':':
                self.__place_of_birth = data[1:].lstrip().rstrip()
            else:
                self.__place_of_birth = data
            self.__state.pop()
        elif last_state == CelebrityPageVisitor.STATE_GENDER:
            if data.find(u'男'):
                self.__gender = Celebrity.MALE
            elif data.find(u'女'):
                self.__gender = Celebrity.FEMALE
            else:
                self.__gender = Celebrity.UNKNOWN_GENDER
            self.__state.pop()
        else:
            pass


# TODO: 出生日期 生卒日期两种

class MoviePageVisitor(HP.HTMLParser):
    # State automaton
    STATE_IDLE = 0
    STATE_MOVIE_INFO_START = 1
    STATE_PROFESSION_START = 2
    STATE_DIRECTOR_START = 3
    STATE_SCRIPTWRITER_START = 4
    STATE_ACTOR_START = 5
    STATE_PROFESSION_GET_ROLE = 6
    GET_NEW_CELEBRITY = 8
    STATE_PLACEHOLDER = 9
    STATE_RELATED_MOVIE_START = 10
    STATE_MOVIE_TITLE_START = 11
    STATE_MOVIE_YEAR_START = 12
    STATE_REGION_START = 13

    def __init__(self, html_content):
        HP.HTMLParser.__init__(self)
        self.__state = [MoviePageVisitor.STATE_IDLE]
        self.__tag_stack = []
        self.__new_celebrity = None
        self.__related_movie_urls = []
        self.__title = None
        self.__year = None
        self.__region = None
        self.__celebrities = {
                MoviePageVisitor.STATE_DIRECTOR_START: [],
                MoviePageVisitor.STATE_SCRIPTWRITER_START: [],
                MoviePageVisitor.STATE_ACTOR_START: []
        }
        self.feed(html_content)
        self.reset()

    def directors(self):
        return self.__celebrities[MoviePageVisitor.STATE_DIRECTOR_START]
    def scriptwriters(self):
        return self.__celebrities[MoviePageVisitor.STATE_SCRIPTWRITER_START]
    def actors(self):
        return self.__celebrities[MoviePageVisitor.STATE_ACTOR_START]
    def related_movie_urls(self):
        return self.__related_movie_urls
    def title(self):
        return self.__title
    def year(self):
        return self.__year
    def region(self):
        return self.__region

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        ltag = tag.lower()
        last_state = self.__state[-1]

        if ltag == 'div':
            if "id" in attrs_dict and attrs_dict["id"] == 'info':
                self.__state.append(MoviePageVisitor.STATE_MOVIE_INFO_START)
            elif "class" in attrs_dict and \
                    attrs_dict["class"] == 'recommendations-bd':
                self.__state.append(MoviePageVisitor.STATE_RELATED_MOVIE_START)
            else:
                pass
        elif ltag == 'span':
            if "class" in attrs_dict and attrs_dict["class"] == 'pl':
                # Update state of parent level: It should be the start
                # of events
                if last_state == MoviePageVisitor.STATE_MOVIE_INFO_START:
                    self.__state.append(MoviePageVisitor.STATE_PROFESSION_START)
            elif "property" in attrs_dict and \
                    attrs_dict["property"] == "v:itemreviewed":
                self.__state.append(MoviePageVisitor.STATE_MOVIE_TITLE_START)
            elif "class" in attrs_dict and attrs_dict["class"] == "year":
                self.__state.append(MoviePageVisitor.STATE_MOVIE_YEAR_START)
            elif "property" in attrs_dict and \
                    attrs_dict["property"] == "v:initialReleaseDate":
                if "content" in attrs_dict:
                    self.__year = attrs_dict["content"]
                    logging.info("Year found from info: %s" % self.__year)
            else:
                pass
        elif ltag == 'a':
            if last_state == MoviePageVisitor.STATE_DIRECTOR_START or \
               last_state == MoviePageVisitor.STATE_SCRIPTWRITER_START or \
               last_state == MoviePageVisitor.STATE_ACTOR_START:
                if "href" in attrs_dict:
                    # Get URL of celebrities, the name of each celebrity
                    # can only be retrieved from handle_data
                    self.__new_celebrity = {}
                    # Make sure the URL matches the content 
                    m = Celebrity.celebrity_pattern.match(attrs_dict["href"])
                    if m is not None:
                        self.__new_celebrity["douban_id"] = m.group(1)
                    else:
                        self.__new_celebrity["douban_id"] = attrs_dict["href"]
                    self.__new_celebrity["profession"] = last_state
                    self.__state.append(MoviePageVisitor.GET_NEW_CELEBRITY)
            elif last_state == MoviePageVisitor.STATE_RELATED_MOVIE_START:
                self.__related_movie_urls.append(attrs_dict["href"])
            else:
                pass
        else:
            pass

    def handle_endtag(self, tag):
        ltag = tag.lower()
        last_state = self.__state[-1]
        if ltag == 'a':
            if last_state == MoviePageVisitor.GET_NEW_CELEBRITY or \
               last_state == MoviePageVisitor.STATE_MOVIE_TITLE_START or \
               last_state == MoviePageVisitor.STATE_MOVIE_YEAR_START:
                self.__state.pop()
            else:
                pass
        elif ltag == 'span':
            if last_state == MoviePageVisitor.STATE_DIRECTOR_START or \
               last_state == MoviePageVisitor.STATE_SCRIPTWRITER_START or \
               last_state == MoviePageVisitor.STATE_ACTOR_START or \
               last_state == MoviePageVisitor.STATE_PROFESSION_GET_ROLE or \
               last_state == MoviePageVisitor.STATE_MOVIE_TITLE_START or \
               last_state == MoviePageVisitor.STATE_MOVIE_YEAR_START or \
               last_state == MoviePageVisitor.STATE_PLACEHOLDER:
                self.__state.pop()
            elif last_state == MoviePageVisitor.STATE_PROFESSION_START:
                # Can't happen here now. All PROFESSION_START are either
                # replaced to real fetch start flag, or placeholder.
                assert False
        elif ltag == 'div':
            if last_state == MoviePageVisitor.STATE_MOVIE_INFO_START:
                self.__state.pop()
            elif last_state == MoviePageVisitor.STATE_RELATED_MOVIE_START:
                self.__state.pop()
            else:
                pass

    def handle_data(self, data):
        data = data.lstrip().rstrip()
        last_state = self.__state[-1]
        if last_state == MoviePageVisitor.STATE_PROFESSION_START:
            if data == u'导演':
                self.__state[-1] = MoviePageVisitor.STATE_DIRECTOR_START
                self.__state.append(MoviePageVisitor.STATE_PLACEHOLDER)
            elif data == u'编剧':
                self.__state[-1] = MoviePageVisitor.STATE_SCRIPTWRITER_START
                self.__state.append(MoviePageVisitor.STATE_PLACEHOLDER)
            elif data == u'主演':
                self.__state[-1] = MoviePageVisitor.STATE_ACTOR_START
                self.__state.append(MoviePageVisitor.STATE_PLACEHOLDER)
            elif data == u'制片国家/地区:':
                # Trick: The region info is different with other fields
                # because it's totally out of scope of span, so we have
                # to insert STATE_REGION_START before GET_ROLE, so next
                # space and receive it.
                self.__state[-1] = MoviePageVisitor.STATE_REGION_START
                self.__state.append(MoviePageVisitor.STATE_PLACEHOLDER)
            else:
                self.__state[-1] = MoviePageVisitor.STATE_PLACEHOLDER
        elif last_state == MoviePageVisitor.STATE_REGION_START:
            self.__region = data
            # This state is special because it's marked for a data
            # section, not for any tag.
            self.__state.pop()
        elif last_state == MoviePageVisitor.GET_NEW_CELEBRITY:
            self.__new_celebrity["name"] = data
            # Now we get full information of a new celebrity
            prof = self.__new_celebrity["profession"]
            self.__celebrities[prof].append(self.__new_celebrity)
            self.__new_celebrity = None
        elif last_state == MoviePageVisitor.STATE_MOVIE_TITLE_START:
            self.__title = data
        elif last_state == MoviePageVisitor.STATE_MOVIE_YEAR_START:
            if self.__year is None:
                self.__year = data[1:-1]
                logging.info("MoviePageVisitor: First year found from h1: %s" \
                                % self.__year)

class Movie(object):
    __movie_url_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/?")
    __param_removal_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/subject\/([0-9][0-9]*)\/(\?.*)?$")
    def __init__(self, douban_url_id, fetch_on_init = False):
        """
        Movie.__init__(self, douban_url_id, fetch_on_init = False)

        Initialize Movie object. An valid ID in Douban's URL is required
        to construct full URL and fetch details from network.

        It also allows caller to choose whether immediately fetch before
        __init__() complete.
        """
        self.__movie_id = douban_url_id
        self.__unique_id = None
        self.__title = None
        self.__year = None
        self.__region = None
        self.__related_movies = []
        self.__celebrities = []
        if fetch_on_init:
            self.fetch()

    def url(self):
        # We don't keep URL all the time, as it's not really useful for
        # spider. Keeping a movie_id is good enough.
        return Movie.reformat_movie_url(self.__movie_id)

    def douban_id(self):
        return self.__movie_id
    def unique_id(self):
        return self.__unique_id
    def title(self):
        return self.__title
    def year(self):
        return self.__year
    def region(self):
        return self.__region
    def celebrities(self):
        return self.__celebrities
    def related_movies(self):
        """
        Movie.related_movies() -> List of movie objects

        Return a list of related movies, found from HTML page. The
        IDs can be used to regenerate full movie page URL with
        Movie.reformat_movie_url().
        """
        return self.__related_movies

    def fetch(self):
        """
        Perform a fetch from Douban URL and parse received data from
        HTML content. After fetch all fields are updated.
        """
        logging.info("MoviePageVisitor: Fetching: %s", self.__movie_id)
        m = MoviePageVisitor(parsehtml(self.url()))
        celebrities = []
        for each_director in m.directors():
            new_celebrity = Celebrity(each_director["douban_id"])
            new_celebrity.profession(Celebrity.DIRECTOR)
            new_celebrity.name(each_director["name"])
            celebrities.append(new_celebrity)
        for each_actor in m.actors():
            new_celebrity = Celebrity(each_actor["douban_id"])
            new_celebrity.profession(Celebrity.ACTOR)
            new_celebrity.name(each_actor["name"])
            celebrities.append(new_celebrity)
        for each_scriptwriter in m.scriptwriters():
            new_celebrity = Celebrity(each_scriptwriter["douban_id"])
            new_celebrity.profession(Celebrity.SCRIPTWRITER)
            new_celebrity.name(each_scriptwriter["name"])
            celebrities.append(new_celebrity)
        related_movies = []
        for each_urls in m.related_movie_urls():
            each_movie_douban_id = Movie.parse_movie_id(each_urls)
            new_movie = Movie(each_movie_douban_id)
            related_movies.append(new_movie)

        self.__related_movies = related_movies
        self.__celebrities = celebrities
        self.__title = m.title()
        self.__year = m.year()
        self.__region = m.region()
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
    """
    This is only a place holder for fetching celebrity web page. Will be
    used in the next version.
    """
    celebrity_pattern = re.compile("\/celebrity\/([0-9][0-9]*)\/")
    __celebrity_url_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/celebrity\/([0-9][0-9]*)\/?")
    __param_removal_pattern = \
            re.compile(r"http:\/\/movie\.douban\.com\/celebrity\/([0-9][0-9]*)\/(\?.*)?$")
    __search_pattern = re.compile(r'\/search\/.*')

    DIRECTOR = 1
    SCRIPTWRITER = 2
    ACTOR = 3

    FEMALE = 0
    MALE = 1
    UNKNOWN_GENDER = 2

    def __init__(self, douban_url_id, fetch_on_init = False):
        """
        Celebrity.__init__(self, douban_url_id, fetch_on_init = False)

        Create an Celebrity object. In current version, Celebrity object
        does not support fetch() method.
        """
        self.__celebrity_id = douban_url_id
        self.__name = None
        self.__profession = None
        self.__unique_id = None
        self.__day_of_birth = None
        self.__day_of_death = None
        self.__place_of_birth = None
        self.__imdb_link = None
        self.__gender = Celebrity.UNKNOWN_GENDER

        if fetch_on_init:
            self.fetch()

    def unique_id(self):
        return self.__unique_id
    def douban_id(self):
        return self.__celebrity_id

    def name(self, new_name = None):
        if new_name is not None:
            old_name = self.__name
            self.__name = new_name
            return old_name
        return self.__name

    def profession(self, new_profession = None):
        if new_profession is not None:
            old_profession = self.__profession
            self.__profession = new_profession
            return old_profession
        return self.__profession

    def day_of_birth(self):
        return self.__day_of_birth
    def day_of_death(self):
        return self.__day_of_death
    def place_of_birth(self):
        return self.__place_of_birth
    def imdb_link(self):
        return self.__imdb_link
    def gender(self):
        return self.__gender

    def fetch(self):
        # A special case: self.__celebrity_id can be set as a format
        # like /search/name. We must fetch it to get result.
        matched = Celebrity.__search_pattern.match(self.__celebrity_id)
        if matched is not None:
            search_id = self.__celebrity_id 
            # Oh yes, we got a search page instead of real user page.
            logging.info("CelebritySearchPageVisitor: Second search: %s" \
                    % self.__celebrity_id)
            search_url = "http://movie.douban.com%s" % self.__celebrity_id
            # Get HTML content, search for h3 tag, and get <a>
            # under it as the real path.
            c = CelebritySearchPageVisitor(parsehtml(search_url))
            # Update the id to real page
            result_url = c.search_result_url()
            self.__celebrity_id = Celebrity.parse_celebrity_id(result_url)
            self.__name = c.name()
            logging.info("CelebritySearchPageVisitor: Redirect %s => %s" \
                    % (search_id, self.__celebrity_id))
        full_url = Celebrity.reformat_celebrity_url(self.__celebrity_id)
        c = CelebrityPageVisitor(parsehtml(full_url))
        self.__gender = c.gender()
        self.__day_of_birth = c.day_of_birth()
        self.__day_of_death = c.day_of_death()
        self.__place_of_birth = c.place_of_birth()
        self.__imdb_link = c.imdb_link()
        # NOTE: We don't update profession. In a lot of cases, one
        # person may have multiple professions. So we leave it to
        # movie_profession_map table.

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
    PLACEHOLDER = "_NaN_"

    __table_params = {
        'v1_celebrity_info': ('unique_id',
                              'douban_id',
                              'name',
                              'gender',
                              'day_of_birth',
                              'day_of_death',
                              'place_of_birth',
                              'imdb_link'),
        'v1_movie_info': ('unique_id',
                          'douban_id',
                          'title',
                          'year',
                          'region'),
        'v1_movie_profession_map': ('movie_douban_id',
                                    'celebrity_douban_id',
                                    'profession'),
        'v1_partial_movie_info': ('douban_id')
    }
    __table_creations = {
        'v1_celebrity_info': """create table v1_celebrity_info (
                                unique_id text,
                                douban_id text,
                                name text,
                                gender integer,
                                day_of_birth text,
                                place_of_birth text,
                                day_of_death text,
                                imdb_link text)""",
        'v1_movie_info': """create table v1_movie_info (
                            unique_id text,
                            douban_id text,
                            title text,
                            year text,
                            region text)""",
        'v1_movie_profession_map': \
                """create table v1_movie_profession_map (
                   movie_douban_id text,
                   celebrity_douban_id text,
                   profession integer)""",
        'v1_partial_movie_info': """create table v1_partial_movie_info (
                            douban_id text)"""

        }
    def __init__(self, sqlite_db_path):
        """
        Sqlite3Host.__init__(self, sqlite_db_path)

        Write data to a SQLite3 database.
        """
        self.__sqlite_db_path = sqlite_db_path
        self.__conn = None

    def start(self):
        """
        Sqlite3Host.start()

        Really start database. This is required to allow database like
        SQlite3 start only in the same working thread.
        """
        if self.__conn is not None:
            return
        self.__conn = sqlite3.connect(self.__sqlite_db_path)
        self.__create_table()

    def save(self, obj, commit = True):
        """
        Sqlite3Host.save(self, obj, commit = True)

        Save object in database. Supports only :Movie: and :Celebrity:.

        The commit parameter is used to determine this save() call
        should be commit to underlying database immediately. If commit
        is set to False, caller must call another
        Sqlite3Host.save(commit = True) or Sqlite3Host.commit(). This
        step is useful if there are a lot of save() operations to be
        performed and developer really concerns about performance.
        However, in most cases we can safely use default commit = True.
        """
        if self.__conn is None:
            raise DatabaseNotStartedException()
        if type(obj) is Movie:
            logging.info("Sqlite3Host: Save Movie: %s %s" % \
                    (obj.title(), obj.douban_id()))
            movie_insertion = """
                insert into v1_movie_info values (?, ?, ?, ?, ?)
            """
            movie_profession_map = """
                 insert into v1_movie_profession_map values (?, ?, ?)
            """
            movie_partial_insertion = """
                insert into v1_partial_movie_info values (?)
            """
            if self.__is_movie_partial(obj):
                # We have to leave all partial movies to a seperated
                # table, because Sqlite3 does not support dropping
                # column from table. If we leave all partial data in
                # same table, they can't be easily rewritten.
                #
                # A typical scenario is developer hit CTRL-C during
                # fetching. Then a long list will be save for next fetch
                # and they are all partial. We can't let them in
                # existing table.
                #
                # For the same reason, we don't need celebrities from
                # partial movie. They will be retrieved at next fetch.
                self.__conn.execute(movie_partial_insertion, \
                                    (self.__v(obj.douban_id()), ))
            else:
                self.__conn.execute(movie_insertion, \
                        (self.__v(obj.unique_id()), \
                         self.__v(obj.douban_id()), \
                         self.__v(obj.title()), \
                         self.__v(obj.year()), \
                         self.__v(obj.region())))
                for each_celebrity in obj.celebrities():
                    celebrity_douban_id = each_celebrity.douban_id()
                    celebrity_profession = each_celebrity.profession()
                    self.__conn.execute(movie_profession_map, \
                            (self.__v(obj.douban_id()), \
                             self.__v(celebrity_douban_id), \
                             self.__v(celebrity_profession)))

        elif type(obj) is Celebrity:
            logging.info("Sqlite3Host: Save Celebrity: %s %s, %s" % \
                    (obj.name(), obj.douban_id(), obj.profession()))
            celebrity_insertion = """
                insert into v1_celebrity_info values (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.__conn.execute(celebrity_insertion, \
                    (self.__v(obj.unique_id()), \
                     self.__v(obj.douban_id()), \
                     self.__v(obj.name()), \
                     self.__v(obj.gender()), \
                     self.__v(obj.day_of_birth()), \
                     self.__v(obj.day_of_death()), \
                     self.__v(obj.place_of_birth()), \
                     self.__v(obj.imdb_link())))
        else:
            raise UnsupportedDataException(type(obj).__name__)
        if commit:
            self.__conn.commit()

    def __is_celebrity_partial(self, obj):
        # This version we use a very weak condition to predict celebrity
        # to be "completed" (thus, partial == False), so it won't be
        # reloaded. It will be changed in the future.
        if obj.name() is not None and obj.douban_id() is not None:
            return 0 # partial == False
        else:
            return 1
    def __is_movie_partial(self, obj):
        if obj.title() is not None and obj.douban_id() is not None \
                and obj.year() is not None:
            return 0 # partial == False
        else:
            return 1

    def __v(self, value):
        if value is None:
            return Sqlite3Host.PLACEHOLDER
        else:
            return value

    def save_list(self, obj_list):
        """
        Sqlite3Host.save_list(self, obj_list)

        Save a list of objects to database. Supports only
        :Movie: and :Celebrity:.
        """
        if self.__conn is None:
            raise DatabaseNotStartedException()
        for each in obj_list:
            self.save(each, False)
        self.__conn.commit()

    def commit(self):
        if self.__conn is None:
            raise DatabaseNotStartedException()
        self.__conn.commit()

    def load_partial_movie_ids(self):
        if self.__conn is None:
            raise DatabaseNotStartedException()
        logging.info("Sqlite3Host: Load partial movie Ids")
        query = "select douban_id from v1_partial_movie_info"
        cursor = self.__conn.execute(query)
        columns = cursor.fetchall()
        ids = [each[0] for each in columns]
        logging.info("Sqlite3Host: Ids loaded: %d" % len(ids))
        logging.info("Sqlite3Host: Drop partial movie table")
        drop = "drop table v1_partial_movie_info"
        self.__conn.execute(drop)
        logging.info("Sqlite3Host: Recreate partial movie table")
        create = Sqlite3Host.__table_creations["v1_partial_movie_info"]
        self.__conn.execute(create)
        self.__conn.commit()
        logging.info("Sqlite3Host: Partial movie table created.")
        return ids

    def __create_table(self):
        tables = Sqlite3Host.__table_params.keys()
        query = '''select :table_name from sqlite_master where
                   type='table' and name=:table_name'''
        for each_table in tables:
            cur = self.__conn.execute(query, {'table_name': each_table})
            if cur.fetchone() is None: # A table does not exist
                logging.info("Create table %s." % each_table)
                create = Sqlite3Host.__table_creations[each_table]
                self.__conn.execute(create)
            else:
                logging.info("Table %s exists. Use it." % each_table)
        self.__conn.commit()
        # Now all tables are created

class Spider(object):
    """
    Main entry for fetching data from remote URL and save data to
    database.
    """
    def __init__(self, db_host, max_movies = 0, fetch_gap_in_secs = 2):
        # The pending items tracks all known URLs that hasn't been
        # downloaded. When the fetching is done, the pending list is
        # written to database.
        self.__index = {
            'movies': [],
            'parsed_movies': set(),
            "parsed_celebrities": set()
        }
        self.__db_host = db_host
        self.__stop_sign = threading.Condition()
        self.__started = False
        self.__background = threading.Thread(target=self.__worker_thread)
        self.__fetch_gap = fetch_gap_in_secs
        self.__max_movies = max_movies
        self.__complete_callbacks = []

    def set_movie_seed(self, seed_movie_douban_id):
        self.__index["movies"].append(seed_movie_douban_id)

    def set_complete_callback(self, complete_callback):
        self.__stop_sign.acquire()
        self.__complete_callbacks.append(complete_callback)
        self.__stop_sign.release()

    def start(self):
        """
        Spider.start(self)

        Start background thread, write all fetched data to database.
        This function requires a movie url as a seed.
        
        Please also note that if given database also contains pending
        movies, they will be processed as well.
        """
        if self.__started is True:
            # No need to stop twice.
            return
        self.__stop_sign.acquire()
        self.__background.start()
        self.__started = True
        self.__stop_sign.release()

    def stop(self):
        """
        Spider.stop(self)

        Stop background thread, write all fetched data to database. When
        it's done, it will call end_callback() once.
        """
        if self.__started is False:
            # No need to stop twice.
            return
        self.__stop_sign.acquire() # Post a condition so they know
        self.__started = False
        self.__stop_sign.notify()
        self.__stop_sign.release()

    def __worker_thread(self):
        logging.info("Worker: starts.")
        self.__stop_sign.acquire()
        logging.info("Worker: lock acquired.")
        try:
            self.__db_host.start()
            # Load pending items from last fetch.
            # NOTE: We don't keep tracking parsed items from last fetch.
            self.__index["movies"] += self.__db_host.load_partial_movie_ids()
            self.__index["parsed_movies"] = set([])
            self.__index["parsed_celebrities"] = set([])

            while len(self.__index["movies"]) != 0:
                # After every fetch, wait for 2 secs so caller can stop.
                self.__stop_sign.wait(self.__fetch_gap)
                if self.__started is False:
                    # OK if somebody asks us to stop. Save all pending list
                    # and exit.
                    break
                else:
                    if self.__max_movies > 0:
                        parsed_movies = len(self.__index["parsed_movies"])
                        if self.__max_movies == parsed_movies:
                            logging.info("Worker: Movie limit reached. Stop.")
                            break
                    # We can continue. Note: stop sign is grabbed by worker
                    # so caller can't stop it at this moment. This is to
                    # make sure a fetch can't be interrupted.
                    new_movie_id = self.__index["movies"].pop()
                    new_movie = Movie(new_movie_id, fetch_on_init = True)
                    self.__index["parsed_movies"].add(new_movie.douban_id())
                    for each_related_movie in new_movie.related_movies():
                        each_movie_id = each_related_movie.douban_id()
                        if each_movie_id not in self.__index["parsed_movies"]:
                            # The item is not retrived. Add to list.
                            self.__index["movies"].append(each_movie_id)
                    # Besides saving movie information, we also need to save
                    # celebrities indepdently
                    for each_celebrity in new_movie.celebrities():
                        each_celebrity.fetch()
                        each_id = each_celebrity.douban_id()
                        if each_id not in self.__index["parsed_celebrities"]:
                            self.__db_host.save(each_celebrity)
                            self.__index["parsed_celebrities"].add(each_id)
                    # Movie must be save AFTER celebrities because the
                    # path of celebrities can be updated on fetch().
                    self.__db_host.save(new_movie)


            # We have fetched all movies and celebrities. Stop.
            pending_movies = len(self.__index["movies"])
            parsed_movies = len(self.__index["parsed_movies"])
            parsed_celebrities = len(self.__index["parsed_celebrities"])
            logging.info("Worker: %d movies parsed." % parsed_movies)
            logging.info("Worker: %d celebrities parsed." % (parsed_celebrities))
            if pending_movies > 0:
                logging.info("Worker: %d movies pending." % (pending_movies))
                # Remove duplcations, but order may change.
                dedup_ids = list(set(self.__index["movies"]))
                logging.info("Worker: Dedup: %d IDs left." % len(dedup_ids))
                saved_movies = [Movie(each) for each in dedup_ids]
                self.__db_host.save_list(saved_movies)
            self.__started = False
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logging.error("FATAL: Exception from workder: %s" % tb)
        try:
            for each_callback in self.__complete_callbacks:
                if each_callback is not None:
                    each_callback()
        finally:
            logging.info("Worker: Callback invoked.")
        self.__stop_sign.release()
        logging.info("Worker: Complete. Bye.")

if __name__ == '__main__':
    import argparse
    import traceback
    import signal
    parser = argparse.ArgumentParser(description="""
    Example: Demonstrate douban spider for Ruuxee
    """)
    parser.add_argument('-l',\
                        '--log', \
                        default="ruuxee_douban_spider.log", \
                        help="Path to log file.")
    parser.add_argument('-d',\
                        '--db', \
                        default="ruuxee_douban_spider.db", \
                        help="Path to database file.")
    parser.add_argument('-s',\
                        '--seedurl', \
                        default="http://movie.douban.com/subject/3266615/", \
                        help="An URL to default starting movie.")
    parser.add_argument('-m',\
                        '--maxmovies', \
                        default="15", \
                        help="Maximum movies to be parsed. 0 means unlimited.")

    args = parser.parse_args()
    formatter = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(filename=args.log, \
                        format=formatter, \
                        level=logging.DEBUG)
    class CompletionWaiter(object):
        def __init__(self):
            self.__condition = threading.Condition()
            self.__done = False
        def __call__(self):
            # Call from worker thread
            self.__condition.acquire()
            self.__done = True
            self.__condition.notify()
            self.__condition.release()
            pass
        def wait(self):
            # Call from main thread
            self.__condition.acquire()
            while True:
                self.__condition.wait(10)
                logging.info("Waiter: wait for completion...")
                if self.__done:
                    break
            self.__condition.release()
    class OnSignalHandle(object):
        def __init__(self, spider, waiter):
            self.__spider = spider
            self.__waiter = waiter
        def __call__(self, signum, frame):
            self.__spider.stop()
            self.__waiter.wait()
    try:
        db = Sqlite3Host(args.db)
        maxmovies = int(args.maxmovies)
        spider = Spider(db, max_movies = maxmovies)
        waiter = CompletionWaiter()
        spider.set_complete_callback(waiter)
        douban_id = Movie.parse_movie_id(args.seedurl)
        spider.set_movie_seed(douban_id) # Can see bug
        signal.signal(signal.SIGINT, OnSignalHandle(spider, waiter))
        spider.start()
        waiter.wait()
        sys.exit(0)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error("FATAL: Exception from main: %s" % tb)
        print("Error: Fail to start spider. Check log for details.")
        sys.exit(1)
