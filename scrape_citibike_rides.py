import mechanize
import cookielib
from BeautifulSoup import BeautifulSoup
import html2text
from datetime import datetime
import getpass
import csv
from collections import Counter

# Helper function to convert the citibike duration string into seconds
# Duration is x h y min z s, convert to an int
def getDurationInSeconds(durationString):
  # If it doesn't have min, then they don't have a recorded time
  if durationString.find('min') is -1:
    return float('nan')

  hours = 0
  if durationString.find('h') is not -1:
    hours = int(durationString[0:(durationString.find("h") - 1)])
    minutes = int(durationString[(durationString.find("h") + 2):(durationString.find("min") - 1)])
  else:
    minutes = int(durationString[0:(durationString.find("min") - 1)])
  
  seconds = int(durationString[(durationString.find("min") + 4):(durationString.find("s") - 1)])
  return minutes * 60 + seconds

# Helper function to convert date string to a datetime object
def getDatetimeFromString(datetime_string):
  try:
    return datetime.strptime(datetime_string, '%m/%d/%Y %I:%M:%S %p')
  except:
    return None

# Creates a browser with a cookie jar so we can login and then navigate to
# other pages while still logged in
def getBrowserForScrape():
  browser = mechanize.Browser()

  cookie_jar = cookielib.LWPCookieJar()
  browser.set_cookiejar(cookie_jar)

  browser.set_handle_equiv(True)
  browser.set_handle_gzip(True)
  browser.set_handle_redirect(True)
  browser.set_handle_referer(True)
  browser.set_handle_robots(False)
  browser.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

  browser.addheaders = [('User-agent', 'Chrome')]

  return browser

# Logs the browser into the citibike website for a sepecific user
def loginToCitibikeWebsite(browser, username, password):
  browser.open('https://member.citibikenyc.com/profile/login')

  # The login form is the second form on the page, this is brittle and
  # could change.
  browser.select_form(nr=1)

  browser.form['_username'] = username
  browser.form['_password'] = password

  browser.submit()

# Everyones trips page has a different url, to find it we can scrape the profile page
# It takes the form https://member.citibikenyc.com/profile/trips/01234567-1?pageNumber=
# This function strips the page number and simply returns a url ending in ..."pageNumber="
def getURLForTripsPage(browser):
  pageContent = browser.open('https://member.citibikenyc.com/profile/').read()
  soup = BeautifulSoup(pageContent)
  trips_link = soup.find('a', 'ed-panel__link ed-panel__link_summary ed-panel__link_last-trip ed-panel__link_standard')
  return trips_link['href'][:-1]

# Scrapes an individual trip from it's div. This function returns an array of the trip
# data, all represented as strings. This makes it easy to write this whole thing to a csv
# for later use. If you want to convert this strings to python objects there are helper
# functions above
def scrapeTripDiv(trip):
  startTime = trip.find("div", "ed-table__item__info__sub-info_trip-start-date").getText()
  endTime = trip.find("div", "ed-table__item__info__sub-info_trip-end-date").getText()
  startStation = trip.find("div", "ed-table__item__info__sub-info_trip-start-station").getText()
  endStation = trip.find("div", "ed-table__item__info__sub-info_trip-end-station").getText()
  duration = trip.find("div", "ed-table__col_trip-duration").getText()

  return [startTime, endTime, startStation, endStation, duration]

# Returns an array of arrays. Each array is a single trip.
def scrapeRides(username, password):
  browser = getBrowserForScrape()
  loginToCitibikeWebsite(browser, username, password)
  url = getURLForTripsPage(browser)

  trips = []
  pageNumber = 1

  while True:
    pageContent = browser.open(url + str(pageNumber)).read()
    soup = BeautifulSoup(pageContent)

    # If you provide too high a page number citibike simply returns the final page content
    # So we can check the current page number to see when we should stop
    if int(soup.find("input", "ed-paginated-navigation__jump-to__page").get('value')) is not pageNumber:
      break

    print "Scraping page: " + str(pageNumber)
    trips += [scrapeTripDiv(trip) for trip in soup.findAll('div', "ed-table__item_trip")]
    pageNumber += 1

  return trips

# Writes all the trip data to a csv
def writeToCSV(filename, trips):
  with open(filename, 'wb') as csvfile:
    writer = csv.writer(csvfile, delimiter = ' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    for trip in trips:
      writer.writerow(trip)

# Converts an array of strings representing a trip (a format easy for writing to files)
# into a dictionary with python objects instead of strings. Datetime objects for start
# and end time, strings for the station names, and the duration in seconds as an int
def convertTripArrayToDictionary(trip_array):
  return {'start_time': getDatetimeFromString(trip_array[0]),
          'end_time': getDatetimeFromString(trip_array[1]),
          'start_station': trip_array[2],
          'end_station': trip_array[3],
          'duration': getDurationInSeconds(trip_array[4])}

# Reads back trip data written by writeToCSV into an array of dictionaries
# See convertTripArrayToDictionary for details
def readFromCSV(filename):
  with open(filename, 'rb') as csvfile:
    reader = reader = csv.reader(csvfile, delimiter=' ', quotechar='|')
    return [convertTripArrayToDictionary(row) for row in reader]

# This module can be run to get a scrape of all your citibike trips written to a csv
# file in this directory. This could take a few minutes depending on the number of
# rides you've taken. The filename will reflect your username and the current time.
# You can use the readFromCSV function above to read this data back later.
if __name__ == '__main__':
  username = raw_input('Enter your citibike username:')
  password = getpass.getpass()
  
  trips = scrapeRides(username, password)
  
  filename = "citibike_scrape_" + username + datetime.now().strftime("%Y-%m-%d_%H:%M:%S") + ".csv"
  writeToCSV(filename, trips)
