<?php

	// This Source Code Form is subject to the terms of the Mozilla Public
	// License, v. 2.0. If a copy of the MPL was not distributed with this
	// file, You can obtain one at https://mozilla.org/MPL/2.0/.

	// See the README.md file for a description of this script.

	$program_start_timestamp = time();

	require('darksky-api.conf.php');

	/****************************************************************************
	*                            F u n c t i o n s                              * 
	****************************************************************************/

	require('MoonPhase.php');
	require('VincentyGreatCircleDistance.php');

	//  Convert metres to miles
	function m2M($metres) {
		return round($metres / 1609.34, 2);
	}

	//  Parse the date strings with interval specs that NOAA uses
	//  and return start and end timestamps for the interval
	function parseInterval($datestring) {
		$parts = explode('/', $datestring);
		$start = new DateTime($parts[0]);
		$end = new DateTime($parts[0]);
		if ($parts[1]) {
			$end->add(new DateInterval($parts[1]));
		}
		return array('start' => $start->format('U'), 'end' => $end->format('U'));
	}

	//  Calculate the average value of an element from the griddata query
	//  within a given time period	
	function calculateGriddataAverage($elements, $start, $end) {
		$total = 0;
		$total_hours = 0;
		foreach($elements as $element) {
			$interval = parseInterval($element['validTime']);
			if ($interval['end'] > $start and $interval['start'] <= $end) {
				if ($interval['start'] < $start) {
					$interval['start'] = $start;
				}					
				if ($interval['end'] > $end) {
					$interval['end'] = $end;
				}
				$hours = ($interval['end'] - $interval['start']) / 3600;
				$total = $total + ($element['value'] * $hours);
				$total_hours = $total_hours + $hours;
			}
		}
		if ($total_hours == 0) {
			return false;
		} else {
			return $total / $total_hours;
		}
	}

	//  Map the names of the icons used
	function mapIcons($icon) {

		// The complete DarkSky icon set:
		// 		clear-day.png    
		// 		clear-night.png  
		// 		cloudy.png  
		// 		fog.png     
		// 		partly-cloudy-day.png    
		// 		partly-cloudy-night.png  
		// 		rain.png   
		// 		sleet.png  
		// 		snow.png
		// 		wind.png

		//  See https://openweathermap.org/weather-conditions#How-to-get-icon-URL
		$openweathermap_icon_list = array(
			'01d' => 'clear-day',
			'02d' => 'partly-cloudy-day',
			'03d' => 'cloudy',
			'04d' => 'partly-cloudy-day',
			'09d' => 'rain',
			'10d' => 'rain',
			'11d' => 'rain',
			'13d' => 'snow',
			'50d' => 'fog',
			'01n' => 'clear-night',
			'02n' => 'partly-cloudy-night',
			'03n' => 'cloudy',
			'04n' => 'partly-cloudy-night',
			'09n' => 'rain',
			'10n' => 'rain',
			'11n' => 'rain',
			'13n' => 'snow',
			'50n' => 'fog'
		);

		//  NOAA icon names aren't currntly used in this script so
		//  thie should be dead code.  It's here just in case I ever
		//  need to change things.
		$noaa_icon_list = array(
			'/land/day/bkn' => 'partly-cloudy-day',
			'/land/day/few' => 'clear-day',
			'/land/day/fog' => 'fog',
			'/land/day/rain_showers' => 'rain',
			'/land/day/sct' => 'partly-cloudy-day',
			'/land/day/tsra' => 'rain',
			'/land/day/wind_bkn' => 'wind',
			'/land/day/wind_sct' => 'wind',
			'/land/night/bkn' => 'partly-cloudy-night',
			'/land/night/few' => 'clear-night',
			'/land/night/fog' => 'fog',
			'/land/night/rain_showers' => 'rain',
			'/land/night/sct' => 'partly-cloudy-night',
			'/land/night/tsra' => 'rain',
			'/land/night/wind_bkn' => 'wind',
			'/land/night/wind_sct' => 'wind',
		);

		if (array_key_exists($icon, $openweathermap_icon_list)) {
			return $openweathermap_icon_list[$icon];
		} else {
			preg_match('/\/icons\/[^?]*/', $icon, $matches);
			$noaa_icon = str_replace('/icons', '', $matches[0]);
			$noaa_icon = explode(',', $noaa_icon)[0];
			if (array_key_exists($icon, $noaa_icon_list)) {
				return $noaa_icon_list[$noaa_icon];
			} else {
				return $icon;
			}
		}
	}

	//  Send an email whenever a program error occurs
	function myErrorHandler($errno, $errmsg, $errfile, $errline) {
		require('darksky-api.conf.php');
		$errmsg = '<b>Error:</b> [' . $errno . '] "' . $errmsg . '" at line ' . 
			$errline . ' of ' . $errfile;
		http_response_code(501);
		error_log($errmsg, 1, $error_email_to, 'From: ' . $error_email_from);
		error_log($errmsg);
		exit($errno);
	}
	set_error_handler('myErrorHandler');
	
	/****************************************************************************
	*                                B e g i n                                  * 
	****************************************************************************/

	//  The user must provide latitude and logitude parameters in the URL
	//  unless they run the script from the command line with the single
	//  parameter "test".  In that case the coordinates for the East
	//  Grand Rapids police station will be used.
	if (array_key_exists('lat', $_GET)) {
		$latitude = $_GET['lat'];
	} else if ($argc ==2 and $argv[1] == 'test') {
		$latitude = 42.948477;
	} else {
		http_response_code(400);
		exit('No latitude parameter ("lat=N") specified in the URL');
	}
	if (array_key_exists('long', $_GET)) {
		$longitude = $_GET['long'];
	} else if ($argc == 2 and $argv[1] == 'test') {
		$longitude = -85.610534;
	} else {
		http_response_code(400);
		exit('No longitude parameter ("long=N") specified in the URL');
	}
	
	//  Set up a skeleton array to contain the DarkSky formated output
	$output = array(
		'latitude' => $latitude,
		'longitude' => $longitude,
		'timezone' => '',
		'currently' => array(),
		'hourly' => array(),
		'daily' => array(),
		'alerts' => array(),
		'flags' => array(
			'sources' => array('noaa','openweathermap'),
			'nearest-station'=> 5000,
			'units'=> 'us'
		),
		'offset' => 0
	);
	
	//  Ask OpenWeatherMap for their One Call API weather data
	$url = 'https://api.openweathermap.org/data/2.5/onecall?lat=' . $latitude .
		'&lon=' . $longitude . '&appid=' . $openweathermap_api_key . '&units=imperial';
	if (($response_data = file_get_contents($url)) !== false) {
		$openweathermap_obj = json_decode($response_data, true);
	} else {
		myErrorHandler('501', 'OpenWeatherMap API did not respond');
	}

	//  Set the timezone
	$output['timezone'] = $openweathermap_obj['timezone'];
	$utc_tz = new DateTimeZone("UTC");
	$point_tz = new DateTimeZone($output['timezone']);
	$now = new DateTime("now", $utc_tz);
	$output['offset'] = $point_tz->getOffset($now) / 3600;

	/****************************************************************************
	*                            C u r r e n t l y                              * 
	****************************************************************************/
	
	//  Map the OpenWeatherMap data into the "currently" part of the output array
	$props = $openweathermap_obj['current'];
	$output['currently'] = array(
		'time' => $props['dt'],
		'summary' => ucfirst($props['weather'][0]['description']),
		'icon' => mapIcons($props['weather'][0]['icon']),
		'temperature' => $props['temp'],
		'apparentTemperature' => $props['feels_like'],
		'dewPoint' => $props['dew_point'],
		'humidity' => round($props['humidity'] / 100, 2),
		'pressure' => $props['pressure'],
		'windSpeed' => $props['wind_speed'],
		'windGust' => null,
		'windBearing' => $props['wind_deg'],
		'cloudCover' => round($props['clouds'] / 100, 2),
		'uvIndex' => $props['uvi'],
		'visibility' => m2M($props['visibility'])
	);

	//  All requests to the NOAA API require this context, including the
	//  User-Agent header which they treat as a sort of API key.
	$noaa_opts = array(
		'http' => array(
			'method' => "GET",
			'header' => "User-Agent: " . $noaa_api_key . "\r\nAccept: application/geo+json\r\n"
		)
	);
	$noaa_context = stream_context_create($noaa_opts);

	//  Ask NOAA to give us the gridpoint coordinates corresponding to the
	//  latitude and longitude that we received from the user
    $url = 'https://api.weather.gov/points/' . $latitude . ',' . $longitude;
	if (($response_data = file_get_contents($url, false, $noaa_context)) !== false) {
		$noaa_points_obj = json_decode($response_data, true);
	} else {
		myErrorHandler('501', 'NOAA API did not respond');
	}
	
	//  Using the stations URL that we got from the NOAA points lookup,
	//  find the nearest station and get its dstance away.  Add this to
	//  the output array.
	$url = $noaa_points_obj['properties']['observationStations'];
	if (($response_data = file_get_contents($url, false, $noaa_context)) !== false) {
		$noaa_stations_obj = json_decode($response_data, true);
		foreach ($noaa_stations_obj['features'] as $feature) {
			$miles = vincentyGreatCircleDistance($latitude, $longitude, 
				$feature['geometry']['coordinates'][1], 
				$feature['geometry']['coordinates'][0]
			);
			if ($miles < $output['flags']['nearest-station']) {
				$noaa_station_url = $feature['id'];
				$output['flags']['nearest-station'] = round($miles, 2);
			}
		}
	}

	/****************************************************************************
	*                                H o u r l y                                * 
	****************************************************************************/
	
	//  Populate an hourly data array with the 48 hours of data that came
	//  from the OpenWeatherMap API call
	$data = array();
	foreach($openweathermap_obj['hourly'] as $hour) {
		$data[] = array(
			'time' => $hour['dt'],
			'summary' => ucfirst($hour['weather'][0]['description']),
			'icon' => mapIcons($hour['weather'][0]['icon']),
			'precipProbability' => null,
			'precipType' => null,
			'temperature' => $hour['temp'],
			'apparentTemperature' => $hour['feels_like'],
			'dewPoint' => $hour['dew_point'],
			'humidity' => round($hour['humidity'] / 100, 2),
			'pressure' => $hour['pressure'],
			'windSpeed' => $hour['wind_speed'],
			'windGust' => null,
			'windBearing' => $hour['wind_deg'],
			'cloudCover' => round($hour['clouds'] / 100, 2)
		);
	}

	//  Using the gridpoints URL that we got from the NOAA points lookup,
	//  get the detailed forecast information and fill in the precipProbability
	//  and visibility elements that OpenWeatherMap didn't give us.
	$url = $noaa_points_obj['properties']['forecastGridData'];
	if (($response_data = file_get_contents($url, false, $noaa_context)) !== false) {
		$noaa_griddata_obj = json_decode($response_data, true);
		$props = $noaa_griddata_obj['properties'];

		//  Set precipitation probability percentage
		foreach($props['probabilityOfPrecipitation']['values'] as $value) {
			$interval = parseInterval($value['validTime']);
			$timestamp = $interval['start'];
			while ($timestamp < $interval['end']) {
				for ($i = 0; $i < count($data); $i++) {
					if ($timestamp == $data[$i]['time']) {
						$data[$i]['precipProbability'] = $value['value'] / 100;
						break;
					}
				}
				$timestamp = $timestamp + 3600;
			}
		}
		
		//  Set miles of visibility.  NOAA only provides 24 hours of this
		//  data so "visibility" will be null in second 24 hours of the 
		//  "hourly" array.
		foreach($props['visibility']['values'] as $value) {
			$interval = parseInterval($value['validTime']);
			$timestamp = $interval['start'];
			while ($timestamp < $interval['end']) {
				for ($i = 0; $i < count($data); $i++) {
					if ($timestamp == $data[$i]['time']) {
						//  This value is in meters, there are 1609.34 meters in a mile
						$data[$i]['visibility'] = round($value['value'] / 1609.34, 2);
						break;
					}
				}
				$timestamp = $timestamp + 3600;
			}
		}
		
		//  Set the precipitation type name based on what's in the NOAA 
		//  "weather" attribute
		foreach($props['weather']['values'] as $value) {
			$interval = parseInterval($value['validTime']);
			$timestamp = $interval['start'];
			while ($timestamp < $interval['end']) {
				for ($i = 0; $i < count($data); $i++) {
					if ($timestamp == $data[$i]['time']) {
						if ($value['value'][0]['weather']) {
							$data[$i]['precipType'] = 
								explode('_', $value['value'][0]['weather'])[0];
						}
						break;
					}
				}
				$timestamp = $timestamp + 3600;
			}
		}		
	}

	//  Add the hourly section to the output
	$output['hourly'] = array(
		'summary' => null,
		'icon' => null,
		'data' => $data
	);

	/****************************************************************************
	*                                 D a i l y                                 * 
	****************************************************************************/

	//  Populate a daily data array with the 8 days of data that came from
	//  the OpenWeatherMap API call
	$data = array();
	foreach($openweathermap_obj['daily'] as $day) {
		$moon = new Solaris\MoonPhase($day['dt']);
		$data[] = array(
			'time' => $day['dt'],
			'summary' => ucfirst($day['weather'][0]['description']),
			'icon' => mapIcons($day['weather'][0]['icon']),
			'sunriseTime' => $day['sunrise'],
			'sunsetTime' => $day['sunset'],
			'moonPhase' => round($moon->get('illumination'), 2),
			'precipProbability' => null,
			'precipType' => null,
			'temperatureHigh' => null,
			'temperatureHighTime' => null,
			'temperatureLow' => null,
			'temperatureLowTime' => null,
			'apparentTemperatureHigh' => null,
			'apparentTemperatureHighTime' => null,
			'apparentTemperatureLow' => null,
			'apparentTemperatureLowTime' => null,
			'dewPoint' => $day['dew_point'],
			'humidity' => $day['humidity'],
			'pressure' => $day['pressure'],
			'windSpeed' => $day['wind_speed'],
			'windGust' => null,
			'windGustTime' => null,
			'windBearing' => $day['wind_deg'],
			'cloudCover' => round($day['clouds'] /100, 2),
			'uvIndex' => $day['uvi'],
			'temperatureMin' => null,
			'temperatureMinTime' => null,
			'temperatureMax' => null,
			'temperatureMaxTime' => null,
			'apparentTemperatureMin' => null,
			'apparentTemperatureMinTime' => null,
			'apparentTemperatureMax' => null,
			'apparentTemperatureMaxTime' => null
		);
	}

	//  Scan the results of the NOAA griddata query to collect all the
	//  mins and maxes for the "daily" section of the output.
	$props = $noaa_griddata_obj['properties'];
	for ($i = 0; $i < count($data); $i++) {
		$start = $data[$i]['time'];
		$end = $start + (3600 * 24);

		//  Set the min/max temperatures
		foreach($props['temperature']['values'] as $prop) {
			$timestamp = strtotime(explode('/', $prop['validTime'])[0]);
			if ($timestamp >= $end) {
				break;
			}
			$value = round(($prop['value'] * 9 / 5) + 32, 2);
			if ($timestamp >= $start and $timestamp < $end) {
				if (!$data[$i]['temperatureHigh'] or ($value > $data[$i]['temperatureHigh'])) {
					$data[$i]['temperatureHigh'] = $value;
					$data[$i]['temperatureHighTime'] = $timestamp;
					$data[$i]['temperatureMax'] = $value;
					$data[$i]['temperatureMaxTime'] = $timestamp;
				}
				if (!$data[$i]['temperatureLow'] or ($value < $data[$i]['temperatureLow'])) {
					$data[$i]['temperatureLow'] = $value;
					$data[$i]['temperatureLowTime'] = $timestamp;
					$data[$i]['temperatureMin'] = $value;
					$data[$i]['temperatureMinTime'] = $timestamp;
				}
			}
		}

		//  Set the min/max apparentTemperatures
		foreach($props['apparentTemperature']['values'] as $prop) {
			$timestamp = strtotime(explode('/', $prop['validTime'])[0]);
			if ($timestamp >= $end) {
				break;
			}
			$value = round(($prop['value'] * 9 / 5) + 32, 2);
			if ($timestamp >= $start and $timestamp < $end) {
				if (!$data[$i]['apparentTemperatureHigh'] or 
					($value > $data[$i]['apparentTemperatureHigh'])) {
					$data[$i]['apparentTemperatureHigh'] = $value;
					$data[$i]['apparentTemperatureHighTime'] = $timestamp;
					$data[$i]['apparentTemperatureMax'] = $value;
					$data[$i]['apparentTemperatureMaxTime'] = $timestamp;
				}
				if (!$data[$i]['apparentTemperatureLow'] or 
					($value < $data[$i]['apparentTemperatureLow'])) {
					$data[$i]['apparentTemperatureLow'] = $value;
					$data[$i]['apparentTemperatureLowTime'] = $timestamp;
					$data[$i]['apparentTemperatureMin'] = $value;
					$data[$i]['apparentTemperatureMinTime'] = $timestamp;
				}
			}
		}

		//  Set the average precipProbability
		$avg = calculateGriddataAverage($props['probabilityOfPrecipitation']['values'],
			$start, $end);
		if ($avg) {
			$data[$i]['precipProbability'] = round($avg, 2);
		}

		//  Set the maximum windGust and the asscoiated timestamp
		foreach($props['windGust']['values'] as $prop) {
			$timestamp = strtotime(explode('/', $prop['validTime'])[0]);
			if ($timestamp >= $end) {
				break;
			}
			$value = round($prop['value'] * 2.23694, 2);
			if ($timestamp >= $start and $timestamp < $end) {
				if (!$data[$i]['windGust'] or ($value > $data[$i]['windGust'])) {
					$data[$i]['windGust'] = $value;
					$data[$i]['windGustTime'] = $timestamp;
				}
			}
		}

		//  Set the average visibility (NOAA only provides 24 hours of data)
		$avg = calculateGriddataAverage($props['visibility']['values'], $start, $end);
		if ($avg) {
			//  This value is in meters, there are 1609.34 meters in a mile
			$data[$i]['visibility'] = round($avg / 1609.34, 2);
		}

	}

	//  Add the daily section to the output
	$output['daily'] = array(
		'summary' => null,
		'icon' => null,
		'data' => $data
	);

	/****************************************************************************
	*                                A l e r t s                                * 
	****************************************************************************/

	//  Ask NOAA for any alerts that pertain to this location and add them
	//  to the output array.  If there are none, delete the "alerts" key
	//  from the output array.
	$url = 'https://api.weather.gov/alerts?point=' . $latitude . ',' . $longitude;
	if (($response_data = file_get_contents($url, false, $noaa_context)) !== false) {
		$noaa_alerts_obj = json_decode($response_data, true);
		if (array_key_exists('features', $noaa_alerts_obj)) {
			
			//  Get a list of the counties in the state that contains 
			//  this point's location
			$county_list = array();
			$url = 'https://api.weather.gov/zones?type=county&area=' .
				$noaa_points_obj['properties']['relativeLocation']['properties']['state'];
			if (($response_data = file_get_contents($url, false, $noaa_context)) !== false) {
				$noaa_zones_obj = json_decode($response_data, true);
				foreach($noaa_zones_obj['features'] as $feature) {
					$county_list[$feature['properties']['id']] = $feature['properties']['name'];
				}
			}
			
			//  Build an array containing all of the alerts
			$data = array();
			foreach($noaa_alerts_obj['features'] as $alert) {
				$props = $alert['properties'];
				
				//  Don't include expired alerts
				if (strtotime($props['expires']) > time()) {
					
					//  Map the region codes in the alert to the list of 
					//  county names we built above
					$regions = array();		
					foreach($props['geocode']['UGC'] as $id) {
						$regions[] = $county_list[$id];
					}

					//  Add the alert to the alerts data array
					$data[] = array(
						'title' => $props['event'],
						'regions' => $regions,
						'severity' => $props['severity'],
						'time' => strtotime($props['onset']),
						'expires' => strtotime($props['expires']),
						'description' => preg_replace('/\s+/', ' ', $props['description']),
						'url' => $props['@id']
					);
					
				}
			}
			
			//  Add the alerts array to the output array
			$output['alerts'] = $data;
			
		}

		//  If there are no alerts then delete the alerts key from
		//  the output array
		if (count($output['alerts']) == 0) {
			unset($output['alerts']);
		}
			
	}
	
	//  Write our output
	header('Cache-Control: max-age=600');
	header('X-Forecast-API-Calls: 0');
	$elapsed = time() - $program_start_timestamp;
	header('X-Response-Time: ' . $elapsed);
	header('Content-type: application/json');
	echo json_encode($output);
//	echo json_encode($output, JSON_PRETTY_PRINT);

?>
