#!/usr/bin/env python
# pylint: disable=line-too-long
# pylint: disable=W0702, W0703, C0103, C0410
# encoding=utf8
'''
# GayHotMovies (IAFD)
                                    Version History
                                    ---------------
    Date            Version             Modification
    12 Aug 2019   2019.08.12.01    Creation
    25 Apr 2020   2019.08.12.02    added multiple result pages handling
                                   removed debug print option
                                   improved error handling
    23 May 2020   2019.08.12.03    Added scene breakdown to summary
    01 Jun 2020   2019.08.12.04    Implemented translation of summary
                                   improved getIAFDActor search
    27 Jun 2020   2019.08.12.05    Improvement to Summary Translation: Translate into Plex Library Language
                                   stripping of intenet domain suffixes from studio names when matching
                                   handling of unicode characters in film titles and comparision string normalisation
    30 Aug 2020   2019.08.12.06    Handling of Roman Numerals in Titles to Match Arabic Numerals
                                   dodgy xpath around site studio name corrected
    12 Sep 2020   2019.08.12.07    Improved search facility - titles with non alphabetic characters like "!" 
                                   were failing to search... took code from GEVI
    07 Oct 2020   2019.08.12.08    IAFD - change to https
    16 Jan 2021   2019.08.12.09    Improved on IAFD search, actors sexual roles if recorded are returned, if not shows a red circle.
    19 Feb 2021   2019.08.12.11    Moved IAFD and general functions to other py files
                                   Enhancements to IAFD search routine, including LevenShtein Matching on Cast names
                                   set content_rating age to 18
                                   Set collections from filename + countries, cast and directors
                                   Added directors photos
                                   included studio on iafd processing of filename
                                   Added iafd legend to summary
                                   improved logging
---------------------------------------------------------------------------------------------------------------
'''
import datetime, platform, os, re, sys, json
from unidecode import unidecode
from googletrans import Translator

# Version / Log Title
VERSION_NO = '2019.08.12.11'
PLUGIN_LOG_TITLE = 'GayHotMovies'
LOG_BIGLINE = '------------------------------------------------------------------------------'
LOG_SUBLINE = '      ------------------------------------------------------------------------'

# Preferences
REGEX = Prefs['regex']                      # file matching pattern
YEAR = Prefs['year']                        # is year mandatory in the filename?
DELAY = int(Prefs['delay'])                 # Delay used when requesting HTML, may be good to have to prevent being banned from the site
DETECT = Prefs['detect']                    # detect the language the summary appears in on the web page
PREFIXLEGEND = Prefs['prefixlegend']        # place cast legend at start of summary or end
COLCLEAR = Prefs['clearcollections']        # clear previously set collections
COLSTUDIO = Prefs['studiocollection']       # add studio name to collection
COLTITLE = Prefs['titlecollection']         # add title [parts] to collection
COLGENRE = Prefs['genrecollection']         # add genres to collection
COLDIRECTOR = Prefs['directorcollection']   # add director to collection
COLCAST = Prefs['castcollection']           # add cast to collection
COLCOUNTRY = Prefs['countrycollection']     # add country to collection
BACKGROUND = Prefs['background']            # download art
ACT_AS_GENRE = Prefs['acts']                # using sex acts as categories

# IAFD Related variables
IAFD_BASE = 'https://www.iafd.com'
IAFD_SEARCH_URL = IAFD_BASE + '/results.asp?searchtype=comprehensive&searchstring={0}'

IAFD_ABSENT = u'\U0000274C'        # red cross mark - not on IAFD
IAFD_FOUND = u'\U00002705'         # heavy white tick on green - on IAFD
IAFD_THUMBSUP = u'\U0001F44D'      # thumbs up unicode character
IAFD_THUMBSDOWN = u'\U0001F44E'    # thumbs down unicode character
IAFD_LEGEND = u'CAST LEGEND\u2003{0} Actor not on IAFD\u2003{1} Actor on IAFD\u2003:: {2} Film on IAFD ::\n'

# URLS
BASE_URL = 'https://www.gayhotmovies.com'
BASE_SEARCH_URL = BASE_URL + '/search.php?num_per_page=48&&page_sort=relevance&search_string={0}&find_with=all&searchtype_value=video_title'

# dictionary holding film variables
FILMDICT = {}

# Date Format used by website
DATEFORMAT = '%b %d, %Y'

# Website Language
SITE_LANGUAGE = 'en'

# Max delta between file duration and film duration for chapters
DURATION_DETLA_THRESHOLD = 90000

# ----------------------------------------------------------------------------------------------------------------------------------
def Start():
    ''' initialise process '''
    HTTP.CacheTime = CACHE_1WEEK
    HTTP.Headers['User-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.113 Safari/537.36'

# ----------------------------------------------------------------------------------------------------------------------------------
def ValidatePrefs():
    ''' validate changed user preferences '''
    pass

# ----------------------------------------------------------------------------------------------------------------------------------
def anyOf(iterable):
    '''  used for matching strings in lists '''
    for element in iterable:
        if element:
            return element
    return None

# ----------------------------------------------------------------------------------------------------------------------------------
class GayHotMovies(Agent.Movies):
    ''' define Agent class '''
    name = 'GayHotMovies (IAFD)'
    languages = [Locale.Language.English]
    primary_provider = False
    preference = True
    media_types = ['Movie']
    contributes_to = ['com.plexapp.agents.GayAdult', 'com.plexapp.agents.GayAdultFilms']

    # import IAFD Functions
    from iafd import *

    # import General Functions
    from genfunctions import *

    # -------------------------------------------------------------------------------------------------------------------------------
    def CleanSearchString(self, myString):
        ''' Prepare Title for search query '''
        self.log('AGNT  :: Original Search Query        : {0}'.format(myString))

        myString = myString.strip().lower()
        nullChars = ["'", ',' '&', '!', '.', '#'] # to be replaced with null
        pattern = u'[{0}]'.format(''.join(nullChars))
        matched = re.search(pattern, myString)  # match against whole string
        if matched:
            self.log('AGNT  :: Search Query:: Replacing characters in string. Found one of these {0}'.format(pattern))
            myString = re.sub(pattern, '', myString)
            myString = ' '.join(myString.split())   # remove continous white space
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: String has none of these {0}'.format(pattern))

        spaceChars = ['-', ur'\u2013', ur'\u2014', '(', ')']  # to be replaced with space
        pattern = u'[{0}]'.format(''.join(spaceChars))
        matched = re.search(pattern, myString)  # match against whole string
        if matched:
            self.log('AGNT  :: Search Query:: Replacing characters with Space. Found one of these {0}'.format(pattern))
            myString = re.sub(pattern, ' ', myString)
            myString = ' '.join(myString.split())   # remove continous white space
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: String has none of these {0}'.format(pattern))

        myString = String.StripDiacritics(myString)
        myString = String.URLEncode(myString)

        # sort out double encoding: & html code %26 for example is encoded as %2526; on MAC OS '*' sometimes appear in the encoded string
        myString = myString.replace('%25', '%').replace('*', '')
        self.log('AGNT  :: Returned Search Query        : {0}'.format(myString))
        self.log(LOG_BIGLINE)

        return myString

    # -------------------------------------------------------------------------------------------------------------------------------
    def search(self, results, media, lang, manual):
        ''' Search For Media Entry '''
        ''' Search For Media Entry '''
        if not media.items[0].parts[0].file:
            return
        folder, filename = os.path.split(os.path.splitext(media.items[0].parts[0].file)[0])

        self.log(LOG_BIGLINE)
        self.log('SEARCH:: Version                      : v.%s', VERSION_NO)
        self.log('SEARCH:: Python                       : %s', sys.version_info)
        self.log('SEARCH:: Platform                     : %s %s', platform.system(), platform.release())
        self.log('SEARCH:: Preferences:')
        self.log('SEARCH::  > Cast Legend Before Summary: %s', PREFIXLEGEND)
        self.log('SEARCH::  > Collection Gathering')
        self.log('SEARCH::      > Cast                  : %s', COLCAST)
        self.log('SEARCH::      > Director(s)           : %s', COLDIRECTOR)
        self.log('SEARCH::      > Studio                : %s', COLSTUDIO)
        self.log('SEARCH::      > Film Title            : %s', COLTITLE)
        self.log('SEARCH::      > Genres                : %s', COLGENRE)
        self.log('SEARCH::  > Delay                     : %s', DELAY)
        self.log('SEARCH::  > Language Detection        : %s', DETECT)
        self.log('SEARCH::  > Library:Site Language     : %s:%s', lang, SITE_LANGUAGE)
        self.log('SEARCH:: Media Title                  : %s', media.title)
        self.log('SEARCH:: File Name                    : %s', filename)
        self.log('SEARCH:: File Folder                  : %s', folder)
        self.log(LOG_BIGLINE)

        # Check filename format
        try:
            FILMDICT = self.matchFilename(filename)
        except Exception as e:
            self.log('SEARCH:: Error: %s', e)
            return
        self.log(LOG_BIGLINE)

        # Search Query - for use to search the internet, remove all non alphabetic characters as GEVI site returns no results if apostrophes or commas exist etc..
        # if title is in a series the search string will be composed of the Film Title minus Series Name and No.
        searchTitle = self.CleanSearchString(FILMDICT['SearchTitle'])
        searchQuery = BASE_SEARCH_URL.format(searchTitle)

        morePages = True
        while morePages:
            self.log('SEARCH:: Search Query: %s', searchQuery)
            try:
                html = HTML.ElementFromURL(searchQuery, timeout=90, errors='ignore', sleep=DELAY)
            except Exception as e:
                self.log('SEARCH:: Error: Search Query did not pull any results: %s', e)
                break

            try:
                searchQuery = html.xpath('//a[@title="Next Page"]/@href')[0]
                searchQuery = (BASE_URL if BASE_URL not in searchQuery else '') + searchQuery
                pageNumber = int(searchQuery.split('&')[0].split('=')[1]) - 1
                morePages = True if pageNumber <= 10 else False
            except:
                pageNumber = 1
                morePages = False

            titleList = html.xpath('//div[@class="cell movie_box"]')
            self.log('SEARCH:: Result Page No: %s, Titles Found %s', pageNumber, len(titleList))

            self.log(LOG_BIGLINE)
            for title in titleList:
                # Site Title
                try:
                    siteTitle = title.xpath('./div/div/h3[@class="title"]/a/text()')[0].strip()
                    self.matchTitle(siteTitle, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Title URL
                try:
                    siteURL = title.xpath('./div/div/h3[@class="title"]/a/@href')[0].strip()
                    siteURL = ('' if BASE_URL in siteURL else BASE_URL) + siteURL
                    FILMDICT['SiteURL'] = siteURL
                    self.log('SEARCH:: Site Title url                %s', siteURL)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title Url: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Studio Name
                try:
                    siteStudio = title.xpath('./div/div/span/strong[text()="Studio:"]/following::a[contains(@title,"Studio name:")]/text()')[0].strip()
                    self.matchStudio(siteStudio, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Studio: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Release Date
                try:
                    siteReleaseDate = title.xpath('./div/div/div/span[@class="release_year"]/a/text()')[0].strip()
                    siteReleaseDate = siteReleaseDate.replace('sept ', 'sep ').replace('july ', 'jul ')
                    try:
                        siteReleaseDate = self.matchReleaseDate(siteReleaseDate, FILMDICT)
                        self.log(LOG_BIGLINE)
                    except Exception as e:
                        self.log('SEARCH:: Error getting Site URL Release Date: %s', e)
                        self.log(LOG_SUBLINE)
                        continue
                except:
                    self.log('SEARCH:: Error getting Site URL Release Date: Default to Filename Date')
                    self.log(LOG_BIGLINE)

                # we should have a match on studio, title and year now
                self.log('SEARCH:: Finished Search Routine')
                self.log(LOG_BIGLINE)
                results.Append(MetadataSearchResult(id=json.dumps(FILMDICT), name=FILMDICT['Title'], score=100, lang=lang))
                return

    # -------------------------------------------------------------------------------------------------------------------------------
    def update(self, metadata, media, lang, force=True):
        ''' Update Media Entry '''
        folder, filename = os.path.split(os.path.splitext(media.items[0].parts[0].file)[0])
        self.log(LOG_BIGLINE)
        self.log('UPDATE:: Version                      : v.%s', VERSION_NO)
        self.log('UPDATE:: File Name                    : %s', filename)
        self.log('UPDATE:: File Folder                  : %s', folder)
        self.log(LOG_BIGLINE)

        # Fetch HTML.
        FILMDICT = json.loads(metadata.id)
        self.log('UPDATE:: Film Dictionary Variables:')
        for key in sorted(FILMDICT.keys()):
            self.log('UPDATE:: {0: <29}: {1}'.format(key, FILMDICT[key]))
        self.log(LOG_BIGLINE)

        html = HTML.ElementFromURL(FILMDICT['SiteURL'], timeout=60, errors='ignore', sleep=DELAY)

        #  The following bits of metadata need to be established and used to update the movie on plex
        #    1.  Metadata that is set by Agent as default
        #        a. Studio               : From studio group of filename - no need to process this as above
        #        b. Title                : From title group of filename - no need to process this as is used to find it on website
        #        c. Tag line             : Corresponds to the url of movie
        #        d. Originally Available : set from metadata.id (search result)
        #        e. Content Rating       : Always X
        #        f. Content Rating Age   : Always 18
        #        g. Collection Info      : From title group of filename 

        # 1a.   Set Studio
        metadata.studio = FILMDICT['Studio']
        self.log('UPDATE:: Studio: %s' , metadata.studio)

        # 1b.   Set Title
        metadata.title = FILMDICT['Title']
        self.log('UPDATE:: Title: %s' , metadata.title)

        # 1c/d. Set Tagline/Originally Available from metadata.id
        metadata.tagline = FILMDICT['SiteURL']
        if 'CompareDate' in FILMDICT:
            metadata.originally_available_at = datetime.datetime.strptime(FILMDICT['CompareDate'], DATEFORMAT)
            metadata.year = metadata.originally_available_at.year
        self.log('UPDATE:: Tagline: %s', metadata.tagline)
        self.log('UPDATE:: Default Originally Available Date: %s', metadata.originally_available_at)

        # 1e/f. Set Content Rating to Adult/18 years
        metadata.content_rating = 'X'
        metadata.content_rating_age = 18
        self.log('UPDATE:: Content Rating - Content Rating Age: X - 18')

        # 1g. Collection
        if COLCLEAR:
            metadata.collections.clear()

        collections = FILMDICT['Collection']
        for collection in collections:
            metadata.collections.add(collection)
        self.log('UPDATE:: Collection Set From filename: %s', collections)

        #    2.  Metadata retrieved from website
        #        a. Categories           : Countries, Genres
        #        b. Collections
        #        c. Rating
        #        d. Directors            : List of Directors (alphabetic order)
        #        e. Cast                 : List of Actors and Photos (alphabetic order) - Photos sourced from IAFD
        #        f. Posters/Art
        #        g. Reviews
        #        h. Summary

        # 2a.  Process Categories: Countries, Genres
        self.log(LOG_BIGLINE)
        try:
            ignoreCategories = ['language', 'gay', 'movies', 'website', 'settings', 'locale', 'plot', 'character']
            countries = []
            genres = []
            htmlcategories = html.xpath('//a[contains(@href,"https://www.gayhotmovies.com/category/")]/span/text()')
            htmlcategories = [x.strip() for x in htmlcategories if x.strip()]
            htmlcategories.sort()
            self.log('UPDATE:: %s Categories Found: %s', len(htmlcategories), htmlcategories)
            for category in htmlcategories:
                if anyOf(x in category.lower() for x in ignoreCategories):
                    continue
                elif 'international' in category.lower():
                    countries.append(category.split('->')[-1])
                else:
                    category = category.replace('Bareback ->', 'Bareback ')
                    genres.append(category.split('->')[-1])
                    if 'compilation' in category.lower():
                        FILMDICT['Compilation'] = 'Compilation'

            self.log('UPDATE:: %s Countries Found: %s', len(countries), countries)
            metadata.countries.clear()
            for country in countries:
                metadata.countries.add(country)

            self.log('UPDATE:: %s Genres Found: %s', len(genres), genres)
            metadata.genres.clear()
            for genre in genres:
                metadata.genres.add(genre)
                # add genres to collection
                if COLGENRE:
                    metadata.collections.add(genre)

        except Exception as e:
            self.log('UPDATE:: Error getting Categories: Countries and Genres: %s', e)

        # 2b.   Collections
        self.log(LOG_BIGLINE)
        try:
            htmlcollections = html.xpath('//a[contains(@href,"https://www.gayhotmovies.com/series/")]/text()')
            htmlcollections = [x.strip() for x in htmlcollections if x.strip()]
            htmlcollections.sort()
            self.log('UPDATE:: %s Collections Found: %s', len(htmlcollections), htmlcollections)
            for collection in htmlcollections:
                if collection.lower() in map(str.lower, FILMDICT['Collection']):  # if set by filename its already in the list - FILMDICT['Collection'] contains a list
                    continue
                metadata.collections.add(collection)
                self.log('UPDATE:: Collection Added: %s', collection)

        except Exception as e:
            self.log('UPDATE:: Error getting Collections: %s', e)

        # 2c.   Rating = Thumbs Up / (Thumbs Up + Thumbs Down) * 10 - Rating is out of 10
        self.log(LOG_BIGLINE)
        try:
            thumbsUp = html.xpath('//span[@class="thumbs-up-count"]/text()')[0].strip()
            thumbsUp = (int(thumbsUp) if unicode(thumbsUp, 'utf-8').isnumeric() else 0) * 1.0
            thumbsDown = html.xpath('//span[@class="thumbs-down-count"]/text()')
            thumbsDown = (1 if not thumbsDown else int(thumbsDown[0].strip())) * 1.0  # default thumbs down to 1 to prevent 100% rating
            rating = thumbsUp / (thumbsUp + thumbsDown) * 10
            self.log('UPDATE:: Film Rating %s', rating)
            metadata.rating = rating

        except Exception as e:
            self.log('UPDATE:: Error getting Rating: %s', e)

        # 2d.   Directors
        self.log(LOG_BIGLINE)
        try:
            htmldirectors = html.xpath('//a[contains(@href,"https://www.gayhotmovies.com/director/")]/span/text()')
            directorDict = self.getIAFD_Director(htmldirectors, FILMDICT)
            metadata.directors.clear()
            for key in sorted(directorDict):
                newDirector = metadata.directors.new()
                newDirector.name = key
                newDirector.photo = directorDict[key]
                # add director to collection
                if COLDIRECTOR:
                    metadata.collections.add(key)

        except Exception as e:
            self.log('UPDATE:: Error getting Director(s): %s', e)

        # 2e.   Cast
        self.log(LOG_BIGLINE)
        try:
            htmlcast = html.xpath('//div[@class="name"]/a/text()[normalize-space()]')
            castdict = self.ProcessIAFD(htmlcast, FILMDICT)

            # sort the dictionary and add key(Name)- value(Photo, Role) to metadata
            metadata.roles.clear()
            for key in sorted(castdict):
                newRole = metadata.roles.new()
                newRole.name = key
                newRole.photo = castdict[key]['Photo']
                newRole.role = castdict[key]['Role']
                # add cast name to collection
                if COLCAST:
                    metadata.collections.add(key)

        except Exception as e:
            self.log('UPDATE:: Error getting Cast: %s', e)

        # 2f.   Poster / Art
        self.log(LOG_BIGLINE)
        try:
            image = html.xpath('//div[@class="lg_inside_wrap"]/@data-front')[0]
            self.log('UPDATE:: Poster Image Found: %s', image)
            #  set poster then only keep it
            metadata.posters[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
            metadata.posters.validate_keys([image])

            if BACKGROUND:
                image = html.xpath('//div[@class="lg_inside_wrap"]/@data-back')[0]
                self.log('UPDATE:: Art Image Found: %s', image)
                #  set Art then only keep it
                metadata.art[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
                metadata.art.validate_keys([image])

        except Exception as e:
            self.log('UPDATE:: Error getting Poster/Art: %s', e)
            try:
                # sometimes no back cover exists... on some old movies/ so use cover photo for both poster/art
                image = html.xpath('//img[@id="cover" and @class="cover"]/@src')[0]
                self.log('UPDATE:: Old Style Cover Image Found: %s', image)
                #  set poster then only keep it
                metadata.posters[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
                metadata.posters.validate_keys([image])

                #  set Art then only keep it
                metadata.art[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
                metadata.art.validate_keys([image])
            except Exception as e:
                self.log('UPDATE:: Error getting Old Style Poster/Art: %s', e)

        # 2g.   Reviews
        self.log(LOG_BIGLINE)
        reviewCount = 4
        try:
            htmlreviews = html.xpath('//div[@class="review"]')
            htmlreviews = htmlreviews[:reviewCount] if len(htmlreviews) >= reviewCount else htmlreviews         # take one less user comment if editor comment is present
            self.log('UPDATE:: Number of Reviews [%s]', len(htmlreviews))
            metadata.reviews.clear()
            for count, review in enumerate(htmlreviews, start=1):
                self.log('UPDATE:: Review No %s', count)
                try:
                    try:
                        writer =  review.xpath('./span[@class="handle_text"]/text()[normalize-space()]')[0]
                        self.log('UPDATE:: Review Writer: %s', writer)
                    except:
                        writer = ''
                    try:
                        writing = review.xpath('./div[@class="review_content"]/span/text()[normalize-space()]')
                        writing = ''.join(writing)
                        self.log('UPDATE:: Review Text: %s', writing)
                    except:
                        writing = ''

                    newReview = metadata.reviews.new()
                    newReview.author = writer
                    newReview.link  = FILMDICT['SiteURL']
                    newReview.source = FILMDICT['Title'] + '...'
                    if len(writing) > 275:
                        for i in range(275, -1, -1):
                            if writing[i] in ['.', '!', '?']:
                                writing = writing[0:i + 1]
                                break
                    newReview.text = writing
                    self.log(LOG_SUBLINE)
                except Exception as e:
                    self.log('UPDATE:: Error getting Review No. %s: %s', count, e)
        except Exception as e:
            self.log('UPDATE:: Error getting Reviews: %s', e)

        # 2h.   Summary = IAFD Legend + Synopsis + Scene Breakdown + Chapter
        self.log(LOG_BIGLINE)
        isChapters = False
        # synopsis
        try:
            synopsis = html.xpath('//span[contains(@class,"video_description")]//text()')
            self.log('UPDATE:: Synopsis Found: %s', synopsis)
            synopsis = ' '.join(synopsis).replace('\n', ' ')
            synopsis = re.sub('<[^<]+?>', '', synopsis).strip()

            regex = r'The movie you are enjoying was created by consenting adults.*'
            pattern = re.compile(regex, re.DOTALL | re.IGNORECASE)
            synopsis = re.sub(pattern, '', synopsis)

        except Exception as e:
            self.log('UPDATE:: Error getting Synopsis: %s', e)
        
        # duration
        try:
            htmlDuration = html.xpath('//span[@datetime]/text()')[0].strip()
            self.log('UPDATE:: Extracted html duration : %s', htmlDuration)
            siteDuration = self.durationSeconds(htmlDuration)*1000
            fileDuration = int(long(getattr(media.items[0].parts[0], 'duration')))
            self.log('UPDATE:: Running time from site: %s', siteDuration)
            self.log('UPDATE:: Running time from file: %s', fileDuration)
            durationDelta = fileDuration - siteDuration
            self.log('UPDATE:: Duration delta: %s', durationDelta)
            if abs(durationDelta) < DURATION_DETLA_THRESHOLD:
                isChapters = True
        except Exception as e:
            self.log('UPDATE:: Error getting duration: %s', e)

        if isChapters:
            metadata.chapters.clear()
            offset = 0
            totalSceneDuration = 0
            newChapters=[]

        # Scene Breakdown
        self.log(LOG_SUBLINE)
        try:
            allscenes = ''
            allacts = []
            htmlheadings = html.xpath('//span[@class="right time"]/text()')
            htmlscenes = html.xpath('//div[@class="scene_details_sm"]')
            self.log('UPDATE:: %s Scenes Found: %s', len(htmlscenes), htmlscenes)
            for (heading, htmlscene) in zip(htmlheadings, htmlscenes):
                settingsList = htmlscene.xpath('./strong[.="Setting"]/following-sibling::*//.//text()[count(.|./strong[.="Theme"]/preceding-sibling::*//.//text()) = count(//strong[.="Theme"]/preceding-sibling::*//.//text())]')
                if settingsList:
                    self.log('UPDATE:: %s Setting Found: %s', len(settingsList), settingsList)
                    settings = ', '.join(settingsList)
                    scene = ('\n[ {0} ] . . . . Setting: {1}').format(heading.strip(), settings)
                else:
                    scene = '\n[ {0} ]'.format(heading.strip())
                starsList = htmlscene.xpath('./div[@class="scene_stars_detail"]/span[@class="scene_stars"]/a[contains(@href,"porn-star")]/text()')
                if starsList:
                    self.log('UPDATE:: %s Stars Found: %s', len(starsList), starsList)
                    for i, star in enumerate(starsList):
                        starsList[i] = star.split('(')[0]
                    stars = ', '.join(starsList)
                    scene += '. . . . Stars: {0}'.format(stars)

                actsList = htmlscene.xpath('./div[@class="attributes"]/span[@class="list_attributes"]/a[contains(@href,"scene_attribute")]/text()')
                if actsList:
                    if ACT_AS_GENRE:
                        for act in actsList:
                            if act not in allacts:
                                allacts.append(act)
                                metadata.genres.add(act)
                    self.log('UPDATE:: %s Sex Acts Found: %s', len(actsList), actsList)
                    acts = ', '.join(actsList)
                    scene += '\nSex Acts: {0}'.format(acts)
                allscenes += scene

                if isChapters:
                    sceneTitle = heading.split('-')[0].strip() + ' - ' + stars + ' (' + acts + ')'
                    sceneDurationStr = heading.split('-')[1].replace('min', ':').replace('sec','').replace('s','').replace(' ', '')
                    self.log('UPDATE:: Scene Duration: %s', sceneDurationStr)
                    sceneDuration = self.durationSeconds(sceneDurationStr) * 1000
                    totalSceneDuration += sceneDuration
                    chapter = {}
                    chapter['title'] = sceneTitle
                    chapter['start_time_offset'] = offset
                    offset = offset + sceneDuration
                    chapter['end_time_offset'] = offset
                    newChapters.append(chapter)
                    self.log('UPDATE:: Chapter - Duration: %s - Title: %s', sceneDuration, sceneTitle)

        except Exception as e:
            allscenes = ''
            self.log('UPDATE:: Error getting Scene Breakdown: %s', e)
        
        # adding chapters
        if isChapters and len(newChapters)>0:
            chapterDelta = fileDuration - totalSceneDuration
            # Note : we assume that potential delta is due to disclamers and intro at the beginning of the movie
            for newChapter in newChapters:
                chapter = metadata.chapters.new()
                chapter.title = newChapter['title']
                chapter.start_time_offset = newChapter['start_time_offset'] + chapterDelta
                chapter.end_time_offset = newChapter['end_time_offset'] + chapterDelta

        # combine and update
        self.log(LOG_SUBLINE)
        castLegend = IAFD_LEGEND.format(IAFD_ABSENT, IAFD_FOUND, IAFD_THUMBSUP if FILMDICT['FoundOnIAFD'] == "Yes" else IAFD_THUMBSDOWN)
        summary = ('{0}\n{1}\n{2}' if PREFIXLEGEND else '{1}\n{2}\n{0}').format(castLegend, synopsis.strip(), allscenes.strip())
        summary = summary.replace('\n\n', '\n')
        metadata.summary = self.TranslateString(summary, lang)

        self.log(LOG_BIGLINE)
        self.log('UPDATE:: Finished Update Routine')
        self.log(LOG_BIGLINE)
