<?php

//  See the "Authentication" section of NOAA's page at 
//  https://www.weather.gov/documentation/services-web-api for details
//  as to what they'd like to see in the "User-Agent" header string.
//  Although I call this an "API key" here, this is, in fact, the text
//  that is associated with the "User-Agent" header.
$noaa_api_key = '(Your Name, you@emailservice.com)';

//  Sign up for free at OpenWeatherMap.org to get their API key.
$openweathermap_api_key = 'Your-API-Key-Goes-Here';

//  The email addresses that should be used as the sender and receiver
//  of messages when there are errors in the script
$error_email_from = 'darksky-api@myserver.com';
$error_email_to = 'you@emailservice.com';

?>
