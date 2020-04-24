# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

'''
Common functions used by both the NOAAWeatherAPI and Climacell modules
'''

import requests

#  isodate may be available in distro packages, or may need to be
#  installed with pip
import isodate

def getURL(url, headers=None, flask_app=None):
	"""
	Get the results of an API call to the NOAA or Climacell weather APIs
	and handle any errors which might occur.
	
	url: a string
	headers: a "requests"-style dictionary array of header names and values
	flask_app : an object containing a Flask application's details.  Used
	            to allow us to write into the application log.
	
	Returns a JSON object or "False" if an error occurred
	"""
	response = requests.get(url, headers=headers)
	if response.status_code == 200:
		return response.json()
	elif response.status_code == 403:
		message_text = '[403] Access denied.  Do you have a valid API key for this service? {}'.format(url)
	elif response.status_code in [502, 504] and '/api.weather.gov/' in url:
		message_text = '[{}] NOAA service unavailable: {}'.format(response.status_code, url)
	else:
		message_text = '[{}] Unexpected response from service: {}\n\n{}'.format(response.status_code, url, response.text)
		
	if flask_app:
		flask_app.logger.error(message_text)
	print(message_text)
	return False

def getKeyValue(dictionary_element, key_list, func=None):
	"""
	Returns a specific value from a dictionary array, in this case from
	a JSON object returned from an NOAA or Climacell weather API call.
	This function checks to be sure that each key in the key_list exists
	before proceeding.  This is necessary because the APIs being used do
	not always return all of the keys in their specifications.
	
	dictionary: the dictionary array
	key_list:   an array of keys that lead down from the top level of the
	            array down to the actual element that is to be returned.
	func:       a function that it to be applied to the value before it
	            is returned.  Mainly intended to be used for rounding or
	            for units conversions.

	Returns the value of the specified dictionary element or "None" if that
	element does not exist.
	"""
	for key in key_list:
		if isinstance(key, int):
			if key < len(dictionary_element):
				dictionary_element = dictionary_element[key]
			else:
				return None
		else:
			if key in dictionary_element:
				dictionary_element = dictionary_element[key]
			else:
				return None
	if dictionary_element and func:
		return func(dictionary_element)
	else:
		return dictionary_element

def parseInterval(time_str, tz_string=None):
	"""
	Parse the ISO8601 date strings with interval/duration specs that NOAA
	uses and return start and end UNIX timestamps for the interval
	
	time_str: an ISO8601-compliant time string, optionally including a
	          duration specification, for example:
              2020-04-10T16:00:00-00:00/P6DT22H
	          
	Returns a dictionary array containing one or two timestamp elements.
	if a duration specification was part of the time_str provided then
	both a "start" and an "end" timestamp element will be returned,
	indicating the start and end times of the duration.  If no duration
	was specified in the time_str, then only a "start" timestamp element
	will be returned.
	"""
	interval = {}
	split_time_str = time_str.split('/')
	start = isodate.parse_datetime(split_time_str[0])
	interval['start'] = int(start.timestamp())
	if len(split_time_str) == 2:
		end = start + isodate.parse_duration(split_time_str[1])
		interval['end'] = int(end.timestamp())
	return interval
