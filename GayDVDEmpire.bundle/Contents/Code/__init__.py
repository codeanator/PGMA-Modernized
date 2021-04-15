#!/usr/bin/env python
# pylint: disable=line-too-long
# pylint: disable=W0702, W0703, C0103, C0410
# encoding=utf8
'''
# GayDVDEmpire (IAFD)
                                    Version History
                                    ---------------
    Date            Version             Modification
    13 Apr 2020   2019.08.12.03    Corrected scrapping of collections
    14 Apr 2020   2019.08.12.04    sped up search routine, corrected tagline
                                   search multiple result pages
    01 Jun 2020   2019.08.12.05    Implemented translation of summary
                                   improved getIAFDActor search
    27 Jun 2020   2019.08.12.06    Improvement to Summary Translation: Translate into Plex Library Language
                                   stripping of internet domain suffixes from studio names when matching
                                   handling of unicode characters in film titles and comparision string normalisation
    30 Aug 2020   2019.08.12.07    Handling of Roman Numerals in Titles to Match Arabic Numerals
                                   Errors in getting production year and release dates corrected
    22 Sep 2020   2019.08.12.08    Correction to regex string to handle titles in Sort Order trailing determinates
    07 Oct 2020   2019.08.12.09    IAFD - change to https
    19 Jan 2021   2019.08.12.10    Improved on IAFD search, actors sexual roles if recorded are returned, if not shows a red circle.
                                   corrections to xpath extra )... failing to get genres, cast and directors
    19 Feb 2021   2019.08.12.12    Moved IAFD and general functions to other py files
                                   Enhancements to IAFD search routine, including LevenShtein Matching on Cast names
                                   set content_rating age to 18
                                   Set collections from filename + countries, cast and directors
                                   Added directors photos
                                   included studio on iafd processing of filename
                                   Added iafd legend to summary
                                   improved logging
    11 Mar 2021   2019.08.12.13    Cast xpath was picking Bios and Interview along with cast name - corrected
---------------------------------------------------------------------------------------------------------------
'''
import datetime, platform, os, re, sys, json
from unidecode import unidecode
from googletrans import Translator

# Version / Log Title
VERSION_NO = '2019.08.12.13'
PLUGIN_LOG_TITLE = 'GayDVDEmpire'
LOG_BIGLINE = '------------------------------------------------------------------------------'
LOG_SUBLINE = '      ------------------------------------------------------------------------'

# Preferences
REGEX = Prefs['regex']                      # file matching pattern
YEAR = Prefs['year']                        # is year mandatory in filename
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
BACKGROUND = Prefs['background']            # backround

# IAFD Related variables
IAFD_BASE = 'https://www.iafd.com'
IAFD_SEARCH_URL = IAFD_BASE + '/results.asp?searchtype=comprehensive&searchstring={0}'

IAFD_ABSENT = u'\U0000274C'        # red cross mark - not on IAFD
IAFD_FOUND = u'\U00002705'         # heavy white tick on green - on IAFD
IAFD_THUMBSUP = u'\U0001F44D'      # thumbs up unicode character
IAFD_THUMBSDOWN = u'\U0001F44E'    # thumbs down unicode character
IAFD_LEGEND = u'CAST LEGEND\u2003{0} Actor not on IAFD\u2003{1} Actor on IAFD\u2003:: {2} Film on IAFD ::\n'

# URLS
BASE_URL = 'http://www.gaydvdempire.com'
BASE_SEARCH_URL = BASE_URL + '/AllSearch/Search?view=list&exactMatch={0}&q={0}'

# dictionary holding film variables
FILMDICT = {}

# Date Formats used by website
DATEFORMAT = '%m/%d/%Y'

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
class GayDVDEmpire(Agent.Movies):
    ''' define Agent class '''
    name = 'GayDVDEmpire (IAFD)'
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

        myString = myString.lower().strip()
        myString = myString.replace(' -', ':').replace(ur'\u2013', '-').replace(ur'\u2014', '-')

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
                searchQuery = html.xpath('.//a[@title="Next"]/@href')[0]
                pageNumber = int(searchQuery.split('page=')[1]) # next page number
                searchQuery = BASE_SEARCH_URL.format(searchTitle) + '&page={0}'.format(pageNumber)
                pageNumber = pageNumber - 1
                self.log('SEARCH:: Search Query: %s', searchQuery)
                morePages = True if pageNumber <= 10 else False
            except:
                pageNumber = 1
                morePages = False

            titleList = html.xpath('.//div[contains(@class,"row list-view-item")]')
            self.log('SEARCH:: Result Page No: %s, Titles Found %s', pageNumber, len(titleList))
            self.log(LOG_BIGLINE)
            for title in titleList:
                # siteTitle = The text in the 'title' - Gay DVDEmpire - displays its titles in SORT order
                try:
                    siteTitle = title.xpath('./div/h3/a[@category and @label="Title"]/@title')[0]
                    # convert sort order version to normal version i.e "Best of Zak Spears, The -> The Best of Zak Spears"
                    pattern = u', (The|An|A)$'
                    matched = re.search(pattern, siteTitle, re.IGNORECASE)  # match against string
                    if matched:
                        determinate = matched.group().replace(', ', '')
                        self.log('SEARCH:: Found Determinate:           %s', determinate)
                        siteTitle = re.sub(pattern, '', siteTitle)
                        siteTitle = '{0} {1}'.format(determinate, siteTitle)
                        self.log('SEARCH:: Re-ordered Site Title:       %s', siteTitle)

                    self.matchTitle(siteTitle, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Title URL
                try:
                    siteURL = title.xpath('./div/h3/a[@label="Title"]/@href')[0]
                    siteURL = ('' if BASE_URL in siteURL else BASE_URL) + siteURL
                    FILMDICT['SiteURL'] = siteURL
                    self.log('SEARCH:: Site Title url                %s', siteURL)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title Url: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Studio Name
                try:
                    siteStudio = title.xpath('./div/ul/li/a/small[text()="studio"]/following-sibling::text()')[0].strip()
                    self.matchStudio(siteStudio, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Studio: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Production Year found in brackets - if fails try Release Date 
                try:
                    siteProductionYear = title.xpath('.//small[contains(., "(")]/text()')[0].replace('(', '').replace(')', '').strip()
                    try:
                        siteReleaseDate = self.matchReleaseDate(siteProductionYear, FILMDICT)
                        self.log(LOG_BIGLINE)
                    except Exception as e:
                        self.log('SEARCH:: Error getting Site URL Release Date: %s', e)
                        self.log(LOG_SUBLINE)
                        continue
                except:
                    # failed to scrape production year - so try release date
                    try:
                        siteReleaseDate = title.xpath('.//small[text()="released"]/following-sibling::text()')[0].strip()
                        try:
                            siteReleaseDate = self.matchReleaseDate(siteReleaseDate, FILMDICT)
                            self.log(LOG_BIGLINE)
                        except Exception as e:
                            self.log('SEARCH:: Error getting Site URL Release Date: %s', e)
                            self.log(LOG_SUBLINE)
                            continue
                    except:
                        # failed to scrape release date to
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
        #        a. Genres
        #        b. Collections
        #        c. Directors            : List of Drectors (alphabetic order)
        #        d. Cast                 : List of Actors and Photos (alphabetic order) - Photos sourced from IAFD
        #        e. Posters/Background
        #        f. Summary

        # 2a.   Genres
        self.log(LOG_BIGLINE)
        try:
            ignoreGenres = ['Sale', '4K Ultra HD']
            genres = []
            htmlgenres = html.xpath('//ul[@class="list-unstyled m-b-2"]//a[@label="Category"]/text()[normalize-space()]')
            htmlgenres = [x.strip() for x in htmlgenres if x.strip()]
            htmlgenres.sort()
            self.log('UPDATE:: %s Genres Found: %s', len(htmlgenres), htmlgenres)
            for genre in htmlgenres:
                if anyOf(x in genre.lower() for x in ignoreGenres):
                    continue
                genres.append(genre)
                if 'compilation' in genre.lower():
                    FILMDICT['Compilation'] = 'Compilation'

            metadata.genres.clear()
            for genre in genres:
                metadata.genres.add(genre)
                if COLGENRE:
                    metadata.collections.add(genre)

        except Exception as e:
            self.log('UPDATE:: Error getting Genres: %s', e)

        # 2b.   Collections
        self.log(LOG_BIGLINE)
        try:
            htmlcollections = html.xpath('//a[contains(@label, "Series")]/text()[normalize-space()]')
            htmlcollections = [x.strip() for x in htmlcollections if x.strip()]
            htmlcollections = [x.replace('"', '').replace('Series', '').strip() for x in htmlcollections]
            self.log('UPDATE:: %s Collections Found: %s', len(htmlcollections), htmlcollections)
            for collection in htmlcollections:
                if collection.lower() in map(str.lower, FILMDICT['Collection']):  # if set by filename its already in the list - FILMDICT['Collection'] contains a list
                    continue
                metadata.collections.add(collection)
                self.log('UPDATE:: Collection Added: %s', collection)

        except Exception as e:
            self.log('UPDATE:: Error getting Collections: %s', e)

        # 2c.   Directors
        self.log(LOG_BIGLINE)
        try:
            htmldirectors = html.xpath('//a[contains(@label, "Director - details")]/text()[normalize-space()]')
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
            self.log('UPDATE:: Error getting Directors: %s', e)

        # 2d.   Cast
        self.log(LOG_BIGLINE)
        try:
            htmlcast = html.xpath('//a[@class="PerformerName" and @label="Performers - detail"]/text()')
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

        # 2e.   Poster/Art
        self.log(LOG_BIGLINE)
        try:
            htmlimage = html.xpath('//*[@id="front-cover"]/img')[0]
            image = htmlimage.get('src')
            self.log('UPDATE:: Poster Image Found: %s', image)
            #  set poster then only keep it
            metadata.posters[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
            metadata.posters.validate_keys([image])

            if BACKGROUND:
                image = image.replace('h.jpg', 'bh.jpg')
                self.log('UPDATE:: Art Image Found: %s', image)
                #  set poster then only keep it
                metadata.art[image] = Proxy.Media(HTTP.Request(image).content, sort_order=1)
                metadata.art.validate_keys([image])

        except Exception as e:
            self.log('UPDATE:: Error getting Poster/Art: %s', e)

        # 2f. Chapters
        isChapters = False

        try:
            htmlduration = html.xpath('//small[text()="Length: "]/following-sibling::text()')[0].strip()
            self.log('UPDATE:: HTML duration: %s', htmlduration)
            htmlduration = htmlduration.replace('hrs.', ':').replace('mins.','').replace(' ', '') + ':00'
            siteDuration = self.durationSeconds(htmlduration)*1000
            fileDuration = 0
            for part in media.items[0].parts:
                fileDuration += int(long(getattr(part, 'duration')))
            self.log('UPDATE:: Running time from site: %s', siteDuration)
            self.log('UPDATE:: Running time from file: %s', fileDuration)
            durationDelta = fileDuration - siteDuration
            self.log('UPDATE:: Duration delta: %s', durationDelta)
            if abs(durationDelta) < DURATION_DETLA_THRESHOLD:
                isChapters = True
        except Exception as e:
            self.log('UPDATE:: Error getting duration: %s', e)
        
        # Scene Breakdown
        self.log(LOG_SUBLINE)
        if isChapters:
            metadata.chapters.clear()
            offset = 0
            totalSceneDuration = 0
            newChapters=[]
            try:
                htmlscenes = html.xpath('//a[@label="Scene Title"]//ancestor::div[@class="row"]')
                self.log('UPDATE:: %s Scenes Found: %s', len(htmlscenes), htmlscenes)
                for htmlscene in htmlscenes:
                    self.log('UPDATE:: Scene: %s', htmlscene.text_content())
                    sceneTitle = htmlscene.xpath('//a[@label="Scene Title"]/text()')[0].strip()
                    sceneDurationStr = htmlscene.xpath('//span[@class="badge"]/text()')[0]
                    sceneDurationStr = sceneDurationStr.replace('min', ':').replace(' ', '') + '00'
                    self.log('UPDATE:: Scene Duration: %s', sceneDurationStr)
                    sceneDuration = self.durationSeconds(sceneDurationStr) * 1000
                    totalSceneDuration += sceneDuration
                    chapter = {}
                    chapter['title'] = sceneTitle
                    chapter['start_time_offset'] = offset
                    offset = offset + sceneDuration
                    chapter['end_time_offset'] = offset
                    newChapters.append(chapter)

            except Exception as e:
                allscenes = ''
                self.log('UPDATE:: Error getting Scene Breakdown: %s', e)
        
        # adding chapters
        if isChapters and len(newChapters)>0:
            chapterDelta = fileDuration - totalSceneDuration
            # Note : we assume that potential delta is due to disclamers and intro at the beginning of the movie
            if chapterDelta >= 0:
                for newChapter in newChapters:
                    chapter = metadata.chapters.new()
                    self.log('UPDATE:: Adding chapter - Title: %s - Beginning: %s', newChapter['title'], newChapter['start_time_offset'] + chapterDelta)
                    chapter.title = newChapter['title']
                    chapter.start_time_offset = newChapter['start_time_offset'] + chapterDelta
                    chapter.end_time_offset = newChapter['end_time_offset'] + chapterDelta

        # 2g.   Summary = IAFD Legend + Synopsis
        self.log(LOG_BIGLINE)
        # synopsis
        try:
            synopsis = html.xpath('//div[@class="col-xs-12 text-center p-y-2 bg-lightgrey"]/div/p')[0].text_content().strip()
            synopsis = re.sub('<[^<]+?>', '', synopsis)
            self.log('UPDATE:: Synopsis Found: %s', synopsis)
        except Exception as e:
            synopsis = ''
            self.log('UPDATE:: Error getting Synopsis: %s', e)

        # combine and update
        self.log(LOG_SUBLINE)
        castLegend = IAFD_LEGEND.format(IAFD_ABSENT, IAFD_FOUND, IAFD_THUMBSUP if FILMDICT['FoundOnIAFD'] == "Yes" else IAFD_THUMBSDOWN)
        summary = ('{0}\n{1}' if PREFIXLEGEND else '{1}\n{0}').format(castLegend, synopsis.strip())
        summary = summary.replace('\n\n', '\n')
        metadata.summary = self.TranslateString(summary, lang)

        self.log(LOG_BIGLINE)
        self.log('UPDATE:: Finished Update Routine')
        self.log(LOG_BIGLINE)