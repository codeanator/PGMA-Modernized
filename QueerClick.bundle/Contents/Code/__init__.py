#!/usr/bin/env python
# pylint: disable=line-too-long
# pylint: disable=W0702, W0703, C0103, C0410
# encoding=utf8
'''
# QueerClick - (IAFD)
                                    Version History
                                    ---------------
    Date            Version             Modification
    28 Apr 2020  2020.02.14.10     Removed disable debug logging preference
                                   corrected logic around image cropping
                                   improved error handling on title, url retrieval
    29 Apr 2020   2020.02.14.11    update IAFD routine
    01 Jun 2020   2020.02.14.12    Implemented translation of summary
                                   improved getIAFDActor search
    25 Jun 2020   2020.02.14.13    Improvement to Summary Translation: Translate into Plex Library Language
                                   stripping of intenet domain suffixes from studio names when matching
                                   handling of unicode characters in film titles and comparision string normalisation
    25 Jul 2020   2020.02.14.14    changed replacement of hyphens etc to null with hyphens to space when building 
                                   the search string, added chars u\2011 (nonbreaking hyphen) and u\2012 (figure dash)
    25 Jul 2020   2020.02.14.15    Change to regex matching code - site titles which had studio name in them were failing to match to 
                                   file titles as regex was different between the two
    07 Oct 2020   2020.02.14.16    IAFD - change to https
    28 Feb 2021   2020.02.14.20    Moved IAFD and general functions to other py files
                                   Enhancements to IAFD search routine, including Levenshtein Matching on Cast names
                                   Added iafd legend to summary

-----------------------------------------------------------------------------------------------------------------------------------
'''
import datetime, platform, os, re, sys, subprocess, json
from unidecode import unidecode
from googletrans import Translator
from PIL import Image
from io import BytesIO

# Version / Log Title
VERSION_NO = '2020.02.14.20'
PLUGIN_LOG_TITLE = 'QueerClick'
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
BACKGROUND = Prefs['background']            # background

# IAFD Related variables
IAFD_BASE = 'https://www.iafd.com'
IAFD_SEARCH_URL = IAFD_BASE + '/results.asp?searchtype=comprehensive&searchstring={0}'

IAFD_ABSENT = u'\U0000274C'        # red cross mark - not on IAFD
IAFD_FOUND = u'\U00002705'         # heavy white tick on green - on IAFD
IAFD_THUMBSUP = u'\U0001F44D'      # thumbs up unicode character
IAFD_THUMBSDOWN = u'\U0001F44E'    # thumbs down unicode character
IAFD_LEGEND = u'CAST LEGEND\u2003{0} Actor not on IAFD\u2003{1} Actor on IAFD\u2003:: {2} Film on IAFD ::'

# PLEX API /CROP Script/online image cropper
load_file = Core.storage.load
CROPPER = r'CScript.exe "{0}/Plex Media Server/Plug-ins/BestExclusivePorn.bundle/Contents/Code/ImageCropper.vbs" "{1}" "{2}" "{3}" "{4}"'
THUMBOR = Prefs['thumbor'] + "/0x0:{0}x{1}/{2}"

# URLS
BASE_URL = 'https://www.queerclick.com'
BASE_SEARCH_URL = BASE_URL + '/?s={0}'

# dictionary holding film variables
FILMDICT = {}   

# Date Formats used by website
DATEFORMAT = '%d %b %y'

# Website Language
SITE_LANGUAGE = 'en'

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
class QueerClick(Agent.Movies):
    ''' define Agent class '''
    name = 'QueerClick (IAFD)'
    languages = [Locale.Language.English]
    primary_provider = False
    preference = True
    media_types = ['Movie']
    contributes_to = ['com.plexapp.agents.GayAdult', 'com.plexapp.agents.GayAdultScenes']

    # import IAFD Functions
    from iafd import *

    # import General Functions
    from genfunctions import *

    # -------------------------------------------------------------------------------------------------------------------------------
    def CleanSearchString(self, myString):
        ''' Prepare Title for search query '''
        self.log('AGNT  :: Original Search Query        : {0}'.format(myString))
        myString = myString.lower().strip()

        # replace curly apostrophes with straight as strip diacritics will remove these
        quoteChars = [ur'\u2018', ur'\u2019']
        pattern = u'({0})'.format('|'.join(quoteChars))
        matched = re.search(pattern, myString)  # match against whole string
        if matched:
            self.log('AGNT  :: Search Query:: Replacing characters in string. Found one of these {0}'.format(pattern))
            myString = re.sub(pattern, "'", myString)
            myString = ' '.join(myString.split())   # remove continous white space
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: String has none of these {0}'.format(pattern))

        spaceChars = [',', '-', ur'\u2011', ur'\u2012', ur'\u2013', ur'\u2014'] # for titles with commas, colons in them on disk represented as ' - '
        pattern = u'({0})'.format('|'.join(spaceChars))
        matched = re.search(pattern, myString)  # match against whole string
        if matched:
            self.log('AGNT  :: Search Query:: Replacing characters in string. Found one of these {0}'.format(pattern))
            myString = re.sub(pattern, ' ', myString)
            myString = ' '.join(myString.split())   # remove continous white space
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: String has none of these {0}'.format(pattern))

        # QueerClick seems to fail to find Titles which have invalid chars in them split at first incident and take first split, just to search but not compare
        # the back tick is added to the list as users who can not include quotes in their filenames can use these to replace them without changing the scrappers code
        badChars = ["'", '"', '`', ur'\u201c', ur'\u201d', ur'\u2018', ur'\u2019']
        pattern = u'({0})'.format('|'.join(badChars))

        # check that title section of string does not start with a bad character, if it does remove studio from search string
        matched = re.search(pattern, myString[0])  # match against first character
        if matched:
            self.log('AGNT  :: Search Query:: Dropping first character [{0}]. Found one of these {1}'.format(myString[0], pattern))
            myString = myString[1:]
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: First character has none of these {0}'.format(pattern))

        matched = re.search(pattern, myString)  # match against whole string
        if matched:
            badPos = matched.start()
            self.log('AGNT  :: Search Query:: Splitting at position [{0}]. Found one of these {1}'.format(badPos, pattern))
            myString = myString[:badPos]
            self.log('AGNT  :: Amended Search Query [{0}]'.format(myString))
        else:
            self.log('AGNT  :: Search Query:: Split not attempted. String has none of these {0}'.format(pattern))

        myString = String.StripDiacritics(myString)
        myString = String.URLEncode(myString.strip())

        # sort out double encoding: & html code %26 for example is encoded as %2526; on MAC OS '*' sometimes appear in the encoded string
        myString = myString.replace('%25', '%').replace('*', '')

        # string can not be longer than 50 characters
        myString = myString[:50].strip()
        myString = myString if myString[-1] != '%' else myString[:49]
        self.log('AGNT  :: Returned Search Query        : {0}'.format(myString))
        self.log(LOG_BIGLINE)

        return myString

    # -------------------------------------------------------------------------------------------------------------------------------
    def getFilmImages(self, imageType, imageURL, whRatio):
        ''' get Film images - posters/background art and crop if necessary '''
        pic = imageURL
        picContent = ''
        picInfo = Image.open(BytesIO(HTTP.Request(pic).content))
        width, height = picInfo.size
        dispWidth = '{:,d}'.format(width)       # thousands separator
        dispHeight = '{:,d}'.format(height)     # thousands separator

        self.log('AGNT  :: {0} Found: Width ({1}) x Height ({2}); URL: {3}'.format(imageType, dispWidth, dispHeight, imageURL))

        maxHeight = float(width * whRatio)      # Maximum allowable height

        cropHeight = float(maxHeight if maxHeight <= height else height)
        cropWidth = float(cropHeight / whRatio)

        DxHeight = 0.0 if cropHeight == height else (abs(cropHeight - height) / height) * 100.0
        DxWidth = 0.0 if cropWidth == width else (abs(cropWidth - width) / width) * 100.0

        cropRequired = True if DxWidth >= 10 or DxHeight >=10 else False
        cropWidth = int(cropWidth)
        cropHeight = int(cropHeight)
        desiredWidth = '{0:,d}'.format(cropWidth)     # thousands separator
        desiredHeight = '{0:,d}'.format(cropHeight)   # thousands separator
        DxWidth = '{0:.2f}'.format(DxWidth)    # percent format
        DxHeight = '{0:.2f}'.format(DxHeight)  # percent format
        self.log('AGNT  :: Crop {0} {1}: Actual (w{2} x h{3}), Desired (w{4} x h{5}), % Dx = w[{6}%] x h[{7}%]'.format("Required:" if cropRequired else "Not Required:", imageType, dispWidth, dispHeight, desiredWidth, desiredHeight, DxWidth, DxHeight))
        if cropRequired:
            try:
                self.log('AGNT  :: Using Thumbor to crop image to: {0} x {1}'.format(desiredWidth, desiredHeight))
                pic = THUMBOR.format(cropWidth, cropHeight, imageURL)
                picContent = HTTP.Request(pic).content
            except Exception as e:
                self.log('AGNT  :: Error Thumbor Failed to Crop Image to: {0} x {1}: {2} - {3}'.format(desiredWidth, desiredHeight, pic, e))
                try:
                    if os.name == 'nt':
                        self.log('AGNT  :: Using Script to crop image to: {0} x {1}'.format(desiredWidth, desiredHeight))
                        envVar = os.environ
                        TempFolder = envVar['TEMP']
                        LocalAppDataFolder = envVar['LOCALAPPDATA']
                        pic = os.path.join(TempFolder, imageURL.split("/")[-1])
                        cmd = CROPPER.format(LocalAppDataFolder, imageURL, pic, cropWidth, cropHeight)
                        subprocess.call(cmd)
                        picContent = load_file(pic)
                except Exception as e:
                    self.log('AGNT  :: Error Script Failed to Crop Image to: {0} x {1}'.format(desiredWidth, desiredHeight))
        else:
            picContent = HTTP.Request(pic).content

        return pic, picContent

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

        # strip studio name from title to use in comparison
        self.log('SEARCH:: Search Title: %s', searchTitle)
        regex = ur'^{0} |at {0}$'.format(re.escape(FILMDICT['CompareStudio']))
        pattern = re.compile(regex, re.IGNORECASE)
        compareTitle = re.sub(pattern, '', searchTitle)
        compareTitle = self.NormaliseComparisonString(compareTitle)

        morePages = True
        while morePages:
            self.log('SEARCH:: Search Query: %s', searchQuery)
            try:
                html = HTML.ElementFromURL(searchQuery, timeout=20, sleep=DELAY)
            except Exception as e:
                self.log('SEARCH:: Error: Search Query did not pull any results: %s', e)
                return

            try:
                searchQuery = html.xpath('//div[@class="pagination post"]/span[@class="right"]/a/@href')[0]
                self.log('SEARCH:: Next Page Search Query: %s', searchQuery)
                pageNumber = int(searchQuery.split('?')[0].split('page/')[1]) - 1
                morePages = True if pageNumber <= 10 else False
            except:
                searchQuery = ''
                self.log('SEARCH:: No More Pages Found')
                pageNumber = 1
                morePages = False

            titleList = html.xpath('.//article[@id and @class]')
            self.log('SEARCH:: Result Page No: %s, Titles Found %s', pageNumber, len(titleList))
            self.log(LOG_BIGLINE)

            for title in titleList:
                # Site Entry
                try:
                    siteEntry = title.xpath('./h2[@class="entry-title"]/a/text()')[0]
                    self.log('SEARCH:: Site Entry: %s', siteEntry)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Entry: %s', e)
                    continue

                # the siteEntry usual has the format Studio: Title
                if ':' in siteEntry:
                    siteStudio, siteTitle = siteEntry.split(': ', 1)
                else: # on very old entries it was Title [at|on] Studio
                    siteEntry = siteEntry.split()
                    if siteEntry[-2].lower() == 'at' or siteEntry[-2].lower() == 'on':
                        siteStudio = [-1]
                        siteTitle = ''.join(siteEntry[0:-2])
                    else:
                        self.log('SEARCH:: Error determining Site Studio and Title from Site Entry')
                        continue

                # Site Title
                try:
                    self.matchTitle(siteTitle, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Studio Name
                try:
                    self.matchStudio(siteStudio, FILMDICT)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Studio: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Title URL
                try:
                    siteURL = title.xpath('./h2[@class="entry-title"]/a/@href')[0]
                    siteURL = ('' if BASE_URL in siteURL else BASE_URL) + siteURL
                    FILMDICT['SiteURL'] = siteURL
                    self.log('SEARCH:: Site Title url                %s', siteURL)
                    self.log(LOG_BIGLINE)
                except Exception as e:
                    self.log('SEARCH:: Error getting Site Title Url: %s', e)
                    self.log(LOG_SUBLINE)
                    continue

                # Site Release Date
                try:
                    siteReleaseDate = title.xpath('./div[@class="postdetails"]/span[@class="date updated"]/text()[normalize-space()]')[0]
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
        #        a.   Cast                 : List of Actors and Photos (alphabetic order) - Photos sourced from IAFD
        #        b.   Posters/Art
        #        c.   Summary

        # 2a    Cast
        #       QueerClick stores the cast as links in the article
        self.log(LOG_BIGLINE)
        try:
            htmlcast = html.xpath('//div[@class="taxonomy"]/a/@title|//article[@id and @class]/p/a/text()[normalize-space()]')

            # standardise apostrophe's then remove duplicates
            htmlcast = [x.replace("’", "'") for x in htmlcast]
            htmlcast = list(set(htmlcast))

            # remove File Studio Name
            htmlcast = [x for x in htmlcast if not '.tv' in x.lower()]
            htmlcast = [x for x in htmlcast if not '.com' in x.lower()]
            htmlcast = [x for x in htmlcast if not '.net' in x.lower()]
            htmlcast = [x for x in htmlcast if not FILMDICT['Studio'].replace(' ', '').lower() in x.replace(' ', '').lower()]

            # as cast is found in summary text and actors can be referred to by their first names only; remove these
            htmlcast = [l for i, l in enumerate(htmlcast) if True not in [l in x for x in htmlcast[0:i]]]

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

        # 2b.   Posters/Art - First Image set to Poster, next to Art
        self.log(LOG_BIGLINE)
        imageType = 'Poster & Art'
        try:
            htmlimages = html.xpath('.//a[@class="aimg"]/img/@data-lazy-src')
            htmlimages = [x for x in htmlimages if 'data:image' not in x]
            self.log('UPDATE:: %s Images Found: %s', len(htmlimages), htmlimages)
            for index, image in enumerate(htmlimages):
                if index > 1:
                    break
                whRatio = 1.5 if index == 0 else 0.5625
                imageType = 'Poster' if index == 0 else 'Art'
                pic, picContent = self.getFilmImages(imageType, image, whRatio)    # height is 1.5 times the width for posters
                if index == 0:      # processing posters
                    #  clean up and only keep the posters we have added
                    metadata.posters[pic] = Proxy.Media(picContent, sort_order=1)
                    metadata.posters.validate_keys([pic])
                    self.log(LOG_SUBLINE)
                elif BACKGROUND:               # processing art
                    metadata.art[pic] = Proxy.Media(picContent, sort_order=1)
                    metadata.art.validate_keys([pic])

        except Exception as e:
            self.log('UPDATE:: Error getting %s: %s', imageType, e)

        # 2a.   Summary = IAFD Legend + Synopsis
        self.log(LOG_BIGLINE)
        # synopsis
        try:
            synopsis = ''
            htmlsynopsis = html.xpath('//article[@id and @class]/p')
            for item in htmlsynopsis:
                synopsis = '{0}{1}\n'.format(synopsis, item.text_content())
            self.log('UPDATE:: Synopsis Found: %s', synopsis)

            regex = r'See more.*'
            pattern = re.compile(regex, re.IGNORECASE)
            synopsis = re.sub(pattern, '', synopsis)
        except:
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