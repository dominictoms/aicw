import os
import json
import re
import math

import spacy
from spacy.tokens import Doc
from spacy.matcher import Matcher
from spacy.lang.en import English

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from datetime import time, datetime, timedelta

from dateutil.parser import parse


def main():

	# create a prediction object
	test = trainPredict()


	#test.newQuery("i want to take a train to manchester airport from london liverpool street at 10:15 PM on sunday")

	test.newQuery()

class trainPredict():

	def __init__(self):

		# key tiploc : {name longname alpha3}
		self.days = {}

		self.stationPatterns = []

		self.nlp = spacy.load("en_core_web_sm")

		self.stationRuler = self.nlp.add_pipe("entity_ruler", before='ner')

		wordTimePatterns = [
			{"label": "WORDTIME", "pattern": [{"LOWER": "midday"}], 'id': 0},
			{"label": "WORDTIME", "pattern": [{"LOWER": "midnight"}], 'id': 1},
			{"label": "WORDTIME", "pattern": [{"LOWER": "quarter"},{"LOWER": "to"}], 'id': 2},
			{"label": "WORDTIME", "pattern": [{"LOWER": "quarter"},{"LOWER": "past"}], 'id': 3},	
			{"label": "WORDTIME", "pattern": [{"LOWER": "half"},{"LOWER": "past"}], 'id': 4},
			]

		# read the csv file
		self.loadFromCsv()

		#self.stationRuler.add_patterns([{"label": "domLovesCock", "pattern": "manchester"}])
		self.stationRuler.add_patterns(self.stationPatterns)
		self.stationRuler.add_patterns(wordTimePatterns)
		#self.stationRuler.add_patterns([{"label": "domLovesFatBigBulgingVeinyCocks", "pattern": [{"LOWER": "manchester"}, {"LOWER": "airport"}]}])

		
		
	def loadFromCsv(self):

		# open the csv file containing every station
		script_dir = os.path.dirname(os.path.abspath(__file__))
		with open(os.path.join(script_dir, "stations.csv"), 'r') as file:

			# get all the lines in the csv file
			lines = file.readlines()

			# remove header from csv file
			lines.pop(0)

			# iterate through every line
			for line in lines:

				# strip whitespace and linebreaks from line
				line = line.replace('"', '').replace('\n', '')

				# split line at commas
				namesSplit = line.split(',')

				# add station to dict, use the tiploc as the key
				name = namesSplit[0]
				longname = namesSplit[1]
				alpha3 =  namesSplit[4]
				tiploc =namesSplit[3]

				# add longname
				longname_patterns = []
				for word in longname.split():
					longname_patterns.append({"LOWER": word.lower()})

				self.stationPatterns.append(
					{"label": "STATION", "pattern": longname_patterns, 'id': tiploc}
				)

				if len(longname_patterns) >= 3:

					longname_patterns = longname_patterns[:-2]

					if longname_patterns[0] == 'London':
						longname_patterns.pop(0)

					self.stationPatterns.append(
						{"label": "STATION", "pattern": longname_patterns, 'id': tiploc}
					)


				# add name
				name_patterns = []
				for word in name.split():
					name_patterns.append({"LOWER": word.lower()})

				self.stationPatterns.append(
					{"label": "STATION", "pattern": name_patterns, 'id': tiploc}
				)

				while "LONDON" in name_patterns:
					name_patterns.remove("LONDON")

				self.stationPatterns.append(
					{"label": "STATION", "pattern": name_patterns, 'id': tiploc}
				)


	# run a new query
	def newQuery(self, query  = None):

		if query == None:
			query = input("Hello! How can I help?\n> ")


		current_datetime = datetime.now()
		date = current_datetime.date() # will need too check with user if this is right
		time = current_datetime.time()
		toStation = None # location defult like time
		fromStation = None
		
		# put query through nlp pipeline
		doc = self.nlp(query)
		for i, token in enumerate(doc):

			
			if token.text == "to":
				if doc[i+1].ent_type_:
					toStation = doc[i + 1].ent_id_
			elif token.text == "from":
				if doc[i+1].ent_type_:
					fromStation = doc[i + 1].ent_id_
			elif token.text == "on": # date
				if doc[i+1].ent_type_:
					date = parse(doc[i + 1].text)
			elif token.text == "at": # time
				if doc[i+1].ent_type_ == "WORDTIME":

					time = doc[i + 1].ent_id_
				else:
					time = self.toTime(doc[i + 1].text + ' ' +  doc[i + 2].text)

		# get a to station
		while toStation == None:

			if fromStation != None:
				query = input(f"I see you want to travel from {fromStation}, where are you going to\n> ")

			else:
				query = input(f"Where are you travelling to?\n> ")

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					toStation = token.ent_id_

		# get a from station
		while fromStation == None:

			if toStation != None:
				query = input(f"I see you want to travel to {toStation}, where are you travelling from?\n> ")

			else:
				query = input(f"Where are you travelling from?\n> ")

			doc = self.nlp(query)

			for token in doc:
				if token.ent_type_:
					fromStation = token.ent_id_


		# format the date for the web scraping
		formatted_date = date.strftime("%d %m %y")
		day, month, year = formatted_date.split()

		# format the time for the web scraping
		formatted_time = time.strftime("%H %M")
		hour, minute = formatted_time.split()

		# round minute up to the next 15 minutes
		minute = str(math.ceil(int(minute) / 15) * 15)


		url = getUrl(fromStation, toStation, day, month, year, hour, minute)


		price = getPrice(url)
		
		if price != None:
			print(f"The cheapest ticket is {price}!")
			print(f"You can get a ticket here: {url}")

		else:
			print("Sorry we fucked up")




	def toTime(self, timeStr):


		match = re.search(r'(\d{1,2}):(\d{2})(?:\s?(AM|PM))?', timeStr, re.IGNORECASE)
		if match:
			hour, minute, period = match.groups()
			hour = int(hour)
			minute = int(minute)
			if period and period.lower() == 'pm' and hour != 12:
				hour += 12
			elif period and period.lower() == 'am' and hour == 12:
				hour = 0
			foundTime = time(hour, minute)
		return(foundTime)



def getPrice(url):

	# configure chromium
	chrome_options = Options()
	chrome_options.add_argument("--headless")
	driver = webdriver.Chrome(options=chrome_options)

	# load our url
	driver.get(url)

	# attempt to get price
	try:

		# get the box containing the price
		price_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "jp-class-jp-results-standard")))

		# return the price
		return re.search(r"£\d+(\.\d+)?", price_box.get_attribute("aria-label")).group()

	# something fucked up
	except:
		return None

# get the url from national rail
def getUrl(origin, destination, date, month, year, hour, minute):
	return f'https://www.nationalrail.co.uk/journey-planner/?type=single&origin={origin}&destination={destination}&leavingType=departing&leavingDate={date}{month}{year}&leavingHour={hour}&leavingMin={minute}&adults=1&extraTime=0#O'
	


if __name__ == '__main__':
	main()
